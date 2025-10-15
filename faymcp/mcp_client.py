#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import sys
import threading
import inspect
import time
from contextlib import AsyncExitStack
from typing import Optional, Dict, Any, Tuple, List, Callable

from mcp import ClientSession
from mcp.client.sse import sse_client
from faymcp import tool_registry

# 尝试导入本地 stdio 传输
try:
    from mcp.client.stdio import stdio_client, StdioServerParameters
    HAS_STDIO = True
except Exception:
    stdio_client = None
    StdioServerParameters = None
    HAS_STDIO = False

logger = logging.getLogger(__name__)


def _is_awaitable(obj: Any) -> bool:
    try:
        return inspect.isawaitable(obj)
    except Exception:
        return False


async def _await_or_value(obj, timeout: Optional[float] = None):
    """如果是 awaitable 则等待（带超时），否则直接返回。"""
    if _is_awaitable(obj):
        if timeout is not None:
            return await asyncio.wait_for(obj, timeout=timeout)
        return await obj
    return obj


class McpClient:
    """
    兼容多版本 mcp 的 MCP 客户端，支持 SSE 与 STDIO。
    修复：部分版本的 list_tools 返回同步 list，如果对其 await 会报
    "object list can't be used in 'await' expression"。
    """

    def __init__(self, server_url: Optional[str] = None, api_key: Optional[str] = None,
                 transport: str = "sse", stdio_config: Optional[Dict[str, Any]] = None,
                 server_id: Optional[int] = None, tools_refresh_interval: int = 60,
                 enabled_lookup: Optional[Callable[[str], bool]] = None):
        self.server_url = server_url
        self.api_key = api_key
        self.transport = transport or "sse"
        if self.transport not in ("sse", "stdio"):
            self.transport = "sse"
        self.stdio_config = stdio_config or {}
        self.server_id = server_id
        self._enabled_lookup = enabled_lookup

        self.session: Optional[ClientSession] = None
        self.tools: Optional[List[Any]] = None
        self.connected = False
        self.exit_stack: Optional[AsyncExitStack] = None

        # timeouts (seconds)
        self.init_timeout_seconds = 30
        self.list_timeout_seconds = 30
        self.call_timeout_seconds = 90

        # dedicated event loop in background thread
        self.event_loop = asyncio.new_event_loop()
        t = threading.Thread(target=self._loop_runner, args=(self.event_loop,), daemon=True)
        t.start()
        self._loop_thread = t

        self._stdio_errlog_file = None
        self._manager_task: Optional[asyncio.Task] = None
        self._disconnect_event: Optional[asyncio.Event] = None
        self._connect_ready_future: Optional[asyncio.Future] = None
        self._last_error: Optional[str] = None

        # tool availability cache
        self.tools_refresh_interval = max(int(tools_refresh_interval), 5)
        self._tool_cache: List[Dict[str, Any]] = []
        self._tool_cache_timestamp: float = 0.0
        self._tools_lock = threading.RLock()
        self._tools_refresh_thread: Optional[threading.Thread] = None
        self._tools_stop_event = threading.Event()

    @staticmethod
    def _loop_runner(loop: asyncio.AbstractEventLoop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def set_enabled_lookup(self, lookup: Optional[Callable[[str], bool]]) -> None:
        """Allow callers to update the enabled-state resolver at runtime."""
        self._enabled_lookup = lookup

    def _clone_tool_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        clone = dict(entry)
        if isinstance(clone.get("inputSchema"), dict):
            clone["inputSchema"] = dict(clone["inputSchema"])
        return clone

    def _sanitize_tools(self, tools: Any) -> List[Dict[str, Any]]:
        sanitized: List[Dict[str, Any]] = []
        if not tools:
            return sanitized

        # Unwrap known container shapes (dict/object with .tools etc.)
        container = tools
        for _ in range(3):
            if container is None:
                break
            if isinstance(container, dict):
                inner = container.get("tools")
                if inner is not None:
                    container = inner
                    continue
            if hasattr(container, "tools"):
                try:
                    inner = getattr(container, "tools")
                except Exception:
                    inner = None
                if inner is not None:
                    container = inner
                    continue
            break

        # Handle responses expressed as iterable of key/value pairs
        try:
            iterable = list(container)
        except TypeError:
            iterable = [container]
        else:
            if iterable and all(isinstance(item, tuple) and len(item) == 2 for item in iterable):
                for key, value in iterable:
                    if key == "tools":
                        return self._sanitize_tools(value)

        for tool in iterable:
            try:
                if hasattr(tool, "name"):
                    name = str(getattr(tool, "name", "")).strip()
                    if not name:
                        continue
                    description = str(getattr(tool, "description", "") or "")
                    input_schema = getattr(tool, "inputSchema", {})
                    if not isinstance(input_schema, dict):
                        input_schema = {}
                    sanitized.append({
                        "name": name,
                        "description": description,
                        "inputSchema": dict(input_schema),
                    })
                elif isinstance(tool, dict) and tool.get("name"):
                    name = str(tool.get("name", "")).strip()
                    if not name:
                        continue
                    entry = {
                        "name": name,
                        "description": str(tool.get("description", "") or ""),
                        "inputSchema": dict(tool.get("inputSchema") or {})
                        if isinstance(tool.get("inputSchema"), dict) else {},
                    }
                    if "enabled" in tool:
                        entry["enabled"] = bool(tool["enabled"])
                    sanitized.append(entry)
                else:
                    # Skip placeholder tuples or metadata fragments
                    if isinstance(tool, tuple) and len(tool) == 2 and isinstance(tool[0], str):
                        continue
                    name = str(tool).strip()
                    if not name:
                        continue
                    sanitized.append({
                        "name": name,
                        "description": "",
                        "inputSchema": {},
                    })
            except Exception as exc:
                logger.debug(f"Failed to normalize MCP tool definition {tool!r}: {exc}")
        return sanitized

    def _apply_tool_cache_update(self, tools: List[Dict[str, Any]]) -> None:
        with self._tools_lock:
            cloned = [self._clone_tool_entry(entry) for entry in tools]
            self._tool_cache = cloned
            self._tool_cache_timestamp = time.time()
            self.tools = [self._clone_tool_entry(entry) for entry in cloned]  # backward compatibility
        if self.server_id is not None:
            tool_registry.set_server_tools(self.server_id, tools, self._enabled_lookup)

    def _get_tool_cache_copy(self) -> List[Dict[str, Any]]:
        with self._tools_lock:
            return [self._clone_tool_entry(entry) for entry in self._tool_cache]

    def get_cached_tools(self) -> List[Dict[str, Any]]:
        """Expose a copy of the cached tool metadata without refreshing remotely."""
        return self._get_tool_cache_copy()

    def _ensure_refresh_worker(self) -> None:
        if self.tools_refresh_interval <= 0:
            return
        with self._tools_lock:
            if self._tools_refresh_thread and self._tools_refresh_thread.is_alive():
                return
            self._tools_stop_event.clear()
            thread = threading.Thread(
                target=self._refresh_loop,
                name=f"mcp-tools-refresh-{self.server_id or 'unknown'}",
                daemon=True,
            )
            self._tools_refresh_thread = thread
            thread.start()

    def _stop_refresh_worker(self) -> None:
        thread = None
        with self._tools_lock:
            thread = self._tools_refresh_thread
            if not thread:
                self._tools_stop_event.set()
                return
            self._tools_stop_event.set()
        if thread.is_alive():
            thread.join(timeout=self.tools_refresh_interval)
        with self._tools_lock:
            self._tools_refresh_thread = None
            self._tools_stop_event = threading.Event()

    def _refresh_loop(self) -> None:
        while not self._tools_stop_event.wait(self.tools_refresh_interval):
            if not self.connected:
                continue
            try:
                self._refresh_tools()
            except Exception as exc:
                logger.debug(f"MCP tool refresh failed: {exc}")

    async def _refresh_tools_async(self) -> bool:
        if not self.session:
            return False
        tools_resp = await _await_or_value(self.session.list_tools(), self.list_timeout_seconds)
        sanitized = self._sanitize_tools(tools_resp)
        if sanitized or self._tool_cache:
            self._apply_tool_cache_update(sanitized)
        return True

    def _refresh_tools(self) -> bool:
        try:
            future = asyncio.run_coroutine_threadsafe(self._refresh_tools_async(), self.event_loop)
            return future.result(timeout=self.list_timeout_seconds + 5)
        except Exception as exc:
            logger.debug(f"Failed to refresh MCP tool cache: {exc}")
            return False

    def _clear_tool_cache(self) -> None:
        with self._tools_lock:
            self._tool_cache = []
            self._tool_cache_timestamp = 0.0
            self.tools = None
        if self.server_id is not None:
            tool_registry.mark_all_unavailable(self.server_id)

    async def _connect_async(self) -> Tuple[bool, Any]:
        if self.connected and self.session:
            return True, self.get_cached_tools()

        if self._manager_task and self._manager_task.done():
            try:
                await self._manager_task
            except Exception:
                pass
            self._manager_task = None

        if self._manager_task:
            if self._connect_ready_future:
                try:
                    return await self._connect_ready_future
                except Exception as exc:
                    logger.error(f"Unexpected connection error during startup wait: {exc}")
                    return False, str(exc)
            await self._manager_task
            if self.connected and self.session:
                return True, self.get_cached_tools()
            return False, self._last_error or "MCP server connection failed"

        loop = asyncio.get_running_loop()
        ready_future: asyncio.Future = loop.create_future()
        disconnect_event = asyncio.Event()
        self._disconnect_event = disconnect_event
        self._connect_ready_future = ready_future
        self._last_error = None
        self._manager_task = loop.create_task(self._run_session(ready_future, disconnect_event))

        try:
            result = await ready_future
        finally:
            self._connect_ready_future = None
        return result

    async def _run_session(self, ready_future: asyncio.Future, disconnect_event: asyncio.Event) -> None:
        stdio_errlog = None
        stack = AsyncExitStack()
        self.exit_stack = stack
        try:
            async with stack:
                if self.transport == "stdio":
                    if not HAS_STDIO:
                        message = "Missing stdio-capable MCP client, run: pip install -U mcp"
                        self._last_error = message
                        if not ready_future.done():
                            ready_future.set_result((False, message))
                        return
                    cfg = self.stdio_config or {}
                    command = cfg.get("command") or sys.executable
                    if str(command).lower() == "python":
                        command = sys.executable
                    args = list(cfg.get("args") or [])
                    env = cfg.get("env") or None
                    cwd = cfg.get("cwd") or None
                    if cwd and not os.path.isabs(cwd):
                        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                        cwd = os.path.abspath(os.path.join(repo_root, cwd))

                    try:
                        log_dir = os.path.join(os.getcwd(), 'logs')
                        os.makedirs(log_dir, exist_ok=True)
                        base = os.path.basename(str(command))
                        log_path = os.path.join(log_dir, f"mcp_stdio_{base}.log")
                        stdio_errlog = open(log_path, 'a', encoding='utf-8')
                    except Exception:
                        stdio_errlog = None

                    self._stdio_errlog_file = stdio_errlog
                    params = StdioServerParameters(command=command, args=args, env=env, cwd=cwd)
                    read_stream, write_stream = await stack.enter_async_context(
                        stdio_client(params, errlog=stdio_errlog or sys.stderr)
                    )
                else:
                    headers = {}
                    if self.api_key:
                        headers['Authorization'] = f'Bearer {self.api_key}'
                    read_stream, write_stream = await stack.enter_async_context(
                        sse_client(self.server_url, headers=headers)
                    )

                self.session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                try:
                    await _await_or_value(getattr(self.session, 'initialize', lambda: None)(), self.init_timeout_seconds)
                except Exception:
                    pass

                tools_resp = await _await_or_value(self.session.list_tools(), self.list_timeout_seconds)
                sanitized_tools = self._sanitize_tools(tools_resp)
                self._apply_tool_cache_update(sanitized_tools)
                self.connected = True
                if not ready_future.done():
                    ready_future.set_result((True, self.get_cached_tools()))

                self._ensure_refresh_worker()

                await disconnect_event.wait()

        except asyncio.TimeoutError as e:
            self._last_error = f"Connection or tool discovery timed out: {e}"
            if not ready_future.done():
                ready_future.set_result((False, self._last_error))
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Error while handling connection lifecycle: {e}")
            if not ready_future.done():
                ready_future.set_result((False, self._last_error))
        finally:
            if stdio_errlog:
                try:
                    stdio_errlog.close()
                except Exception:
                    pass
            if self._stdio_errlog_file and self._stdio_errlog_file is not stdio_errlog:
                try:
                    self._stdio_errlog_file.close()
                except Exception:
                    pass
            self._stdio_errlog_file = None
            self._stop_refresh_worker()
            self.connected = False
            self.session = None
            self._clear_tool_cache()
            if not ready_future.done():
                ready_future.set_result((False, self._last_error or "MCP server connection failed"))
            if self._disconnect_event is disconnect_event:
                self._disconnect_event = None
            self._manager_task = None
            self.exit_stack = None

    def connect(self):
        fut = asyncio.run_coroutine_threadsafe(self._connect_async(), self.event_loop)
        return fut.result(timeout=self.init_timeout_seconds + self.list_timeout_seconds + 10)

    async def _call_tool_async(self, method: str, params=None):
        if not self.connected or not self.session:
            return False, "未连接到MCP服务器"
        try:
            params = params or {}
            result = await _await_or_value(self.session.call_tool(method, params), self.call_timeout_seconds)
            return True, result
        except asyncio.TimeoutError:
            return False, f"调用工具超时({self.call_timeout_seconds}s)"
        except Exception as e:
            logger.exception("调用工具失败异常堆栈")
            return False, f"调用工具失败: {type(e).__name__}: {e}"

    def call_tool(self, method, params=None):
        future = asyncio.run_coroutine_threadsafe(self._call_tool_async(method, params), self.event_loop)
        return future.result(timeout=self.call_timeout_seconds + 5)

    def list_tools(self, refresh: bool = False):
        if not self.connected:
            success, tools = self.connect()
            if not success:
                return []
            return tools or []
        if refresh:
            self._refresh_tools()
        return self.get_cached_tools()

    async def _disconnect_async(self) -> bool:
        task = self._manager_task
        event = self._disconnect_event
        if event and not event.is_set():
            event.set()
        if task:
            try:
                await task
            except Exception as e:
                logger.error(f"Error while closing connection: {e}")
                return False
        return True

    def disconnect(self):
        if not self._manager_task and not self._disconnect_event:
            return True
        try:
            fut = asyncio.run_coroutine_threadsafe(self._disconnect_async(), self.event_loop)
            return fut.result(timeout=10)
        except Exception as e:
            logger.error(f"Error while closing connection: {e}")
            return False


#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import time
import os
import sys
import threading
from contextlib import AsyncExitStack
from typing import Optional, Dict, Any
from mcp import ClientSession
from mcp.client.sse import sse_client
from utils import util

# 尝试导入本地 stdio 传输
try:
    from mcp.client.stdio import stdio_client, StdioServerParameters
    HAS_STDIO = True
except Exception:
    stdio_client = None
    StdioServerParameters = None
    HAS_STDIO = False

# 设置日志记录
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class McpClient:
    """
    MCP客户端类，用于连接MCP服务器并调用其工具
    支持两种传输:
    - SSE: 远程HTTP(S) SSE服务器
    - STDIO: 本地进程通过stdin/stdout通信
    """
    def __init__(self, server_url: Optional[str] = None, api_key: Optional[str] = None,
                 transport: str = "sse", stdio_config: Optional[Dict[str, Any]] = None):
        """
        初始化MCP客户端
        :param server_url: MCP服务器URL（SSE模式必填）
        :param api_key: MCP服务器API密钥（可选，仅SSE）
        :param transport: 传输类型: 'sse' 或 'stdio'
        :param stdio_config: 本地stdio配置，如 {command, args, env, cwd}
        """
        self.server_url = server_url
        self.api_key = api_key
        self.transport = transport or "sse"
        # 如果未显式指定，按server_url推断
        if self.transport not in ("sse", "stdio"):
            self.transport = "stdio" if (server_url and str(server_url).startswith("stdio:")) else "sse"
        self.stdio_config = stdio_config or {}
        self.session = None
        self.tools = None
        self.connected = False
        self.event_loop = None
        self.exit_stack: Optional[AsyncExitStack] = None
        # 超时配置（秒）
        self.init_timeout_seconds = 20
        self.list_timeout_seconds = 20
        self.call_timeout_seconds = 60
        self._ensure_event_loop()
        # stdio 子进程stderr日志文件句柄
        self._stdio_errlog_file = None
        # 后台事件循环线程
        self._loop_thread: Optional[threading.Thread] = None

    def _ensure_event_loop(self):
        """
        启动一个后台事件循环线程，供所有异步操作使用，避免跨线程无事件循环的问题
        """
        if getattr(self, "event_loop", None) and self._loop_thread and self._loop_thread.is_alive():
            return
        # 创建独立事件循环并在后台线程中常驻
        loop = asyncio.new_event_loop()
        self.event_loop = loop

        def _runner():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        t = threading.Thread(target=_runner, name=f"McpClientLoop-{id(self)}", daemon=True)
        t.start()
        self._loop_thread = t

    async def _connect_async(self):
        """
        异步连接到MCP服务器或本地进程
        """
        try:
            # 创建退出栈
            self.exit_stack = AsyncExitStack()

            if self.transport == "stdio":
                if not HAS_STDIO:
                    return False, "未安装或不可用的 MCP stdio 客户端，请确认 mcp 包版本并包含 mcp.client.stdio"
                cfg = self.stdio_config or {}
                command = cfg.get("command")
                if not command:
                    return False, "本地MCP配置缺少 command"
                args = cfg.get("args") or []
                env = cfg.get("env") or None
                cwd = cfg.get("cwd") or None
                logger.info(f"正在通过 STDIO 启动本地MCP: {command} {args} (cwd={cwd})")
                params = StdioServerParameters(
                    command=command,
                    args=list(args or []),
                    env=env,
                    cwd=cwd,
                )
                # 将子进程stderr写入日志文件，便于排查
                try:
                    log_dir = os.path.join(os.getcwd(), 'logs')
                    os.makedirs(log_dir, exist_ok=True)
                    base = os.path.basename(str(command))
                    log_path = os.path.join(log_dir, f"mcp_stdio_{base}.log")
                    self._stdio_errlog_file = open(log_path, 'a', encoding='utf-8')
                except Exception:
                    self._stdio_errlog_file = None
                streams = await self.exit_stack.enter_async_context(
                    stdio_client(params, errlog=self._stdio_errlog_file or sys.stderr)
                )
                logger.info("STDIO 连接已建立")
            else:
                logger.info(f"正在连接到 SSE 服务: {self.server_url}")
                # 准备请求头，如果有API密钥则添加到请求头中
                headers = {}
                if self.api_key:
                    headers['Authorization'] = f'Bearer {self.api_key}'
                # 增加超时设置
                streams = await self.exit_stack.enter_async_context(
                    sse_client(url=self.server_url, timeout=60, headers=headers)  # 增加超时时间到60秒并传递请求头
                )
                logger.info("SSE 连接已建立")

            # 创建会话
            self.session = await self.exit_stack.enter_async_context(ClientSession(*streams))
            try:
                # 为 initialize 增加超时，避免服务器未握手导致阻塞
                await asyncio.wait_for(self.session.initialize(), timeout=20)
            except asyncio.TimeoutError:
                logger.error("会话初始化超时 (initialize) — 请检查本地STDIO服务是否成功启动/输出")
                return False, "会话初始化超时"
            logger.info("会话已创建")

            # 获取工具列表
            logger.info("正在获取工具列表...")
            try:
                # 使用asyncio.wait_for添加超时控制
                tools_response = await asyncio.wait_for(self.session.list_tools(), timeout=self.list_timeout_seconds)
                logger.info(f"可用工具: {tools_response}")

                # 提取工具列表
                if hasattr(tools_response, 'tools') and tools_response.tools:
                    self.tools = tools_response.tools
                else:
                    # 如果返回的是直接的工具列表
                    self.tools = tools_response

                self.connected = True
                return True, self.tools
            except asyncio.TimeoutError:
                logger.error("获取工具列表超时")
                return False, "获取工具列表超时"

        except Exception as e:
            logger.error(f"连接或调用过程中出错: {e}")
            error_msg = str(e)
            # 分类错误信息
            if self.transport == "sse":
                if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                    logger.error("网络连接问题，请检查网络或服务器状态")
                    return False, "网络连接问题，请检查网络或服务器状态"
                elif "auth" in error_msg.lower() or "unauthorized" in error_msg.lower():
                    logger.error("可能存在认证问题，请检查是否需要提供 API 密钥")
                    return False, "认证问题，请检查是否需要提供 API 密钥"
                elif "sse" in error_msg.lower() or "stream" in error_msg.lower():
                    logger.error("SSE流处理错误，可能是服务器提前关闭了连接")
                    return False, "SSE流处理错误，可能是服务器提前关闭了连接"
            else:
                if "command" in error_msg.lower() or "not found" in error_msg.lower():
                    return False, "本地MCP命令启动失败，请检查 command/args/cwd 是否正确"
            return False, f"连接错误: {error_msg}"

    def connect(self):
        """
        连接到MCP服务器（提交到后台事件循环）
        :return: (是否成功, 工具列表或错误信息)
        """
        fut = asyncio.run_coroutine_threadsafe(self._connect_async(), self.event_loop)
        return fut.result(timeout=self.init_timeout_seconds + self.list_timeout_seconds + 10)

    async def _call_tool_async(self, method, params=None):
        """
        异步调用MCP工具
        :param method: 方法名
        :param params: 参数字典
        :return: 调用结果
        """
        if not self.connected or not self.session:
            return False, "未连接到MCP服务器"

        try:
            if params is None:
                params = {}

            logger.info(f"调用工具: {method}, 参数: {params}")
            result = await asyncio.wait_for(self.session.call_tool(method, params), timeout=self.call_timeout_seconds)
            logger.info(f"调用结果: {result}")
            return True, result
        except asyncio.TimeoutError:
            return False, f"调用工具超时({self.call_timeout_seconds}s)"
        except Exception as e:
            # 提供更可读的错误类型，并在日志中打印完整异常，便于排查
            logger.exception("调用工具失败异常堆栈")
            msg = str(e)
            if not msg:
                msg = repr(e)
            return False, f"调用工具失败: {type(e).__name__}: {msg}"

    def call_tool(self, method, params=None):
        """
        调用MCP工具（提交到后台事件循环）
        :param method: 方法名
        :param params: 参数字典
        :return: (是否成功, 结果或错误信息)
        """
        try:
            future = asyncio.run_coroutine_threadsafe(self._call_tool_async(method, params), self.event_loop)
            return future.result(timeout=self.call_timeout_seconds + 5)
        except Exception as e:
            util.log(1, f"调用MCP工具时出错: {str(e)}")
            return False, f"调用工具失败: {str(e)}"

    def list_tools(self):
        """
        获取可用工具列表
        :return: 工具列表
        """
        if not self.connected:
            success, result = self.connect()
            if not success:
                return []
        return self.tools or []

    def disconnect(self):
        """
        断开与MCP服务器的连接
        """
        if self.connected and self.exit_stack:
            try:
                # 在后台事件循环中关闭资源
                try:
                    if self.exit_stack:
                        fut = asyncio.run_coroutine_threadsafe(self.exit_stack.aclose(), self.event_loop)
                        fut.result(timeout=10)
                finally:
                    self.connected = False
                    self.session = None
                    # 关闭子进程stderr日志文件
                    try:
                        if self._stdio_errlog_file:
                            self._stdio_errlog_file.close()
                            self._stdio_errlog_file = None
                    except Exception:
                        pass
                logger.info("已断开与MCP服务器的连接")
                return True
            except Exception as e:
                logger.error(f"断开连接时出错: {e}")
                return False
        return True  # 如果本来就没连接，也返回成功

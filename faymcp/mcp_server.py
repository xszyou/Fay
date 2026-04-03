#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fay broadcast MCP server (SSE transport).

暴露 `broadcast_message` 工具，将文本/音频透传到 Fay 的 `/transparent-pass`。

环境变量：
- FAY_BROADCAST_API    默认 http://127.0.0.1:5000/transparent-pass
- FAY_BROADCAST_USER   默认 User
- FAY_BROADCAST_TIMEOUT 默认 10
- FAY_MCP_SSE_HOST     默认 0.0.0.0
- FAY_MCP_SSE_PORT     默认 8765
- FAY_MCP_SSE_PATH     SSE 路径（默认 /sse）
- FAY_MCP_MSG_PATH     消息 POST 路径（默认 /messages）
"""

import asyncio
import logging
import os
import sys
import json
from typing import Any, Dict, Tuple, List, Optional

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from mcp.server.sse import SseServerTransport
    from faymcp import tool_registry
    from faymcp import mcp_service
except ImportError:
    print("缺少 mcp 库，请先安装：pip install mcp", file=sys.stderr)
    sys.exit(1)

try:
    from starlette.applications import Starlette
    from starlette.datastructures import MutableHeaders
    from starlette.routing import Mount, Route
    from starlette.types import ASGIApp, Message, Receive, Scope, Send
except ImportError:
    print("缺少 starlette，请先安装：pip install starlette sse-starlette", file=sys.stderr)
    sys.exit(1)

try:
    import uvicorn
except ImportError:
    print("缺少 uvicorn，请先安装：pip install uvicorn", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("缺少 requests，请先安装：pip install requests", file=sys.stderr)
    sys.exit(1)


log = logging.getLogger("fay_mcp_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

SERVER_NAME = "fay_broadcast"

DEFAULT_API_URL = os.environ.get("FAY_BROADCAST_API", "http://127.0.0.1:5000/transparent-pass")
DEFAULT_USER = os.environ.get("FAY_BROADCAST_USER", "User")
DEFAULT_SPEAKER = os.environ.get("FAY_BROADCAST_SPEAKER", "\u5e7f\u64ad\u6d88\u606f")
REQUEST_TIMEOUT = float(os.environ.get("FAY_BROADCAST_TIMEOUT", "10"))

HOST = os.environ.get("FAY_MCP_SSE_HOST", "0.0.0.0")
PORT = int(os.environ.get("FAY_MCP_SSE_PORT", "8765"))
SSE_PATH = os.environ.get("FAY_MCP_SSE_PATH", "/sse")
MSG_PATH = os.environ.get("FAY_MCP_MSG_PATH", "/messages")

server = None  # Removed global singleton
sse_transport = SseServerTransport(MSG_PATH)

# 聚合工具索引：namespaced_tool_name -> (server_id, tool_name)
_aggregated_index: Dict[str, Tuple[int, str]] = {}


def _text_content(text: str) -> TextContent:
    try:
        return TextContent(type="text", text=text)
    except Exception:
        return {"type": "text", "text": text}  # type: ignore[return-value]


TOOLS: list[Tool] = [
    Tool(
        name="broadcast_message",
        description="通过 Fay 的 /transparent-pass 透传文本/音频。",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要广播的文本（audio_url为空时必填）"},
                "audio_url": {"type": "string", "description": "可选音频 URL"},
                "user": {"type": "string", "description": "用户标识名称，默认 FAY_BROADCAST_USER 或 User"},
                "speaker": {
                    "type": "string",
                    "description": "发言人显示名，输出为\"{speaker}说：{text}\"",
                },
                "queue": {"type": "boolean", "description": "是否走队列播放，默认 false"},
                "queue_playback": {"type": "boolean", "description": "兼容参数，等同 queue"},
                "enqueue": {"type": "boolean", "description": "兼容参数，等同 queue"},
                "mode": {"type": "string", "description": "兼容参数，值为 queue 时启用队列播放"},
            },
            "required": [],
        },
    )
]

async def _handle_list_tools() -> list[Tool]:
    # 本地广播工具 + Fay 当前在线 MCP 工具的聚合视图（namespaced）
    aggregated = []
    try:
        aggregated = _build_aggregated_tools()
    except Exception as e:
        log.warning(f"Failed to build aggregated tools: {e}")
    return TOOLS + aggregated



def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v == "":
            return False
        return v in {"1", "true", "yes", "on", "y", "queue"}
    return bool(value)


def _parse_arguments(arguments: Dict[str, Any]) -> Tuple[str, str, str, str, bool]:
    text = str(arguments.get("text", "") or "").strip()
    audio_url = str(arguments.get("audio_url", "") or "").strip()
    user = str(arguments.get("user", "") or "").strip() or DEFAULT_USER
    speaker = str(arguments.get("speaker", "") or "").strip() or DEFAULT_SPEAKER
    if "queue" in arguments:
        queue = _as_bool(arguments.get("queue"))
    elif "queue_playback" in arguments:
        queue = _as_bool(arguments.get("queue_playback"))
    elif "enqueue" in arguments:
        queue = _as_bool(arguments.get("enqueue"))
    elif "mode" in arguments:
        queue = str(arguments.get("mode", "") or "").strip().lower() == "queue"
    else:
        queue = False
    return text, audio_url, user, speaker, queue
def _build_aggregated_tools() -> List[Tool]:
    """
    将 Fay 已连接的 MCP 工具聚合，对外暴露为 namespaced 名称：
    <server_id>:<tool_name>
    """
    tools: List[Tool] = []
    _aggregated_index.clear()

    server_name_map = {s.get("id"): s.get("name", f"Server{s.get('id')}") for s in mcp_service.mcp_servers or []}

    for entry in tool_registry.get_enabled_tools():
        server_id = entry.get("server_id")
        tool_name = entry.get("name")
        if server_id is None or not tool_name:
            continue
        agg_name = f"{server_id}:{tool_name}"
        desc = entry.get("description", "")
        server_label = server_name_map.get(server_id, f"Server {server_id}")
        agg_desc = f"{desc} [via {server_label}]"
        input_schema = entry.get("inputSchema") or {}
        tool = Tool(
            name=agg_name,
            description=agg_desc,
            inputSchema=input_schema if isinstance(input_schema, dict) else {},
        )
        tools.append(tool)
        _aggregated_index[agg_name] = (server_id, tool_name)

    return tools


async def _send_broadcast(payload: Dict[str, Any]) -> Tuple[bool, str]:
    def _post() -> Tuple[bool, str]:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        resp = requests.post(
            DEFAULT_API_URL,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=REQUEST_TIMEOUT,
        )
        try:
            data = resp.json()
        except Exception:
            data = None

        if resp.ok:
            if isinstance(data, dict):
                msg = data.get("message") or data.get("msg") or ""
                code = data.get("code")
                if isinstance(code, int) and code >= 400:
                    return False, msg or f"透传失败，HTTP码 {code}"
                return True, msg or "已发送透传请求。"
            return True, "已发送透传请求。"

        err_detail = ""
        if isinstance(data, dict):
            err_detail = data.get("message") or data.get("error") or data.get("msg") or ""
        if not err_detail:
            err_detail = resp.text
        return False, f"HTTP {resp.status_code}: {err_detail}"

    try:
        return await asyncio.to_thread(_post)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def _handle_call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    # 本地广播
    if name == "broadcast_message":
        text, audio_url, user, speaker, queue = _parse_arguments(arguments or {})
        if not text and not audio_url:
            return [_text_content("text 或 audio_url 至少需提供一个。")]

        payload: Dict[str, Any] = {"user": user}
        if text:
            payload["text"] = f"{speaker}\u8bf4\uff1a{text}"
        if audio_url:
            payload["audio"] = audio_url
        if queue:
            payload["queue"] = True
            payload["queue_playback"] = True
            payload["mode"] = "queue"

        ok, message = await _send_broadcast(payload)
        prefix = "成功" if ok else "失败"
        return [_text_content(f"{prefix}: {message}")]

    target = _aggregated_index.get(name)
    if not target:
        return [_text_content(f"未知工具: {name}")]

    server_id, tool_name = target
    try:
        success, result = await asyncio.to_thread(mcp_service.call_mcp_tool, server_id, tool_name, arguments or {})
        if not success:
            return [_text_content(f"error: {result}")]
        return _normalize_result(result)
    except Exception as e:
        return [_text_content(f"error: {type(e).__name__}: {e}")]


def _normalize_result(result: Any) -> List[TextContent]:
    """
    将上游返回的任意对象转换为 MCP 文本内容列表。
    """
    # 如果已经是 TextContent 或列表，直接返回
    try:
        from mcp.types import TextContent
        if isinstance(result, TextContent):
            return [result]
    except Exception:
        pass

    if isinstance(result, list):
        contents: List[TextContent] = []
        for item in result:
            try:
                if hasattr(item, "type") and getattr(item, "type", "") == "text" and hasattr(item, "text"):
                    contents.append(item)
                    continue
            except Exception:
                pass
            try:
                if isinstance(item, dict) and item.get("type") == "text":
                    contents.append(TextContent(type="text", text=str(item.get("text", ""))))  # type: ignore
                    continue
            except Exception:
                pass
            contents.append(_text_content(str(item)))
        return contents

    return [_text_content(str(result))]


class SseEndpoint:
    """ASGI endpoint for MCP SSE connections.

    `connect_sse()` writes the response directly to the ASGI send channel, so
    this route must not return an extra Starlette `Response`.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        local_server = Server(SERVER_NAME)
        local_server.list_tools()(_handle_list_tools)
        local_server.call_tool()(_handle_call_tool)

        async with sse_transport.connect_sse(scope, receive, send) as (read_stream, write_stream):
            await local_server.run(read_stream, write_stream, local_server.create_initialization_options())


class Utf8CharsetMiddleware:
    """Ensure text responses declare UTF-8 without buffering streaming bodies."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_charset(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                content_type = headers.get("content-type", "")
                if content_type.startswith("text/") and "charset=" not in content_type.lower():
                    headers["content-type"] = f"{content_type}; charset=utf-8"
            await send(message)

        await self.app(scope, receive, send_with_charset)


routes = [
    Route(SSE_PATH, SseEndpoint(), methods=["GET"]),
    Mount(MSG_PATH, app=sse_transport.handle_post_message),
]

app = Utf8CharsetMiddleware(Starlette(routes=routes))


def main():
    log.info(f"SSE MCP server started at http://{HOST}:{PORT}{SSE_PATH}")
    log.info(f"Message endpoint mounted at {MSG_PATH}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

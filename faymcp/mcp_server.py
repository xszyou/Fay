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
from typing import Any, Dict, Tuple

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from mcp.server.sse import SseServerTransport
except ImportError:
    print("缺少 mcp 库，请先安装：pip install mcp", file=sys.stderr)
    sys.exit(1)

try:
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Mount, Route
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
REQUEST_TIMEOUT = float(os.environ.get("FAY_BROADCAST_TIMEOUT", "10"))

HOST = os.environ.get("FAY_MCP_SSE_HOST", "0.0.0.0")
PORT = int(os.environ.get("FAY_MCP_SSE_PORT", "8765"))
SSE_PATH = os.environ.get("FAY_MCP_SSE_PATH", "/sse")
MSG_PATH = os.environ.get("FAY_MCP_MSG_PATH", "/messages")

server = Server(SERVER_NAME)
sse_transport = SseServerTransport(MSG_PATH)


def _text_content(text: str) -> TextContent:
    try:
        return TextContent(type="text", text=text)
    except Exception:
        return {"type": "text", "text": text}  # type: ignore[return-value]


TOOLS: list[Tool] = [
    Tool(
        name="broadcast_message",
        description="通过 Fay 的 /transparent-pass 广播文本/音频（SSE 服务器）。",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要广播的文本（audio_url为空时必填）"},
                "audio_url": {"type": "string", "description": "可选音频 URL"},
                "user": {"type": "string", "description": "目标用户名，默认 FAY_BROADCAST_USER 或 User"},
            },
            "required": [],
        },
    )
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


def _parse_arguments(arguments: Dict[str, Any]) -> Tuple[str, str, str]:
    text = str(arguments.get("text", "") or "").strip()
    audio_url = str(arguments.get("audio_url", "") or "").strip()
    user = str(arguments.get("user", "") or "").strip() or DEFAULT_USER
    return text, audio_url, user


async def _send_broadcast(payload: Dict[str, Any]) -> Tuple[bool, str]:
    def _post() -> Tuple[bool, str]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
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
                    return False, msg or f"Broadcast failed with code {code}"
                return True, msg or "Broadcast sent via Fay."
            return True, "Broadcast sent via Fay."

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


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    if name != "broadcast_message":
        return [_text_content(f"Unknown tool: {name}")]

    text, audio_url, user = _parse_arguments(arguments or {})
    if not text and not audio_url:
        return [_text_content("Either 'text' or 'audio_url' must be provided.")]

    payload: Dict[str, Any] = {"user": user}
    if text:
        payload["text"] = text
    if audio_url:
        payload["audio"] = audio_url

    ok, message = await _send_broadcast(payload)
    prefix = "success" if ok else "error"
    return [_text_content(f"{prefix}: {message}")]


async def sse_endpoint(request):
    async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
    # 客户端断开时返回空响应，避免 NoneType 问题
    return Response()


routes = [
    Route(SSE_PATH, sse_endpoint, methods=["GET"]),
    Mount(MSG_PATH, app=sse_transport.handle_post_message),
]

app = Starlette(routes=routes)


def main():
    log.info(f"SSE MCP server started at http://{HOST}:{PORT}{SSE_PATH}")
    log.info(f"Message endpoint mounted at {MSG_PATH}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

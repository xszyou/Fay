#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本文件是一个最小可用的 MCP STDIO（本地）服务器示例。

运行:
  python test/mcp_stdio_example.py

在 UI 中添加本地 MCP 服务器时:
  transport: stdio
  command: python
  args: ["test/mcp_stdio_example.py"]
  cwd: 项目根目录 (可选)

提供的工具:
  - ping() -> "pong"
  - echo(text: str)
  - upper(text: str)
  - add(a: int, b: int)
  - now(fmt: str = "%Y-%m-%d %H:%M:%S") -> 当前时间格式化

注意: 返回内容遵循 MCP 协议，使用 TextContent 包装文本。
"""

import asyncio
import os
import sys
from datetime import datetime

try:
    # 核心 MCP 服务器 API（低层）
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
except Exception as e:
    print("[mcp_stdio_example] 请先安装 mcp 包: pip install mcp", file=sys.stderr)
    raise


server = Server("Fay STDIO Example")

# --- 定义工具清单（低层 API 需要手动注册 list_tools 和 call_tool）---
TOOLS: list[types.Tool] = [
    types.Tool(
        name="ping",
        description="连通性检查：若提供 host 则执行系统 ping，否则返回 pong",
        inputSchema={
            "type": "object",
            "properties": {"host": {"type": "string"}},
            "required": []
        }
    ),
    types.Tool(
        name="echo",
        description="返回相同文本",
        inputSchema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"]
        }
    ),
    types.Tool(
        name="upper",
        description="将文本转为大写",
        inputSchema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"]
        }
    ),
    types.Tool(
        name="add",
        description="两个整数求和",
        inputSchema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"]
        }
    ),
    types.Tool(
        name="now",
        description="返回当前时间，默认格式为 %Y-%m-%d %H:%M:%S，可通过 fmt 指定",
        inputSchema={
            "type": "object",
            "properties": {"fmt": {"type": "string"}},
            "required": []
        }
    ),
]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        match name:
            case "ping":
                host = (arguments or {}).get("host")
                if host:
                    # 在不同平台调用系统 ping，避免 Windows 下 shlex.quote 与 shell=True 的兼容问题
                    import platform, subprocess
                    is_win = platform.system().lower().startswith("win")
                    cmd = ["ping", ("-n" if is_win else "-c"), "2", str(host)]
                    try:
                        out = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=8)
                        ok = (out.returncode == 0)
                        stdout = out.stdout or ""
                        # 截取最后几行摘要
                        lines = [line for line in stdout.strip().splitlines() if line.strip()]
                        summary = lines[-6:] if lines else []
                        text = ("SUCCESS\n" if ok else "FAIL\n") + "\n".join(summary)
                    except Exception as e:
                        text = f"执行 ping 出错: {type(e).__name__}: {e}"
                    return [types.TextContent(type="text", text=text)]
                else:
                    return [types.TextContent(type="text", text="pong")]
            case "echo":
                return [types.TextContent(type="text", text=str(arguments.get("text", "")))]
            case "upper":
                return [types.TextContent(type="text", text=str(arguments.get("text", "")).upper())]
            case "add":
                a = int(arguments.get("a", 0))
                b = int(arguments.get("b", 0))
                return [types.TextContent(type="text", text=str(a + b))]
            case "now":
                fmt = arguments.get("fmt") or "%Y-%m-%d %H:%M:%S"
                try:
                    txt = datetime.now().strftime(fmt)
                except Exception:
                    txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return [types.TextContent(type="text", text=txt)]
            case _:
                return [types.TextContent(type="text", text=f"未知工具: {name}")]
    except Exception as e:
        # 返回错误信息（isError将由框架根据异常处理）
        return [types.TextContent(type="text", text=f"调用异常: {e}")]


async def main() -> None:
    # 通过 STDIO 暴露 MCP Server
    async with stdio_server() as (read_stream, write_stream):
        # 显式开启 tools 能力，避免部分版本下未注册导致 list_tools/call_tool 问题
        init_opts = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_opts)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


#!/usr/bin/env python3
"""
TwelveLabs Pegasus 视频理解 MCP server.

通过 TwelveLabs Pegasus 模型对视频进行理解/分析，让 Fay 的 agent 能够"看懂"视频内容
（总结、问答、提取要点等），返回自然语言文本。

Tools:
- analyze_video: 对一个视频（公开 URL 或已上传的 asset_id）按给定提示词进行分析，返回文本结果。

凭据：从环境变量 TWELVELABS_API_KEY 读取（绝不在代码中硬编码）。
未配置 API key 时该服务器不会启动，因此对未配置者无任何影响（完全可选）。
免费 API key 可在 https://twelvelabs.io 申请，有较慷慨的免费额度。
"""

import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

try:
    from twelvelabs import TwelveLabs
    from twelvelabs.types import VideoContext_AssetId, VideoContext_Url
except ImportError:
    print(
        "twelvelabs SDK not installed. Please run: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    import mcp.server.stdio
except ImportError:
    print("MCP library not installed. Please run: pip install mcp", file=sys.stderr)
    sys.exit(1)


# 配置（全部来自环境变量，便于在 Fay 的 MCP 管理页面里配置）
API_KEY = os.getenv("TWELVELABS_API_KEY", "").strip()
DEFAULT_MODEL = os.getenv("TWELVELABS_MODEL", "pegasus1.5").strip() or "pegasus1.5"
# Pegasus 1.5 要求 max_tokens 在 512~65536 之间
DEFAULT_MAX_TOKENS = int(os.getenv("TWELVELABS_MAX_TOKENS", "2048"))

if not API_KEY:
    print(
        "TWELVELABS_API_KEY is not set. Get a free key at https://twelvelabs.io and "
        "configure it in the MCP server environment.",
        file=sys.stderr,
    )
    sys.exit(1)

server = Server("twelvelabs_video")

_client: Optional[TwelveLabs] = None


def _get_client() -> TwelveLabs:
    """惰性创建 TwelveLabs 客户端，复用单例。"""
    global _client
    if _client is None:
        _client = TwelveLabs(api_key=API_KEY)
    return _client


def _text_content(text: str):
    try:
        return TextContent(type="text", text=text)
    except Exception:
        return {"type": "text", "text": text}


def _build_video_context(video_url: str, asset_id: str):
    """根据传入参数构造 Pegasus 的视频输入。

    注意：Pegasus 1.5 不接受裸 video_id，只能用公开 URL 或已上传的 asset_id。
    """
    url = (video_url or "").strip()
    asset = (asset_id or "").strip()
    if url and asset:
        raise ValueError("video_url 与 asset_id 只能二选一。")
    if url:
        return VideoContext_Url(url=url)
    if asset:
        return VideoContext_AssetId(asset_id=asset)
    raise ValueError("必须提供 video_url 或 asset_id 其中之一。")


def analyze_video(
    prompt: str,
    video_url: str = "",
    asset_id: str = "",
    max_tokens: Optional[int] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    model_name: Optional[str] = None,
) -> str:
    """调用 Pegasus 分析视频并返回文本结果。"""
    if not prompt or not str(prompt).strip():
        raise ValueError("prompt（提示词）不能为空。")

    video = _build_video_context(video_url, asset_id)
    tokens = max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS
    try:
        tokens = int(tokens)
    except Exception:
        tokens = DEFAULT_MAX_TOKENS
    # Pegasus 1.5 要求 max_tokens >= 512
    tokens = max(512, tokens)

    # 可选时间窗口（Pegasus 1.5），用于只分析视频的一段；窗口需 >= 4 秒。
    kwargs: Dict[str, Any] = {}
    if start_time is not None:
        kwargs["start_time"] = float(start_time)
    if end_time is not None:
        kwargs["end_time"] = float(end_time)

    client = _get_client()
    response = client.analyze(
        model_name=(model_name or DEFAULT_MODEL),
        video=video,
        prompt=str(prompt).strip(),
        max_tokens=tokens,
        **kwargs,
    )
    return getattr(response, "data", "") or ""


TOOLS: List[Tool] = [
    Tool(
        name="analyze_video",
        description=(
            "Understand/analyse a video with TwelveLabs Pegasus and return text "
            "(summary, Q&A, key points, etc.). Provide a public video URL or an "
            "uploaded asset_id (a bare video_id is NOT accepted by Pegasus 1.5). "
            "Public URLs are supported up to ~4GB; local-file uploads via asset are "
            "capped at 200MB. The analysed window must be at least 4 seconds."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Instruction guiding the analysis, e.g. '用一句话总结这个视频' or 'What objects appear?'.",
                },
                "video_url": {
                    "type": "string",
                    "description": "Direct http(s) URL to a video file (mutually exclusive with asset_id).",
                },
                "asset_id": {
                    "type": "string",
                    "description": "ID of a video asset already uploaded to TwelveLabs (mutually exclusive with video_url).",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Max output tokens (Pegasus 1.5 minimum 512). Defaults to TWELVELABS_MAX_TOKENS.",
                },
                "start_time": {
                    "type": "number",
                    "description": "Optional analysis window start in seconds (Pegasus 1.5). Window must be >= 4s.",
                },
                "end_time": {
                    "type": "number",
                    "description": "Optional analysis window end in seconds (Pegasus 1.5). Window must be >= 4s.",
                },
            },
            "required": ["prompt"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> List[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: Optional[Dict[str, Any]]) -> List[Any]:
    args = arguments or {}
    try:
        if name == "analyze_video":
            prompt = args.get("prompt", "")
            video_url = args.get("video_url", "") or ""
            asset_id = args.get("asset_id", "") or ""
            max_tokens = args.get("max_tokens")
            start_time = args.get("start_time")
            end_time = args.get("end_time")
            # 网络/分析为阻塞调用，放到线程里避免卡住事件循环
            text = await asyncio.to_thread(
                analyze_video,
                prompt,
                video_url,
                asset_id,
                max_tokens,
                start_time,
                end_time,
            )
            return [_text_content(text or "（模型未返回内容）")]

        return [_text_content(f"Unknown tool: {name}")]

    except Exception as exc:
        return [_text_content(f"Error running tool {name}: {exc}")]


async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        init_opts = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_opts)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

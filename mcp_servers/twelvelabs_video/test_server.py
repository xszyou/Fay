#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TwelveLabs Pegasus 视频理解 MCP server 的轻量自检。

无网络单元测试（始终运行）：校验视频输入参数构造与互斥校验。
联网实测（仅在设置了 TWELVELABS_API_KEY 时运行）：用一个公开视频 URL 真正调用
Pegasus，断言返回非空文本。

运行：
  python mcp_servers/twelvelabs_video/test_server.py
"""

import importlib
import os
import sys

# server.py 在导入时要求存在 TWELVELABS_API_KEY，这里给无网络单测兜底一个占位值。
HAS_REAL_KEY = bool(os.getenv("TWELVELABS_API_KEY", "").strip())
if not HAS_REAL_KEY:
    os.environ["TWELVELABS_API_KEY"] = "test-placeholder-key"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
server = importlib.import_module("server")

# 一个公开的 720p 视频（>=4s，分辨率合规），用于联网实测。
SAMPLE_VIDEO_URL = (
    "https://archive.org/download/BigBuckBunny_124/Content/"
    "big_buck_bunny_720p_surround.mp4"
)


def test_build_video_context_url():
    ctx = server._build_video_context("https://example.com/a.mp4", "")
    assert ctx.url == "https://example.com/a.mp4", ctx


def test_build_video_context_asset():
    ctx = server._build_video_context("", "asset_123")
    assert ctx.asset_id == "asset_123", ctx


def test_build_video_context_requires_one_source():
    for bad in [("", ""), ("https://x/a.mp4", "asset_1")]:
        try:
            server._build_video_context(*bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_analyze_requires_prompt():
    try:
        server.analyze_video("", video_url="https://example.com/a.mp4")
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty prompt")


def test_live_analyze():
    """仅在配置了真实 API key 时运行。"""
    if not HAS_REAL_KEY:
        print("SKIP live test (TWELVELABS_API_KEY not set)")
        return
    text = server.analyze_video(
        "Describe what happens in this video in one sentence.",
        video_url=SAMPLE_VIDEO_URL,
        max_tokens=512,
        start_time=0,
        end_time=10,
    )
    assert isinstance(text, str) and text.strip(), repr(text)
    print("live analyze ->", text[:160])


if __name__ == "__main__":
    test_build_video_context_url()
    test_build_video_context_asset()
    test_build_video_context_requires_one_source()
    test_analyze_requires_prompt()
    print("unit tests passed")
    test_live_analyze()
    print("OK")

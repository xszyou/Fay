#!/usr/bin/env python3
"""
Window Capture MCP server.

Tools:
- list_windows: enumerate top-level windows with optional keyword filtering.
- capture_window: take a PNG screenshot of a specific window by title keyword or handle.

Only Windows is supported because the capture path relies on Win32 APIs and Pillow's ImageGrab.
"""

import asyncio
import ctypes
from ctypes import wintypes
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import ImageGrab
except ImportError:
    print("Pillow not installed. Please run: pip install Pillow", file=sys.stderr)
    sys.exit(1)

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    import mcp.server.stdio
except ImportError:
    print("MCP library not installed. Please run: pip install mcp", file=sys.stderr)
    sys.exit(1)


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SAVE_DIR = os.path.join(PROJECT_ROOT, "cache_data", "window_captures")
os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)

if os.name != "nt":
    print("window_capture MCP server currently supports Windows only.", file=sys.stderr)

server = Server("window_capture")

user32 = ctypes.windll.user32
SW_RESTORE = 9

try:
    user32.SetProcessDPIAware()
except Exception:
    pass


@dataclass
class WindowInfo:
    handle: int
    title: str
    cls: str
    rect: Tuple[int, int, int, int]
    visible: bool
    minimized: bool

    def to_dict(self) -> Dict[str, Any]:
        left, top, right, bottom = self.rect
        return {
            "title": self.title,
            "class": self.cls,
            "handle": self.handle,
            "handle_hex": hex(self.handle),
            "visible": self.visible,
            "minimized": self.minimized,
            "rect": {"left": left, "top": top, "right": right, "bottom": bottom},
            "size": {"width": max(0, right - left), "height": max(0, bottom - top)},
        }


class WindowCaptureError(Exception):
    pass


def _text_content(text: str):
    try:
        return TextContent(type="text", text=text)
    except Exception:
        return {"type": "text", "text": text}


def _sanitize_filename(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in (" ", "_", "-"))
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned or "window"


def _enum_windows(keyword: Optional[str] = None, include_hidden: bool = False, limit: int = 30) -> List[WindowInfo]:
    if os.name != "nt":
        raise WindowCaptureError("Window enumeration is only supported on Windows.")

    results: List[WindowInfo] = []
    keyword_l = keyword.lower() if keyword else None

    def callback(hwnd, _lparam):
        if not user32.IsWindow(hwnd):
            return True
        if not include_hidden and not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        title_buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buf, length + 1)
        title = title_buf.value.strip()
        if not title:
            return True

        if keyword_l and keyword_l not in title.lower():
            return True

        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 255)
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True

        info = WindowInfo(
            handle=int(hwnd),
            title=title,
            cls=class_buf.value,
            rect=(rect.left, rect.top, rect.right, rect.bottom),
            visible=bool(user32.IsWindowVisible(hwnd)),
            minimized=bool(user32.IsIconic(hwnd)),
        )
        results.append(info)
        if limit > 0 and len(results) >= limit:
            return False
        return True

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(enum_proc(callback), 0)

    results.sort(key=lambda w: w.title.lower())
    return results


def _parse_handle(value: str) -> Optional[int]:
    text = value.strip().lower()
    if text.startswith("0x"):
        try:
            return int(text, 16)
        except ValueError:
            return None
    if text.isdigit():
        try:
            return int(text)
        except ValueError:
            return None
    return None


def _resolve_window(query: str, include_hidden: bool = False) -> WindowInfo:
    if not query or not str(query).strip():
        raise WindowCaptureError("Window identifier is required.")

    handle_candidate = _parse_handle(str(query))
    if handle_candidate is not None:
        windows = _enum_windows(None, include_hidden=include_hidden, limit=0)
        for win in windows:
            if win.handle == handle_candidate:
                return win
        raise WindowCaptureError(f"Window handle {handle_candidate} not found.")

    matches = _enum_windows(query, include_hidden=include_hidden, limit=50)
    if not matches:
        raise WindowCaptureError(f"No window matched keyword '{query}'.")

    exact = [w for w in matches if w.title.lower() == query.lower()]
    if len(exact) == 1:
        return exact[0]
    if len(matches) == 1:
        return matches[0]

    names = "; ".join(w.title for w in matches[:6])
    raise WindowCaptureError(f"Multiple windows matched. Please be more specific. Candidates: {names}")


def _get_foreground_window() -> int:
    """获取当前前台窗口句柄"""
    try:
        return user32.GetForegroundWindow()
    except Exception:
        return 0


def _activate_window(hwnd: int) -> bool:
    """激活指定窗口，返回是否成功"""
    try:
        # 如果窗口最小化，先恢复
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.1)

        # 尝试多种方式激活窗口
        # 方法1: 使用 SetForegroundWindow
        result = user32.SetForegroundWindow(hwnd)

        if not result:
            # 方法2: 使用 keybd_event 模拟 Alt 键来允许切换前台
            ALT_KEY = 0x12
            KEYEVENTF_EXTENDEDKEY = 0x0001
            KEYEVENTF_KEYUP = 0x0002
            user32.keybd_event(ALT_KEY, 0, KEYEVENTF_EXTENDEDKEY, 0)
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(ALT_KEY, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

        time.sleep(0.3)  # 等待窗口完全显示
        return True
    except Exception:
        return False


def _get_window_rect(hwnd: int) -> Tuple[int, int, int, int]:
    """获取窗口的最新坐标"""
    rect = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (rect.left, rect.top, rect.right, rect.bottom)
    return (0, 0, 0, 0)


def capture_window(query: str, save_dir: Optional[str] = None, include_hidden: bool = False):
    if os.name != "nt":
        raise WindowCaptureError("Window capture is only supported on Windows.")

    window = _resolve_window(query, include_hidden=include_hidden)

    # 记录当前前台窗口，截图后恢复
    original_foreground = _get_foreground_window()

    try:
        # 激活目标窗口
        _activate_window(window.handle)

        # 激活后重新获取窗口坐标（窗口位置可能在激活/恢复后发生变化）
        left, top, right, bottom = _get_window_rect(window.handle)
        if right - left <= 0 or bottom - top <= 0:
            raise WindowCaptureError("Target window has zero area.")

        # 更新 window 对象的 rect 以便返回正确信息
        window.rect = (left, top, right, bottom)

        try:
            img = ImageGrab.grab(bbox=(left, top, right, bottom))
        except Exception as exc:
            raise WindowCaptureError(f"ImageGrab failed: {exc}") from exc

        save_dir = save_dir or DEFAULT_SAVE_DIR
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{_sanitize_filename(window.title)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_path = os.path.abspath(os.path.join(save_dir, filename))

        img.save(save_path, format="PNG")

        return save_path

    finally:
        # 恢复原来的前台窗口
        if original_foreground and original_foreground != window.handle:
            time.sleep(0.1)
            _activate_window(original_foreground)


TOOLS: List[Tool] = [
    Tool(
        name="list_windows",
        description="List visible top-level windows. Supports keyword filter and optional hidden windows.",
        inputSchema={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Substring to match in the window title (case-insensitive)."},
                "include_hidden": {"type": "boolean", "description": "Include hidden/minimized windows."},
                "limit": {"type": "integer", "description": "Max number of windows to return (0 means no limit)."},
            },
            "required": [],
        },
    ),
    Tool(
        name="capture_window",
        description="Capture a PNG screenshot of a specific window by title keyword or numeric/hex handle; returns local file path.",
        inputSchema={
            "type": "object",
            "properties": {
                "window": {
                    "type": "string",
                    "description": "Title keyword or window handle (e.g. 'Notepad', '197324', or '0x2ff3e').",
                },
                "include_hidden": {"type": "boolean", "description": "Allow capturing hidden/minimized windows."},
                "save_dir": {
                    "type": "string",
                    "description": f"Optional folder to save the PNG. Default: {DEFAULT_SAVE_DIR}",
                },
            },
            "required": ["window"],
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
        if name == "list_windows":
            keyword = args.get("keyword")
            include_hidden = bool(args.get("include_hidden", False))
            limit_raw = args.get("limit", 20)
            try:
                limit_val = int(limit_raw)
            except Exception:
                limit_val = 20
            limit_val = max(0, min(limit_val, 200))

            windows = _enum_windows(keyword, include_hidden=include_hidden, limit=limit_val or 0)
            payload = {
                "count": len(windows),
                "keyword": keyword or "",
                "include_hidden": include_hidden,
                "windows": [w.to_dict() for w in windows],
            }
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            return [_text_content(text)]

        if name == "capture_window":
            query = args.get("window") or args.get("title")
            include_hidden = bool(args.get("include_hidden", False))
            save_dir = args.get("save_dir") or None

            save_path = capture_window(query, save_dir=save_dir, include_hidden=include_hidden)
            return [_text_content(save_path)]

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

#!/usr/bin/env python3
"""
Fay Logseq MCP Server

通过文件系统对 Logseq 知识库进行操作，提供以下能力：
- 检索内容（标签、文本）
- 获取指定标签的 pages
- 在指定 page 写入 TODO 及文本内容
- 资源存入（assets），可选插入到指定 page
- 创建 pages

使用方式：
1. 推荐通过环境变量 LOGSEQ_GRAPH_DIR 指定 Logseq 图谱根目录
   例如：/path/to/your-graph （包含 pages/、journals/、assets/ 等目录）
2. 也可在每次调用工具时传入 graph_dir 参数覆盖

注意：本服务直接读写 Markdown 文件，不依赖 Logseq 运行态。
"""

import os
import re
import sys
import json
import base64
import datetime
from typing import Any, Dict, List, Optional, Tuple

# 将项目根目录加入 sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    import mcp.server.stdio
except ImportError:
    print("MCP库未安装，请运行: pip install mcp", file=sys.stderr, flush=True)
    sys.exit(1)


server = Server("logseq")


def _now_ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


class LogseqGraph:
    def __init__(self, root: Optional[str] = None):
        self.root = os.path.abspath(root) if root else None

    def with_root(self, graph_dir: Optional[str]) -> "LogseqGraph":
        root = graph_dir or self.root or os.environ.get("LOGSEQ_GRAPH_DIR")
        if not root:
            raise ValueError("未配置 Logseq 图谱目录，请设置环境变量 LOGSEQ_GRAPH_DIR 或在调用时传入 graph_dir")
        return LogseqGraph(root)

    # 路径相关
    def pages_dir(self) -> str:
        return os.path.join(self.root, "pages")

    def journals_dir(self) -> str:
        return os.path.join(self.root, "journals")

    def assets_dir(self) -> str:
        return os.path.join(self.root, "assets")

    def ensure_dirs(self):
        for d in [self.pages_dir(), self.journals_dir(), self.assets_dir()]:
            os.makedirs(d, exist_ok=True)

    # 文件名处理
    @staticmethod
    def _sanitize_filename(name: str) -> str:
        # 去除不合法字符，保留空格和中文
        return re.sub(r"[\\/:*?\"<>|]", "_", name).strip()

    def page_path(self, page_name: str) -> str:
        fname = self._sanitize_filename(page_name)
        # Logseq page 默认 .md
        if not fname.lower().endswith(".md") and not fname.lower().endswith(".org"):
            fname += ".md"
        return os.path.join(self.pages_dir(), fname)

    def list_md_files(self) -> List[Tuple[str, str]]:
        """返回 (绝对路径, 类型) 类型 ∈ {pages, journals} 的 md 文件列表"""
        files: List[Tuple[str, str]] = []
        for folder, kind in [(self.pages_dir(), "pages"), (self.journals_dir(), "journals")]:
            if os.path.isdir(folder):
                for fn in os.listdir(folder):
                    if fn.lower().endswith((".md", ".org")):
                        files.append((os.path.join(folder, fn), kind))
        return files

    # 基础操作
    def create_page(self, page_name: str, content: Optional[str] = None) -> Dict[str, Any]:
        self.ensure_dirs()
        path = self.page_path(page_name)
        if os.path.exists(path):
            return {"success": True, "message": "页面已存在", "path": path}
        with open(path, "w", encoding="utf-8") as f:
            if content:
                f.write(content.rstrip() + "\n")
        return {"success": True, "message": "页面创建成功", "path": path}

    def append_to_page(self, page_name: str, line: str) -> Dict[str, Any]:
        self.ensure_dirs()
        path = self.page_path(page_name)
        # 若不存在则先创建
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                pass
        with open(path, "a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")
        return {"success": True, "message": "写入成功", "path": path}

    def save_asset(self, filename: str, source_path: Optional[str] = None, base64_data: Optional[str] = None) -> Dict[str, Any]:
        self.ensure_dirs()
        safe_name = self._sanitize_filename(filename)
        target = os.path.join(self.assets_dir(), safe_name)
        if source_path:
            # 复制文件
            import shutil
            shutil.copy2(source_path, target)
        elif base64_data:
            data = base64.b64decode(base64_data)
            with open(target, "wb") as f:
                f.write(data)
        else:
            return {"success": False, "message": "必须提供 source_path 或 base64_data"}
        return {"success": True, "message": "资源已保存", "path": target, "filename": safe_name}

    # 检索
    @staticmethod
    def _read_text(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    def search_text(self, query: str, case_sensitive: bool = False, max_results: int = 200) -> Dict[str, Any]:
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(query), flags)
        results: List[Dict[str, Any]] = []
        for path, kind in self.list_md_files():
            text = self._read_text(path)
            for i, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    results.append({
                        "file": path,
                        "kind": kind,
                        "line": i,
                        "text": line.strip()
                    })
                    if len(results) >= max_results:
                        return {"success": True, "results": results}
        return {"success": True, "results": results}

    def search_tag(self, tag: str, max_results: int = 200) -> Dict[str, Any]:
        # 支持 #tag 或 #[[tag]] 两种形式；也兼容行内 [[tag]] 当作引用
        tag_escaped = re.escape(tag)
        patterns = [
            re.compile(rf"(^|\s)#({tag_escaped})(\b|$)", re.IGNORECASE),
            re.compile(rf"(^|\s)#\[\[({tag_escaped})\]\](\b|$)", re.IGNORECASE),
            re.compile(rf"\[\[({tag_escaped})\]\]", re.IGNORECASE),
        ]
        results: List[Dict[str, Any]] = []
        for path, kind in self.list_md_files():
            text = self._read_text(path)
            for i, line in enumerate(text.splitlines(), start=1):
                if any(p.search(line) for p in patterns):
                    results.append({
                        "file": path,
                        "kind": kind,
                        "line": i,
                        "text": line.strip()
                    })
                    if len(results) >= max_results:
                        return {"success": True, "results": results}
        return {"success": True, "results": results}

    def get_pages_by_tag(self, tag: str) -> Dict[str, Any]:
        search = self.search_tag(tag, max_results=10_000)
        if not search.get("success"):
            return search
        pages = set()
        pages_dir = self.pages_dir()
        for hit in search["results"]:
            path = hit["file"]
            # 提取 pages 下的文件名作为 page 名称
            if path.startswith(pages_dir):
                base = os.path.basename(path)
                # 去掉扩展名
                name = os.path.splitext(base)[0]
                pages.add(name)
        return {"success": True, "pages": sorted(pages)}

    def read_page(self, page_name: str) -> Dict[str, Any]:
        """读取指定页面的完整内容"""
        self.ensure_dirs()
        path = self.page_path(page_name)
        if not os.path.exists(path):
            return {
                "success": False,
                "message": f"页面不存在: {page_name}",
                "path": path
            }

        try:
            content = self._read_text(path)
            return {
                "success": True,
                "page": page_name,
                "path": path,
                "content": content,
                "lines": len(content.splitlines())
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"读取失败: {str(e)}",
                "path": path
            }

    def _ensure_root(self) -> str:
        if not self.root:
            raise ValueError(
                "Missing Logseq graph directory. Set LOGSEQ_GRAPH_DIR or pass graph_dir when calling the tool."
            )
        return self.root

    def _resolve_md_path(self, *, file: Optional[str] = None, page: Optional[str] = None) -> str:
        root = self._ensure_root()
        if file:
            path = os.path.abspath(file)
        elif page:
            path = self.page_path(page)
        else:
            raise ValueError("Either file or page must be provided")

        root_norm = os.path.normcase(root)
        path_norm = os.path.normcase(path)
        try:
            common = os.path.commonpath([root_norm, path_norm])
        except ValueError as exc:
            raise ValueError(f"File must live under the configured Logseq graph: {path}") from exc

        if common != root_norm:
            raise ValueError(f"File must live under the configured Logseq graph: {path}")

        if not os.path.isfile(path):
            raise FileNotFoundError(f"File not found: {path}")
        return path

    def update_task_status(
        self,
        *,
        file: Optional[str] = None,
        page: Optional[str] = None,
        line: Optional[int] = None,
        task_contains: Optional[str] = None,
        from_status: str = "TODO",
        to_status: str = "DONE"
    ) -> Dict[str, Any]:
        from_status = (from_status or "").strip()
        to_status = (to_status or "").strip()
        if not from_status or not to_status:
            return {"success": False, "message": "from_status and to_status must not be empty"}
        if from_status == to_status:
            return {"success": False, "message": "from_status and to_status cannot be the same"}

        path = self._resolve_md_path(file=file, page=page)

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if line is not None:
            idx_candidates = [line - 1]
            if idx_candidates[0] < 0 or idx_candidates[0] >= len(lines):
                return {"success": False, "message": f"Line number out of range: {line}"}
        else:
            idx_candidates = list(range(len(lines)))

        status_pattern = re.compile(rf"^(\s*[-*]\s+){re.escape(from_status)}(\b.*)$")
        match_index: Optional[int] = None
        original_line: Optional[str] = None

        task_filter = (task_contains or "").strip()
        for idx in idx_candidates:
            if idx < 0 or idx >= len(lines):
                continue
            current_line = lines[idx]
            if not status_pattern.match(current_line):
                continue
            if task_filter and task_filter not in current_line:
                continue
            match_index = idx
            original_line = current_line
            break

        if match_index is None:
            location_hint = f"line {line}" if line is not None else "the specified location"
            return {
                "success": False,
                "message": f"Could not find a matching {from_status} task at {location_hint}"
            }

        updated_line = status_pattern.sub(rf"\1{to_status}\2", original_line, count=1)
        if updated_line == original_line:
            return {"success": False, "message": "Task already appears to have the requested status"}
        lines[match_index] = updated_line

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return {
            "success": True,
            "file": path,
            "line": match_index + 1,
            "before": original_line.rstrip("\n"),
            "after": updated_line.rstrip("\n")
        }


graph = LogseqGraph(os.environ.get("LOGSEQ_GRAPH_DIR"))


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="search_text",
            description="全文检索：在 pages/ 和 journals/ 中查找包含指定文本的行",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要检索的文本"},
                    "case_sensitive": {"type": "boolean", "default": False},
                    "max_results": {"type": "integer", "default": 200},
                    "graph_dir": {"type": "string", "description": "可选，覆盖 LOGSEQ_GRAPH_DIR"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="search_tag",
            description="按标签检索：匹配 #tag、#[[tag]]、[[tag]]",
            inputSchema={
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "标签名（不含#）"},
                    "max_results": {"type": "integer", "default": 200},
                    "graph_dir": {"type": "string", "description": "可选，覆盖 LOGSEQ_GRAPH_DIR"}
                },
                "required": ["tag"]
            }
        ),
        Tool(
            name="get_pages_by_tag",
            description="获取包含指定标签的页面列表（仅统计 pages/ 目录）",
            inputSchema={
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "标签名（不含#）"},
                    "graph_dir": {"type": "string", "description": "可选，覆盖 LOGSEQ_GRAPH_DIR"}
                },
                "required": ["tag"]
            }
        ),
        Tool(
            name="read_page",
            description="读取指定页面的完整内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"type": "string", "description": "页面名（不含扩展名），例如：Fay"},
                    "graph_dir": {"type": "string", "description": "可选，覆盖 LOGSEQ_GRAPH_DIR"}
                },
                "required": ["page"]
            }
        ),
        Tool(
            name="append_todo_to_page",
            description="在指定 page 末尾追加一个 TODO 列表项",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"type": "string", "description": "页面名（不含扩展名）"},
                    "content": {"type": "string", "description": "TODO 内容"},
                    "level": {"type": "integer", "description": "缩进层级，0表示顶级", "default": 0},
                    "with_timestamp": {"type": "boolean", "default": True},
                    "graph_dir": {"type": "string", "description": "可选，覆盖 LOGSEQ_GRAPH_DIR"}
                },
                "required": ["page", "content"]
            }
        ),
        Tool(
            name="append_text_to_page",
            description="在指定 page 末尾追加一个文本列表项",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"type": "string", "description": "页面名（不含扩展名）"},
                    "content": {"type": "string", "description": "文本内容"},
                    "level": {"type": "integer", "description": "缩进层级，0表示顶级", "default": 0},
                    "graph_dir": {"type": "string", "description": "可选，覆盖 LOGSEQ_GRAPH_DIR"}
                },
                "required": ["page", "content"]
            }
        ),
        Tool(
            name="create_page",
            description="创建一个新的 page（若已存在则忽略）",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"type": "string", "description": "页面名（不含扩展名）"},
                    "content": {"type": "string", "description": "初始内容，可选"},
                    "graph_dir": {"type": "string", "description": "可选，覆盖 LOGSEQ_GRAPH_DIR"}
                },
                "required": ["page"]
            }
        ),
        Tool(
            name="update_task_status",
            description="Update status of a task inline (e.g. TODO -> DONE).",
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Absolute path of the markdown file to edit"},
                    "page": {"type": "string", "description": "Optional page name if you prefer to refer by page"},
                    "line": {"type": "integer", "description": "Optional line number (1-based)", "minimum": 1},
                    "task_contains": {"type": "string", "description": "Optional substring to help locate the task"},
                    "from_status": {"type": "string", "description": "Current status keyword (default TODO)", "default": "TODO"},
                    "to_status": {"type": "string", "description": "Target status keyword (default DONE)", "default": "DONE"},
                    "graph_dir": {"type": "string", "description": "Override LOGSEQ_GRAPH_DIR if needed"}
                },
                "required": ["file"]
            }
        ),
        Tool(
            name="save_asset",
            description="保存资源到 assets/，可选在指定 page 插入引用",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "目标文件名（会被清洗）"},
                    "source_path": {"type": "string", "description": "本地源文件路径，与 base64_data 二选一"},
                    "base64_data": {"type": "string", "description": "Base64 数据，与 source_path 二选一"},
                    "page": {"type": "string", "description": "可选，插入到该 page"},
                    "alt": {"type": "string", "description": "插图/附件说明，可选"},
                    "graph_dir": {"type": "string", "description": "可选，覆盖 LOGSEQ_GRAPH_DIR"}
                },
                "required": ["filename"]
            }
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    try:
        g = graph.with_root(arguments.get("graph_dir"))
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"success": False, "message": str(e)}, ensure_ascii=False))]

    try:
        if name == "search_text":
            res = g.search_text(
                query=arguments["query"],
                case_sensitive=arguments.get("case_sensitive", False),
                max_results=arguments.get("max_results", 200)
            )
            return [TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]

        elif name == "search_tag":
            res = g.search_tag(
                tag=arguments["tag"],
                max_results=arguments.get("max_results", 200)
            )
            return [TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]

        elif name == "get_pages_by_tag":
            res = g.get_pages_by_tag(arguments["tag"])
            return [TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]

        elif name == "read_page":
            res = g.read_page(arguments["page"])
            return [TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]

        elif name == "append_todo_to_page":
            level = max(int(arguments.get("level", 0)), 0)
            indent = "  " * level
            text = arguments["content"].strip()
            line = f"{indent}- TODO {text}"
            if arguments.get("with_timestamp", True):
                line += f"  ({_now_ts()})"
            res = g.append_to_page(arguments["page"], line)
            return [TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]

        elif name == "append_text_to_page":
            level = max(int(arguments.get("level", 0)), 0)
            indent = "  " * level
            text = arguments["content"].strip()
            line = f"{indent}- {text}"
            res = g.append_to_page(arguments["page"], line)
            return [TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]

        elif name == "create_page":
            res = g.create_page(arguments["page"], arguments.get("content"))
            return [TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]

        elif name == "update_task_status":
            res = g.update_task_status(
                file=arguments.get("file"),
                page=arguments.get("page"),
                line=arguments.get("line"),
                task_contains=arguments.get("task_contains"),
                from_status=arguments.get("from_status", "TODO"),
                to_status=arguments.get("to_status", "DONE")
            )
            return [TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]

        elif name == "save_asset":
            res = g.save_asset(
                filename=arguments["filename"],
                source_path=arguments.get("source_path"),
                base64_data=arguments.get("base64_data")
            )
            # 如需插入到 page
            if res.get("success") and arguments.get("page"):
                fname = res.get("filename")
                alt = arguments.get("alt") or os.path.splitext(fname)[0]
                # 在 pages 下引用 assets 需使用相对路径 ../assets/xxx
                link = f"![{alt}](../assets/{fname})"
                g.append_to_page(arguments["page"], f"- {link}")
            return [TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]

        else:
            return [TextContent(type="text", text=json.dumps({"success": False, "message": f"未知工具: {name}"}, ensure_ascii=False))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"success": False, "message": f"执行出错: {e}"}, ensure_ascii=False))]


async def main():
    # 运行 stdio 传输的 MCP Server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        init_opts = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_opts)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

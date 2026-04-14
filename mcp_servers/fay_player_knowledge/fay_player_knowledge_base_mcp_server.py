#!/usr/bin/env python3
"""
Fay 课程播放器 — 知识库检索 MCP 服务

仅支持原生课程包（含 manifest.json 的 .zip 文件）。
服务启动后在内存中建立索引，通过 MCP 工具向第三方 agent 提供课程知识检索能力，
无需浏览器播放器运行。

主要功能：
- 启动时从 --source 指定的目录/文件预加载课程包
- 每 60 秒自动扫描目录，检测课程包新增、变更、删除并更新索引
- 搜索命中章节时按需提取图片到缓存目录，通过内置 HTTP 服务返回可访问 URL

源码地址：https://gitee.com/xszyou/fay-player
在线播放器：https://player.fay-agent.com/
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import re
import shutil
import socketserver
import sys
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SERVER_NAME = "fay_player_knowledge_base_mcp_server"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

# ---------------------------------------------------------------------------
# 轻量 Embedding 客户端（调用 OpenAI 兼容 /embeddings 接口）
# ---------------------------------------------------------------------------
import math
import urllib.request
import urllib.error

_fay_url: str = ""  # Fay 本地服务地址，如 http://127.0.0.1:5000


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _call_embedding_api(text: str) -> Optional[List[float]]:
    """通过 Fay 透传接口 /v1/embeddings 获取向量，失败返回 None。"""
    if not _fay_url:
        return None
    try:
        url = f"{_fay_url.rstrip('/')}/v1/embeddings"
        payload = json.dumps({
            "model": "fay-embedding",
            "input": text[:2000],
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        data = result.get("data")
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get("embedding")
    except Exception as exc:
        write_stderr(f"[{SERVER_NAME}] embedding 调用失败: {exc}")
    return None


def _embedding_available() -> bool:
    return bool(_fay_url)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
MARKDOWN_EXTS = {".md", ".markdown"}
ZIP_EXTS = {".zip"}
DEFAULT_IMAGE_PORT = 18780

# Global image cache config — set by main() before any loading happens
_image_cache_dir: Optional[Path] = None
_image_base_url: str = ""
COURSE_SECTION_RE = re.compile(r"^第\s*(\d+)\s*节\s*(.*)$")
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
ASCII_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_./+-]{1,}", re.IGNORECASE)
CJK_SPAN_RE = re.compile(r"[\u3400-\u9FFF]+")
IMAGE_REF_RE = re.compile(r"!\[(.*?)\]\((?:<)?(.*?)(?:>)?\)")
LIST_KV_RE = re.compile(r"^\s*[-*+]\s*([^:：]+)\s*[:：]\s*(.*?)\s*$")
QUIZ_LINE_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
QUIZ_OPTION_RE = re.compile(r"^\s*[-*+]\s+([A-Z])\.\s+(.*\S)\s*$")
QUIZ_ANSWER_RE = re.compile(r"^\s*[-*+]\s+答案\s*[:：]\s*(.*?)\s*$")
QUIZ_TIP_RE = re.compile(r"^\s*[-*+]\s+解析\s*[:：]\s*(.*?)\s*$")
QUERY_TOKEN_STOPWORDS = {
    "a",
    "an",
    "are",
    "can",
    "could",
    "do",
    "does",
    "for",
    "how",
    "is",
    "please",
    "tell",
    "that",
    "the",
    "this",
    "what",
    "why",
    "with",
    "一下",
    "什么",
    "为啥",
    "为什么",
    "告诉",
    "如何",
    "怎么",
    "怎样",
    "是否",
    "有没",
    "有没有",
    "能否",
    "请问",
}


@dataclass
class QuizItem:
    index: int
    question: str
    options: List[str] = field(default_factory=list)
    answer_index: int = -1
    answer: str = ""
    tip: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "question": self.question,
            "options": list(self.options),
            "answer_index": self.answer_index,
            "answer": self.answer,
            "tip": self.tip,
        }


@dataclass
class SectionRecord:
    section_id: str
    index: int
    title: str
    level: int
    script: str = ""
    code_text: str = ""
    quizzes: List[QuizItem] = field(default_factory=list)
    images: List[Dict[str, str]] = field(default_factory=list)
    body_markdown: str = ""
    content_text: str = ""
    section_type: str = "content"  # "cover" | "toc" | "content"

    def to_catalog_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "index": self.index,
            "title": self.title,
            "level": self.level,
            "section_type": self.section_type,
            "quiz_count": len(self.quizzes),
            "image_count": len(self.images),
            "has_script": bool(self.script.strip()),
            "has_code": bool(self.code_text.strip()),
        }

    def to_full_dict(
        self,
        *,
        include_quizzes: bool = True,
        include_markdown: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "section_id": self.section_id,
            "index": self.index,
            "title": self.title,
            "level": self.level,
            "section_type": self.section_type,
            "script": self.script,
            "code_text": self.code_text,
            "images": list(self.images),
            "content_text": self.content_text,
            "quiz_count": len(self.quizzes),
        }
        if include_quizzes:
            payload["quizzes"] = [item.to_dict() for item in self.quizzes]
        if include_markdown:
            payload["body_markdown"] = self.body_markdown
        return payload


@dataclass
class KnowledgeSource:
    source_id: str
    source_type: str
    path: str
    source_name: str
    title: str
    course_id: str
    author: str
    version: str
    description: str
    sections: List[SectionRecord]
    raw_markdown: str
    knowledge_text: str
    indexed_at: float

    def summary_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "path": self.path,
            "source_name": self.source_name,
            "title": self.title,
            "course_id": self.course_id,
            "author": self.author,
            "version": self.version,
            "description": self.description,
            "section_count": len(self.sections),
            "indexed_at": self.indexed_at,
        }

    def catalog_dict(self) -> Dict[str, Any]:
        payload = self.summary_dict()
        payload["sections"] = [section.to_catalog_dict() for section in self.sections]
        return payload


@dataclass
class SearchChunk:
    chunk_id: str
    source_id: str
    source_title: str
    source_type: str
    section_id: str
    section_index: int
    section_title: str
    chunk_type: str
    text: str
    title_tokens: set[str]
    tokens: set[str]
    embedding: Optional[List[float]] = None


def write_stderr(text: str) -> None:
    try:
        sys.stderr.write(text.rstrip() + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def json_pretty(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def safe_json_loads(text: str, fallback: Any) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return fallback


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_search_text(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = re.sub(r"[`*_~>#\[\]\(\){}|]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def short_text(text: str, limit: int = 220) -> str:
    clean = normalize_spaces(text)
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."


def stable_hash(*parts: str) -> str:
    joined = "||".join(str(part or "") for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]


def slugify(text: str, fallback: str = "item") -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "")).strip("-").lower()
    return value or fallback


def parse_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def read_framed_message() -> Optional[Dict[str, Any]]:
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None

        stripped = line.strip()
        if not stripped:
            continue

        lower = stripped.lower()
        if lower.startswith(b"content-length:"):
            headers: Dict[str, str] = {}
            try:
                key, value = line.split(b":", 1)
                headers[key.decode("utf-8", errors="ignore").strip().lower()] = value.decode(
                    "utf-8", errors="ignore"
                ).strip()
            except Exception:
                return None

            while True:
                hline = sys.stdin.buffer.readline()
                if not hline:
                    return None
                if hline in (b"\r\n", b"\n"):
                    break
                if b":" not in hline:
                    continue
                key, value = hline.split(b":", 1)
                headers[key.decode("utf-8", errors="ignore").strip().lower()] = value.decode(
                    "utf-8", errors="ignore"
                ).strip()

            try:
                length = int(headers.get("content-length", "0"))
            except ValueError:
                length = 0
            if length <= 0:
                return None
            body = sys.stdin.buffer.read(length)
            if not body:
                return None
            return json.loads(body.decode("utf-8"))

        try:
            return json.loads(stripped.decode("utf-8"))
        except Exception as exc:
            write_stderr(f"[{SERVER_NAME}] invalid stdio json line: {exc}")
            continue


def write_framed_message(payload: Dict[str, Any]) -> None:
    raw = json_dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(raw + b"\n")
    sys.stdout.buffer.flush()


def write_response(msg_id: Any, result: Dict[str, Any]) -> None:
    write_framed_message({"jsonrpc": "2.0", "id": msg_id, "result": result})


def write_error(msg_id: Any, code: int, message: str) -> None:
    write_framed_message(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": code, "message": message},
        }
    )


def read_utf8_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_markdown(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"!\[(.*?)\]\((?:<)?(.*?)(?:>)?\)", r"\1 \2", value)
    value = re.sub(r"\[(.*?)\]\((?:<)?(.*?)(?:>)?\)", r"\1", value)
    value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value, flags=re.MULTILINE)
    value = value.replace("```", "\n").replace("~~~", "\n")
    value = re.sub(r"[*_~`]+", "", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def build_search_tokens(text: str, *, split_compound: bool = True) -> set[str]:
    """构建搜索 token 集合。
    split_compound=True（默认）：用于索引端，拆分复合词以扩大召回面。
    split_compound=False：用于查询端，保持用户原词不拆，避免碎片匹配。
    """
    normalized = normalize_search_text(text)
    tokens = set()
    for match in ASCII_TOKEN_RE.finditer(normalized):
        whole = match.group(0).lower()
        tokens.add(whole)
        # 仅索引端拆分复合词（如 fay-player → fay, player）
        if split_compound and any(sep in whole for sep in ("-", ".", "/")):
            for part in re.split(r"[-./]", whole):
                part = part.strip()
                if len(part) >= 2:
                    tokens.add(part)
    for span in CJK_SPAN_RE.findall(normalized):
        if len(span) <= 2:
            tokens.add(span)
            continue
        for size in (2, 3):
            if len(span) < size:
                continue
            for idx in range(len(span) - size + 1):
                tokens.add(span[idx : idx + size])
    return {token for token in tokens if token}


def filter_query_tokens(tokens: Iterable[str]) -> List[str]:
    filtered: List[str] = []
    seen: set[str] = set()
    for token in tokens:
        value = str(token or "").strip().lower()
        if not value or value in seen:
            continue
        if value in QUERY_TOKEN_STOPWORDS:
            continue
        if len(value) == 1 and value.isascii():
            continue
        seen.add(value)
        filtered.append(value)
    return filtered


def text_occurrences(text: str, token: str, limit: int = 4) -> int:
    count = 0
    start = 0
    while token and count < limit:
        pos = text.find(token, start)
        if pos < 0:
            break
        count += 1
        start = pos + len(token)
    return count


def extract_snippet(text: str, query: str, limit: int = 240) -> str:
    clean = normalize_spaces(text)
    if not clean:
        return ""
    normalized_query = normalize_search_text(query)
    normalized_text = normalize_search_text(clean)
    if not normalized_query or normalized_query not in normalized_text:
        return short_text(clean, limit)
    pos = normalized_text.find(normalized_query)
    start = max(0, pos - max(20, limit // 3))
    end = min(len(clean), start + limit)
    snippet = clean[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(clean):
        snippet = snippet.rstrip() + "..."
    return snippet


def section_title_from_heading(raw_title: str, default_index: int) -> Tuple[int, str]:
    title = normalize_spaces(raw_title)
    matched = COURSE_SECTION_RE.match(title)
    if matched:
        index = int(matched.group(1))
        rest = normalize_spaces(matched.group(2))
        return index, rest or f"Section {index}"
    return default_index, title or f"Section {default_index}"


_COVER_KEYWORDS = {"封面", "cover", "首页", "标题页"}
_TOC_KEYWORDS = {"目录", "toc", "table of contents", "章节目录", "课程目录", "大纲"}


def classify_section_type(title: str) -> str:
    """根据节标题判断类型: cover / toc / content"""
    t = normalize_spaces(title).lower().strip()
    if t in _COVER_KEYWORDS or any(kw in t for kw in _COVER_KEYWORDS):
        return "cover"
    if t in _TOC_KEYWORDS or any(kw in t for kw in _TOC_KEYWORDS):
        return "toc"
    return "content"


def split_markdown_on_level(text: str, level: int) -> Tuple[List[str], List[Tuple[str, List[str]]]]:
    lines = str(text or "").splitlines()
    preamble: List[str] = []
    blocks: List[Tuple[str, List[str]]] = []
    current_title: Optional[str] = None
    current_lines: List[str] = []
    in_fence = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if current_title is None:
                preamble.append(line)
            else:
                current_lines.append(line)
            in_fence = not in_fence
            continue

        heading = MARKDOWN_HEADING_RE.match(line)
        if not in_fence and heading and len(heading.group(1)) == level:
            if current_title is not None:
                blocks.append((current_title, current_lines))
            current_title = normalize_spaces(heading.group(2))
            current_lines = []
            continue

        if current_title is None:
            preamble.append(line)
        else:
            current_lines.append(line)

    if current_title is not None:
        blocks.append((current_title, current_lines))

    return preamble, blocks


def extract_code_blocks(markdown_text: str) -> List[str]:
    lines = str(markdown_text or "").splitlines()
    blocks: List[str] = []
    in_fence = False
    current: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if in_fence:
                blocks.append("\n".join(current).strip())
                current = []
            in_fence = not in_fence
            continue
        if in_fence:
            current.append(line)

    return [block for block in blocks if block]


def extract_image_refs(markdown_text: str) -> List[Dict[str, str]]:
    images: List[Dict[str, str]] = []
    for match in IMAGE_REF_RE.finditer(str(markdown_text or "")):
        alt = normalize_spaces(match.group(1))
        src = normalize_spaces(match.group(2))
        if not src:
            continue
        images.append({"alt": alt or "image", "src": src})
    return images


def render_quizzes_text(quizzes: Sequence[QuizItem]) -> str:
    lines: List[str] = []
    for quiz in quizzes:
        lines.append(f"{quiz.index + 1}. {quiz.question}")
        for idx, option in enumerate(quiz.options):
            lines.append(f"   - {chr(65 + idx)}. {option}")
        if quiz.answer:
            lines.append(f"   - Answer: {quiz.answer}")
        if quiz.tip:
            lines.append(f"   - Tip: {quiz.tip}")
    return "\n".join(lines).strip()


def parse_quizzes_from_markdown(markdown_text: str) -> List[QuizItem]:
    quizzes: List[QuizItem] = []
    current: Optional[QuizItem] = None

    for raw_line in str(markdown_text or "").splitlines():
        question_match = QUIZ_LINE_RE.match(raw_line)
        if question_match:
            if current is not None:
                quizzes.append(current)
            current = QuizItem(index=len(quizzes), question=normalize_spaces(question_match.group(2)))
            continue

        if current is None:
            continue

        option_match = QUIZ_OPTION_RE.match(raw_line)
        if option_match:
            current.options.append(normalize_spaces(option_match.group(2)))
            continue

        answer_match = QUIZ_ANSWER_RE.match(raw_line)
        if answer_match:
            current.answer = normalize_spaces(answer_match.group(1))
            label = current.answer[:1].upper()
            if "A" <= label <= "Z":
                current.answer_index = ord(label) - 65
            continue

        tip_match = QUIZ_TIP_RE.match(raw_line)
        if tip_match:
            current.tip = normalize_spaces(tip_match.group(1))
            continue

    if current is not None:
        quizzes.append(current)

    return quizzes


def infer_asset_type(src: str, explicit: str = "") -> str:
    exp = str(explicit or "").strip().lower()
    if exp:
        return exp
    lower = str(src or "").strip().lower()
    if any(lower.endswith(ext) for ext in IMAGE_EXTS):
        return "slide"
    if lower.endswith(".json") or ".code." in lower or lower.endswith(".txt"):
        return "code"
    return "file"


def zip_file_map(zf: zipfile.ZipFile) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for name in zf.namelist():
        normalized = name.strip("/").replace("\\", "/").lower()
        if normalized:
            mapping[normalized] = name
    return mapping


def find_zip_member(zf: zipfile.ZipFile, file_map: Dict[str, str], relative_path: str, base_dir: str = "") -> Optional[str]:
    normalized = str(relative_path or "").strip().replace("\\", "/").strip("/")
    if not normalized:
        return None
    candidates = [normalized]
    if base_dir:
        candidates.append(f"{base_dir.strip('/')}/{normalized}")
    lower_candidates = {item.lower(): item for item in candidates}
    for lowered in lower_candidates:
        if lowered in file_map:
            return file_map[lowered]
    suffixes = ["/" + item.lower() for item in candidates]
    for key, original in file_map.items():
        for suffix in suffixes:
            if key.endswith(suffix):
                return original
    return None


def read_zip_text(zf: zipfile.ZipFile, member: Optional[str]) -> str:
    if not member:
        return ""
    try:
        return zf.read(member).decode("utf-8")
    except UnicodeDecodeError:
        return zf.read(member).decode("utf-8-sig", errors="ignore")


def parse_quizzes_from_json(payload: Any) -> List[QuizItem]:
    rows = payload if isinstance(payload, list) else []
    quizzes: List[QuizItem] = []
    for idx, item in enumerate(rows):
        if not isinstance(item, dict):
            continue
        options = [normalize_spaces(str(value or "")) for value in item.get("opts") or []]
        answer_index = int(item.get("ans", -1)) if str(item.get("ans", "")).strip() else -1
        answer = ""
        if 0 <= answer_index < len(options):
            answer = f"{chr(65 + answer_index)}. {options[answer_index]}"
        quizzes.append(
            QuizItem(
                index=idx,
                question=normalize_spaces(item.get("q") or ""),
                options=options,
                answer_index=answer_index,
                answer=answer,
                tip=normalize_spaces(item.get("tip") or ""),
            )
        )
    return quizzes


def parse_course_metadata_from_lines(lines: Sequence[str]) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for raw_line in lines:
        match = LIST_KV_RE.match(raw_line)
        if not match:
            continue
        key = normalize_spaces(match.group(1)).lower()
        value = normalize_spaces(match.group(2))
        if not value:
            continue
        meta[key] = value
    return meta


def render_source_markdown(
    title: str,
    course_id: str,
    author: str,
    version: str,
    description: str,
    sections: Sequence[SectionRecord],
) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"- 课程ID：{course_id or 'unknown'}")
    lines.append(f"- 作者：{author or 'unknown'}")
    lines.append(f"- 版本：{version or '0.0.0'}")
    lines.append(f"- 章节数：{len(sections)}")
    if description:
        lines.append(f"- 简介：{description}")
    lines.extend(["", "## 目录", ""])
    for section in sections:
        title_part = section.title
        quiz_part = f"（{len(section.quizzes)} 题）" if section.quizzes else ""
        lines.append(f"{section.index + 1}. {title_part}{quiz_part}")

    for section in sections:
        lines.extend(["", f"## 第{section.index + 1}节 {section.title}", "", "### 讲稿", ""])
        lines.append(section.script or "（无）")
        lines.extend(["", "### 代码/文案", ""])
        if section.code_text.strip():
            lines.extend(["```", section.code_text, "```"])
        else:
            lines.append("（无）")
        lines.extend(["", "### 题目", ""])
        if section.quizzes:
            for quiz in section.quizzes:
                lines.append(f"{quiz.index + 1}. {quiz.question}")
                for idx, option in enumerate(quiz.options):
                    lines.append(f"   - {chr(65 + idx)}. {option}")
                lines.append(f"   - 答案：{quiz.answer or '（未配置）'}")
                if quiz.tip:
                    lines.append(f"   - 解析：{quiz.tip}")
        else:
            lines.append("（无）")
    lines.append("")
    return "\n".join(lines)


def build_knowledge_text(
    title: str,
    course_id: str,
    author: str,
    version: str,
    sections: Sequence[SectionRecord],
) -> str:
    lines = [
        f"Course ID: {course_id}",
        f"Title: {title}",
        f"Author: {author}",
        f"Version: {version}",
    ]
    for section in sections:
        lines.extend(["", f"[Section {section.index + 1}] {section.title}"])
        if section.script:
            lines.append(section.script)
        if section.code_text:
            lines.extend(["Code:", section.code_text])
        if section.quizzes:
            lines.append("Quizzes:")
            lines.append(render_quizzes_text(section.quizzes))
    return "\n".join(lines).strip()


def load_markdown_source(path: Path, text: str, source_type: str) -> KnowledgeSource:
    preamble_h2, h2_blocks = split_markdown_on_level(text, 2)
    title_match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    title = normalize_spaces(title_match.group(1)) if title_match else path.stem
    meta = parse_course_metadata_from_lines(preamble_h2)
    course_id = meta.get("课程id", "") or slugify(path.stem, "course")
    author = meta.get("作者", "") or "unknown"
    version = meta.get("版本", "") or "0.0.0"
    description = meta.get("简介", "")
    sections: List[SectionRecord] = []

    exported_blocks = [
        (heading, lines) for heading, lines in h2_blocks if COURSE_SECTION_RE.match(normalize_spaces(heading))
    ]
    if exported_blocks:
        for fallback_index, (heading, lines) in enumerate(exported_blocks, start=1):
            section_index, section_title = section_title_from_heading(heading, fallback_index)
            body = "\n".join(lines).strip()
            _, h3_blocks = split_markdown_on_level(body, 3)
            script = ""
            code_text = ""
            quizzes: List[QuizItem] = []
            images: List[Dict[str, str]] = []
            body_parts: List[str] = []

            for sub_heading, sub_lines in h3_blocks:
                sub_title = normalize_spaces(sub_heading)
                sub_body = "\n".join(sub_lines).strip()
                if sub_title == "讲稿":
                    script = strip_markdown(sub_body)
                elif sub_title in {"代码/文案", "代码", "文案"}:
                    code_blocks = extract_code_blocks(sub_body)
                    code_text = "\n\n".join(code_blocks).strip() if code_blocks else strip_markdown(sub_body)
                elif sub_title == "题目":
                    quizzes = parse_quizzes_from_markdown(sub_body)
                elif sub_title == "图片":
                    images = extract_image_refs(sub_body)
                else:
                    body_parts.append(sub_body)

            content_chunks = [
                value
                for value in [
                    script,
                    code_text,
                    render_quizzes_text(quizzes),
                    strip_markdown("\n\n".join(body_parts)),
                ]
                if value
            ]
            section_id = f"s{section_index:02d}-{slugify(section_title, f'section-{section_index}')}"
            sections.append(
                SectionRecord(
                    section_id=section_id,
                    index=section_index - 1,
                    title=section_title,
                    level=2,
                    script=script,
                    code_text=code_text,
                    quizzes=quizzes,
                    images=images,
                    body_markdown=body,
                    content_text="\n\n".join(content_chunks).strip(),
                    section_type=classify_section_type(section_title),
                )
            )
    else:
        if h2_blocks:
            for idx, (heading, lines) in enumerate(h2_blocks):
                body = "\n".join(lines).strip()
                quizzes = parse_quizzes_from_markdown(body) if "题目" in heading else []
                code_blocks = extract_code_blocks(body)
                content_text = strip_markdown(body)
                sec_title = normalize_spaces(heading) or f"Section {idx + 1}"
                sections.append(
                    SectionRecord(
                        section_id=f"s{idx + 1:02d}-{slugify(heading, f'section-{idx + 1}')}",
                        index=idx,
                        title=sec_title,
                        level=2,
                        script=content_text,
                        code_text="\n\n".join(code_blocks).strip(),
                        quizzes=quizzes,
                        images=extract_image_refs(body),
                        body_markdown=body,
                        content_text=content_text,
                        section_type=classify_section_type(sec_title),
                    )
                )
        else:
            content_text = strip_markdown(text)
            sections.append(
                SectionRecord(
                    section_id="s01-document",
                    index=0,
                    title=title,
                    level=1,
                    script=content_text,
                    code_text="\n\n".join(extract_code_blocks(text)).strip(),
                    quizzes=parse_quizzes_from_markdown(text),
                    images=extract_image_refs(text),
                    body_markdown=text.strip(),
                    content_text=content_text,
                    section_type=classify_section_type(title),
                )
            )

    source_id = f"{slugify(course_id or title, 'source')}-{stable_hash(str(path.resolve()))}"
    knowledge_text = build_knowledge_text(title, course_id, author, version, sections)
    return KnowledgeSource(
        source_id=source_id,
        source_type=source_type,
        path=str(path.resolve()),
        source_name=path.name,
        title=title,
        course_id=course_id,
        author=author,
        version=version,
        description=description,
        sections=sections,
        raw_markdown=text,
        knowledge_text=knowledge_text,
        indexed_at=time.time(),
    )


def _extract_and_serve_images(
    source: "KnowledgeSource",
    images: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """Extract images from the source zip to cache and return list with HTTP URLs.

    Only called when a section is actually returned to the caller.
    If the cache is not configured or the source zip is missing, returns the original list.
    """
    if not _image_cache_dir or not _image_base_url:
        return images
    if not images:
        return images
    zip_path = Path(source.path)
    if not zip_path.is_file():
        return images
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            file_map = zip_file_map(zf)
            # Determine manifest_dir from the zip
            manifest_dir = ""
            for name in zf.namelist():
                if name.strip("/").replace("\\", "/").lower().endswith("manifest.json"):
                    manifest_dir = str(Path(name).parent).replace("\\", "/").strip(".")
                    break

            result: List[Dict[str, str]] = []
            for img in images:
                src = img.get("src", "")
                member = find_zip_member(zf, file_map, src, manifest_dir)
                if not member:
                    result.append(img)
                    continue
                safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(member).name)
                dest_dir = _image_cache_dir / source.source_id
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file = dest_dir / safe_name
                try:
                    with zf.open(member) as zin, open(dest_file, "wb") as fout:
                        shutil.copyfileobj(zin, fout)
                    result.append({
                        "alt": img.get("alt", "image"),
                        "src": f"{_image_base_url}/{source.source_id}/{safe_name}",
                    })
                except Exception:
                    result.append(img)
            return result
    except Exception:
        return images


def _start_image_http_server(cache_dir: Path, port: int) -> int:
    """Start a daemon HTTP server serving files from cache_dir. Returns the actual port."""

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(cache_dir), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            pass  # suppress access logs to avoid polluting stderr

        def end_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    server = ReusableTCPServer(("127.0.0.1", port), QuietHandler)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="kb-image-http")
    thread.start()
    write_stderr(f"[{SERVER_NAME}] image HTTP server started at http://127.0.0.1:{actual_port}")
    return actual_port


def load_course_zip(path: Path) -> KnowledgeSource:
    with zipfile.ZipFile(path, "r") as zf:
        file_map = zip_file_map(zf)
        manifest_member = None
        for name in zf.namelist():
            normalized = name.strip("/").replace("\\", "/").lower()
            if normalized.endswith("manifest.json"):
                manifest_member = name
                break
        if not manifest_member:
            raise ValueError("course zip does not contain manifest.json")

        manifest_text = read_zip_text(zf, manifest_member)
        manifest = safe_json_loads(manifest_text, None)
        if not isinstance(manifest, dict):
            raise ValueError("manifest.json parse error")
        sections_payload = manifest.get("sections")
        if not isinstance(sections_payload, list):
            raise ValueError("manifest.sections is required")

        manifest_dir = str(Path(manifest_member).parent).replace("\\", "/").strip(".")
        course_id = normalize_spaces(manifest.get("id") or "") or slugify(path.stem, "course")
        title = normalize_spaces(manifest.get("title") or "") or path.stem
        author = normalize_spaces(manifest.get("author") or "") or "unknown"
        version = normalize_spaces(manifest.get("version") or "") or "0.0.0"
        description = normalize_spaces(manifest.get("description") or "")
        source_id = f"{slugify(course_id or title, 'source')}-{stable_hash(str(path.resolve()))}"

        sections: List[SectionRecord] = []
        for idx, payload in enumerate(sections_payload):
            if not isinstance(payload, dict):
                continue
            raw_title = normalize_spaces(payload.get("title") or "") or f"Section {idx + 1}"
            script_member = find_zip_member(zf, file_map, str(payload.get("script") or ""), manifest_dir)
            script = strip_markdown(read_zip_text(zf, script_member))

            quiz_member = find_zip_member(zf, file_map, str(payload.get("quiz") or ""), manifest_dir)
            quiz_payload = safe_json_loads(read_zip_text(zf, quiz_member), [])
            quizzes = parse_quizzes_from_json(quiz_payload)

            images: List[Dict[str, str]] = []
            code_parts: List[str] = []
            for asset in payload.get("assets") or []:
                if isinstance(asset, str):
                    src = asset
                    asset_type = infer_asset_type(src)
                    title_text = Path(src).name
                    inline_code = ""
                elif isinstance(asset, dict):
                    src = str(asset.get("src") or "")
                    asset_type = infer_asset_type(src, str(asset.get("type") or ""))
                    title_text = normalize_spaces(asset.get("title") or Path(src).name)
                    inline_code = str(asset.get("code") or asset.get("content") or "")
                else:
                    continue

                if asset_type in {"slide", "image"}:
                    if src:
                        images.append({"alt": title_text or "image", "src": src})
                    continue

                if asset_type == "code":
                    if inline_code.strip():
                        code_parts.append(inline_code.strip())
                        continue
                    member = find_zip_member(zf, file_map, src, manifest_dir)
                    raw_code = read_zip_text(zf, member)
                    if not raw_code.strip():
                        continue
                    parsed_code = safe_json_loads(raw_code, None)
                    if isinstance(parsed_code, dict) and isinstance(parsed_code.get("code"), str):
                        code_parts.append(parsed_code["code"].strip())
                    else:
                        code_parts.append(raw_code.strip())

            inline_section_code = str(payload.get("code") or "").strip()
            if inline_section_code:
                code_parts.append(inline_section_code)

            code_text = "\n\n".join(part for part in code_parts if part).strip()
            quiz_text = render_quizzes_text(quizzes)
            content_parts = [value for value in [script, code_text, quiz_text] if value]
            sections.append(
                SectionRecord(
                    section_id=normalize_spaces(payload.get("id") or "") or f"s{idx + 1:02d}",
                    index=idx,
                    title=raw_title,
                    level=2,
                    script=script,
                    code_text=code_text,
                    quizzes=quizzes,
                    images=images,
                    body_markdown="",
                    content_text="\n\n".join(content_parts).strip(),
                    section_type=classify_section_type(raw_title),
                )
            )

    raw_markdown = render_source_markdown(title, course_id, author, version, description, sections)
    knowledge_text = build_knowledge_text(title, course_id, author, version, sections)
    return KnowledgeSource(
        source_id=source_id,
        source_type="course_zip",
        path=str(path.resolve()),
        source_name=path.name,
        title=title,
        course_id=course_id,
        author=author,
        version=version,
        description=description,
        sections=sections,
        raw_markdown=raw_markdown,
        knowledge_text=knowledge_text,
        indexed_at=time.time(),
    )


def load_source_from_path(path: Path) -> KnowledgeSource:
    suffix = path.suffix.lower()
    if suffix not in ZIP_EXTS:
        raise ValueError(f"unsupported file (only .zip course packages are supported): {path.name}")
    return load_course_zip(path)


def discover_source_files(root: Path, recursive: bool) -> List[Path]:
    iterator: Iterable[Path] = root.rglob("*") if recursive else root.iterdir()
    files: List[Path] = []
    for entry in iterator:
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix in ZIP_EXTS:
            files.append(entry)
    return sorted({item.resolve() for item in files})


class KnowledgeBase:
    def __init__(self) -> None:
        self.sources: Dict[str, KnowledgeSource] = {}
        self.chunks: List[SearchChunk] = []
        self.section_lookup: Dict[Tuple[str, str], SectionRecord] = {}

    def _rebuild_chunk_index(self) -> None:
        chunks: List[SearchChunk] = []
        section_lookup: Dict[Tuple[str, str], SectionRecord] = {}
        for source in self.sources.values():
            for section in source.sections:
                section_lookup[(source.source_id, section.section_id)] = section
                narrative_parts = [section.title]
                if section.script.strip():
                    narrative_parts.append(section.script)
                elif section.content_text.strip():
                    narrative_parts.append(section.content_text)
                base_chunk_text = "\n\n".join(part for part in narrative_parts if part).strip()
                chunks.append(
                    SearchChunk(
                        chunk_id=f"{source.source_id}:{section.section_id}:section",
                        source_id=source.source_id,
                        source_title=source.title,
                        source_type=source.source_type,
                        section_id=section.section_id,
                        section_index=section.index,
                        section_title=section.title,
                        chunk_type="section",
                        text=base_chunk_text,
                        title_tokens=build_search_tokens(section.title),
                        tokens=build_search_tokens(base_chunk_text),
                    )
                )

                if section.code_text.strip():
                    chunks.append(
                        SearchChunk(
                            chunk_id=f"{source.source_id}:{section.section_id}:code",
                            source_id=source.source_id,
                            source_title=source.title,
                            source_type=source.source_type,
                            section_id=section.section_id,
                            section_index=section.index,
                            section_title=section.title,
                            chunk_type="code",
                            text=section.code_text,
                            title_tokens=build_search_tokens(section.title),
                            tokens=build_search_tokens(section.code_text),
                        )
                    )

                for quiz in section.quizzes:
                    quiz_text_lines = [quiz.question]
                    for idx, option in enumerate(quiz.options):
                        quiz_text_lines.append(f"{chr(65 + idx)}. {option}")
                    if quiz.answer:
                        quiz_text_lines.append(f"Answer: {quiz.answer}")
                    if quiz.tip:
                        quiz_text_lines.append(f"Tip: {quiz.tip}")
                    quiz_text = "\n".join(quiz_text_lines)
                    chunks.append(
                        SearchChunk(
                            chunk_id=f"{source.source_id}:{section.section_id}:quiz:{quiz.index}",
                            source_id=source.source_id,
                            source_title=source.title,
                            source_type=source.source_type,
                            section_id=section.section_id,
                            section_index=section.index,
                            section_title=section.title,
                            chunk_type="quiz",
                            text=quiz_text,
                            title_tokens=build_search_tokens(section.title),
                            tokens=build_search_tokens(quiz_text),
                        )
                    )
        self.chunks = chunks
        self.section_lookup = section_lookup
        # embedding 索引在后台线程异步构建，不阻塞 MCP 连接
        if _embedding_available():
            threading.Thread(
                target=self._build_embeddings_async,
                daemon=True,
            ).start()

    def _build_embeddings_async(self) -> None:
        """后台线程：等 Fay flask 就绪后逐个计算 chunk embedding。"""
        # 等待 Fay flask 服务就绪（最多 30 秒）
        for _ in range(30):
            try:
                test_req = urllib.request.Request(
                    f"{_fay_url.rstrip('/')}/v1/models",
                    method="GET",
                )
                with urllib.request.urlopen(test_req, timeout=2):
                    break
            except Exception:
                time.sleep(1)
        else:
            write_stderr(f"[{SERVER_NAME}] Fay 服务未就绪，跳过 embedding 索引")
            return

        embedded_count = 0
        chunks_snapshot = list(self.chunks)  # 快照，避免迭代中被替换
        for chunk in chunks_snapshot:
            if chunk.embedding is not None:
                continue
            embed_text = f"{chunk.source_title} - {chunk.section_title}: {chunk.text[:500]}"
            vec = _call_embedding_api(embed_text)
            if vec:
                chunk.embedding = vec
                embedded_count += 1
        write_stderr(f"[{SERVER_NAME}] embedding 索引完成: {embedded_count}/{len(chunks_snapshot)} chunks")

    def add_source_path(self, path_text: str, *, recursive: bool = True) -> Dict[str, Any]:
        path = Path(path_text).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"path not found: {path}")

        if path.is_dir():
            discovered = discover_source_files(path, recursive=recursive)
            loaded: List[Dict[str, Any]] = []
            skipped: List[Dict[str, str]] = []
            for file_path in discovered:
                try:
                    source = load_source_from_path(file_path)
                    self.sources[source.source_id] = source
                    loaded.append(source.summary_dict())
                except Exception as exc:
                    skipped.append({"path": str(file_path), "error": str(exc)})
            self._rebuild_chunk_index()
            return {
                "root": str(path),
                "recursive": recursive,
                "loaded_count": len(loaded),
                "skipped_count": len(skipped),
                "loaded": loaded,
                "skipped": skipped,
            }

        source = load_source_from_path(path)
        self.sources[source.source_id] = source
        self._rebuild_chunk_index()
        return {
            "loaded_count": 1,
            "skipped_count": 0,
            "loaded": [source.summary_dict()],
            "skipped": [],
        }

    def list_sources(self) -> Dict[str, Any]:
        items = [self.sources[key].summary_dict() for key in sorted(self.sources)]
        return {"count": len(items), "sources": items}

    def remove_source(self, source_id: str) -> Dict[str, Any]:
        removed = self.sources.pop(source_id, None)
        if removed is None:
            raise ValueError(f"source not found: {source_id}")
        self._rebuild_chunk_index()
        return {"removed": removed.summary_dict(), "remaining_count": len(self.sources)}

    def reload(self, source_id: str = "") -> Dict[str, Any]:
        if source_id:
            target = self.sources.get(source_id)
            if not target:
                raise ValueError(f"source not found: {source_id}")
            refreshed = load_source_from_path(Path(target.path))
            self.sources[source_id] = refreshed
            self._rebuild_chunk_index()
            return {"reloaded_count": 1, "sources": [refreshed.summary_dict()]}

        refreshed_sources: Dict[str, KnowledgeSource] = {}
        results: List[Dict[str, Any]] = []
        for existing_id in sorted(self.sources):
            current = self.sources[existing_id]
            refreshed = load_source_from_path(Path(current.path))
            refreshed_sources[existing_id] = refreshed
            results.append(refreshed.summary_dict())
        self.sources = refreshed_sources
        self._rebuild_chunk_index()
        return {"reloaded_count": len(results), "sources": results}

    def get_catalog(self, source_id: str = "") -> Dict[str, Any]:
        if source_id:
            source = self.sources.get(source_id)
            if not source:
                raise ValueError(f"source not found: {source_id}")
            return source.catalog_dict()
        catalogs = [self.sources[key].catalog_dict() for key in sorted(self.sources)]
        return {"count": len(catalogs), "sources": catalogs}

    @staticmethod
    def _resolve_section_images(
        source: KnowledgeSource, section: SectionRecord, section_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Replace zip-internal image paths with HTTP URLs (on-demand extraction)."""
        if section.images and _image_cache_dir and _image_base_url:
            section_dict["images"] = _extract_and_serve_images(source, section.images)
        return section_dict

    def get_section(
        self,
        source_id: str,
        *,
        section_id: str = "",
        section_index: Optional[int] = None,
        include_quizzes: bool = True,
        include_markdown: bool = False,
    ) -> Dict[str, Any]:
        source = self.sources.get(source_id)
        if not source:
            raise ValueError(f"source not found: {source_id}")

        target: Optional[SectionRecord] = None
        if section_id:
            for section in source.sections:
                if section.section_id == section_id:
                    target = section
                    break
        elif section_index is not None:
            for section in source.sections:
                if section.index == section_index:
                    target = section
                    break
        else:
            raise ValueError("section_id or section_index is required")

        if target is None:
            raise ValueError("section not found")

        section_dict = target.to_full_dict(
            include_quizzes=include_quizzes,
            include_markdown=include_markdown,
        )
        self._resolve_section_images(source, target, section_dict)
        # 将图片以 markdown 语法追加到 content_text
        resolved_images = section_dict.get("images") or []
        if resolved_images:
            img_lines = "\n".join(
                f'![{img.get("alt", "image")}]({img["src"]})'
                for img in resolved_images if img.get("src", "").startswith("http")
            )
            if img_lines:
                section_dict["content_text"] = (section_dict.get("content_text") or "") + "\n\n" + img_lines
        return {
            "source": source.summary_dict(),
            "section": section_dict,
        }

    def read_document(self, source_id: str, fmt: str = "summary") -> Dict[str, Any]:
        source = self.sources.get(source_id)
        if not source:
            raise ValueError(f"source not found: {source_id}")

        output = normalize_spaces(fmt).lower() or "summary"
        if output == "summary":
            return {
                "source": source.summary_dict(),
                "sections": [section.to_catalog_dict() for section in source.sections],
            }
        if output == "markdown":
            return {
                "source": source.summary_dict(),
                "format": "markdown",
                "content": source.raw_markdown,
            }
        if output == "text":
            return {
                "source": source.summary_dict(),
                "format": "text",
                "content": source.knowledge_text,
            }
        if output == "json":
            section_dicts = []
            for section in source.sections:
                sd = section.to_full_dict(include_markdown=True)
                self._resolve_section_images(source, section, sd)
                section_dicts.append(sd)
            return {
                "source": source.summary_dict(),
                "format": "json",
                "content": {
                    "course_id": source.course_id,
                    "title": source.title,
                    "author": source.author,
                    "version": source.version,
                    "description": source.description,
                    "sections": section_dicts,
                },
            }
        raise ValueError("format must be one of: summary, markdown, text, json")

    def search(
        self,
        query: str,
        *,
        source_id: str = "",
        limit: int = 5,
        include_match_details: bool = False,
        include_quizzes: bool = True,
        include_markdown: bool = False,
    ) -> Dict[str, Any]:
        query_text = normalize_search_text(query)
        if not query_text:
            raise ValueError("query is required")
        if source_id and source_id not in self.sources:
            source_id = ""  # fallback: search all sources

        query_tokens = filter_query_tokens(build_search_tokens(query_text, split_compound=False))
        if not query_tokens:
            query_tokens = list(build_search_tokens(query_text))

        # 计算 query embedding（用于混合评分）
        query_embedding: Optional[List[float]] = None
        if _embedding_available():
            query_embedding = _call_embedding_api(query)

        grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for chunk in self.chunks:
            if source_id and chunk.source_id != source_id:
                continue

            source_title_text = normalize_search_text(chunk.source_title)
            title_text = normalize_search_text(chunk.section_title)
            body_text = normalize_search_text(chunk.text)
            score = 0.0

            # 课程标题匹配（最高优先级）
            if query_text == source_title_text:
                score += 200.0
            elif query_text in source_title_text:
                score += 120.0
            elif source_title_text in query_text:
                score += 80.0

            # 章节标题匹配
            if query_text == title_text:
                score += 100.0
            elif query_text in title_text:
                score += 50.0
            elif query_text in body_text:
                score += 18.0 + 3.0 * text_occurrences(body_text, query_text)

            token_hits = 0
            title_hits = 0
            source_title_tokens = build_search_tokens(source_title_text)
            source_title_hits = 0
            for token in query_tokens:
                if token in chunk.tokens:
                    token_hits += 1
                if token in chunk.title_tokens:
                    title_hits += 1
                if token in source_title_tokens:
                    source_title_hits += 1
            score += token_hits * 4.0
            score += title_hits * 6.0
            score += source_title_hits * 15.0

            if chunk.chunk_type == "quiz" and ("题" in query_text or "quiz" in query_text):
                score += 3.0
            if chunk.chunk_type == "code" and ("代码" in query_text or "code" in query_text):
                score += 3.0

            # embedding 语义相似度加分
            if query_embedding and chunk.embedding:
                sim = _cosine_similarity(query_embedding, chunk.embedding)
                score += max(0.0, sim) * 100.0  # 余弦相似度 0~1 映射到 0~100

            if score < 10.0:
                continue

            key = (chunk.source_id, chunk.section_id)
            group = grouped.get(key)
            if group is None:
                section = self.section_lookup.get(key)
                if section is None:
                    continue
                source = self.sources.get(chunk.source_id)
                if source is None:
                    continue
                group = {
                    "source": source,
                    "section": section,
                    "best_score": 0.0,
                    "score_sum": 0.0,
                    "match_count": 0,
                    "matched_in": set(),
                    "details": [],
                }
                grouped[key] = group

            group["best_score"] = max(float(group["best_score"]), score)
            group["score_sum"] = float(group["score_sum"]) + score
            group["match_count"] = int(group["match_count"]) + 1
            group["matched_in"].add(chunk.chunk_type)
            group["details"].append(
                {
                    "chunk_type": chunk.chunk_type,
                    "score": score,
                    "snippet": extract_snippet(chunk.text, query_text),
                }
            )

        # 预计算每个课程的 source-level 标题匹配分（所有章节共享）
        # 标题越短、查询词占比越高 → 越可能是"关于这个词本身"的课程
        source_title_scores: Dict[str, float] = {}
        for sid, src in self.sources.items():
            st = normalize_search_text(src.title)
            s = 0.0
            if query_text == st:
                s = 200.0
            elif query_text in st:
                # 查询词在标题中的覆盖率越高，说明课程越聚焦于该主题
                coverage = len(query_text) / max(len(st), 1)
                s = 120.0 + coverage * 80.0  # 120~200 之间
            elif st in query_text:
                s = 80.0
            # 课程标题 token 命中
            st_tokens = build_search_tokens(st)
            for token in query_tokens:
                if token in st_tokens:
                    s += 15.0
            source_title_scores[sid] = s

        ranked: List[Tuple[float, Dict[str, Any]]] = []
        for group in grouped.values():
            best_score = float(group["best_score"])
            score_sum = float(group["score_sum"])
            match_count = int(group["match_count"])
            match_type_bonus = len(group["matched_in"]) * 2.5
            repeated_match_bonus = min(match_count, 3) * 0.5
            aggregate_score = best_score + max(0.0, score_sum - best_score) * 0.35
            aggregate_score += match_type_bonus + repeated_match_bonus
            # 课程级标题分：确保"关于X的介绍"课程在搜索X时始终排在前面
            # 取课程级和 chunk 级的较高者，避免重复计分
            src_id = group["source"].source_id
            src_title_score = source_title_scores.get(src_id, 0.0)
            aggregate_score = max(aggregate_score, src_title_score) + min(aggregate_score, src_title_score) * 0.3
            ranked.append((aggregate_score, group))

        ranked.sort(
            key=lambda item: (
                -item[0],
                item[1]["source"].title.lower(),
                item[1]["section"].index,
                item[1]["section"].title.lower(),
            )
        )
        items: List[Dict[str, Any]] = []
        for score, group in ranked[: max(1, min(limit, 50))]:
            source = group["source"]
            section = group["section"]
            details = sorted(
                group["details"],
                key=lambda item: (-float(item["score"]), str(item["chunk_type"]), str(item["snippet"])),
            )
            section_dict = section.to_full_dict(
                include_quizzes=include_quizzes,
                include_markdown=include_markdown,
            )
            self._resolve_section_images(source, section, section_dict)
            # 将图片以 markdown 语法追加到 content_text，方便 LLM 直接引用
            resolved_images = section_dict.get("images") or []
            if resolved_images:
                img_lines = "\n".join(
                    f'![{img.get("alt", "image")}]({img["src"]})'
                    for img in resolved_images if img.get("src", "").startswith("http")
                )
                if img_lines:
                    section_dict["content_text"] = (section_dict.get("content_text") or "") + "\n\n" + img_lines
            entry = {
                "score": round(score, 2),
                "source_id": source.source_id,
                "source_title": source.title,
                "source_type": source.source_type,
                "section_id": section.section_id,
                "section_index": section.index,
                "section_title": section.title,
                "section_type": section.section_type,
                "matched_in": sorted(group["matched_in"]),
                "match_count": int(group["match_count"]),
                "snippet": details[0]["snippet"] if details else short_text(section.content_text or section.script),
                "section": section_dict,
            }
            if include_match_details:
                entry["match_details"] = [
                    {
                        "chunk_type": item["chunk_type"],
                        "score": round(float(item["score"]), 2),
                        "snippet": item["snippet"],
                    }
                    for item in details[:3]
                ]
            items.append(entry)

        return {
            "query": query,
            "source_id": source_id,
            "count": len(items),
            "results": items,
        }


def make_tool_specs() -> Dict[str, Dict[str, Any]]:
    return {
        "kb_add_source": {
            "description": "加载课程包（含 manifest.json 的 .zip）或课程包目录到内存知识库。通常启动时已自动加载，仅在需要补充新源时调用。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        "kb_list_sources": {
            "description": "列出当前已加载的所有课程知识源。建议首次使用时先调用此工具确认知识库状态。",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        "kb_remove_source": {
            "description": "从内存知识库中移除指定的课程源。",
            "inputSchema": {
                "type": "object",
                "properties": {"source_id": {"type": "string"}},
                "required": ["source_id"],
                "additionalProperties": False,
            },
        },
        "kb_reload": {
            "description": "从磁盘重新加载指定课程源或全部课程源，用于手动刷新内容（通常目录监控会自动处理）。",
            "inputSchema": {
                "type": "object",
                "properties": {"source_id": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        "kb_get_catalog": {
            "description": "获取课程目录结构和章节概要。用于了解课程整体内容分布，不含章节正文。",
            "inputSchema": {
                "type": "object",
                "properties": {"source_id": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        "kb_search": {
            "description": "【核心工具】用自然语言问题搜索知识库，返回命中章节的完整内容（讲稿、代码、题目、图片URL）。回答用户问题前应优先调用此工具。如果章节包含图片，images[].src 为可直接访问的 HTTP 地址，请用 ![描述](src) 格式嵌入回复。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "source_id": {"type": "string"},
                    "limit": {"type": "number"},
                    "include_match_details": {"type": "boolean"},
                    "include_quizzes": {"type": "boolean"},
                    "include_markdown": {"type": "boolean"},
                    "include_content": {"type": "boolean"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        "kb_get_section": {
            "description": "读取指定章节的完整详情（讲稿、代码、题目、图片URL）。当 kb_search 结果不够详细时使用。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "section_id": {"type": "string"},
                    "section_index": {"type": "number"},
                    "include_quizzes": {"type": "boolean"},
                    "include_markdown": {"type": "boolean"},
                },
                "required": ["source_id"],
                "additionalProperties": False,
            },
        },
        "kb_read_document": {
            "description": "读取整个课程源的全文内容。format 可选：summary（目录概要）、markdown、text、json。数据量较大，建议优先使用 kb_search。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "format": {"type": "string"},
                },
                "required": ["source_id"],
                "additionalProperties": False,
            },
        },
    }


def _build_resources_list(kb: KnowledgeBase) -> Dict[str, Any]:
    """Build the resources/list response from current knowledge base state."""
    resources: List[Dict[str, Any]] = []
    # 1) 课程总览资源
    resources.append({
        "uri": "knowledge://courses",
        "name": "课程列表",
        "description": "当前已加载的所有课程概览（名称、作者、简介）",
        "mimeType": "application/json",
    })
    # 2) 每门课程的目录资源
    for source_id in sorted(kb.sources):
        source = kb.sources[source_id]
        resources.append({
            "uri": f"knowledge://courses/{source_id}/catalog",
            "name": f"{source.title} — 章节目录",
            "description": f"课程「{source.title}」的完整章节目录",
            "mimeType": "application/json",
        })
    return {"resources": resources}


def _read_resource(kb: KnowledgeBase, uri: str) -> List[Dict[str, Any]]:
    """Read a resource by URI and return a list of content items."""
    if uri == "knowledge://courses":
        items = []
        for sid in sorted(kb.sources):
            s = kb.sources[sid]
            items.append({
                "source_id": s.source_id,
                "title": s.title,
                "author": s.author,
                "description": s.description,
                "section_count": len(s.sections),
            })
        return [{"uri": uri, "mimeType": "application/json", "text": json_pretty({"courses": items})}]

    # knowledge://courses/{source_id}/catalog
    prefix = "knowledge://courses/"
    suffix = "/catalog"
    if uri.startswith(prefix) and uri.endswith(suffix):
        source_id = uri[len(prefix):-len(suffix)]
        source = kb.sources.get(source_id)
        if not source:
            raise ValueError(f"source not found: {source_id}")
        sections = []
        for sec in source.sections:
            sections.append({
                "section_id": sec.section_id,
                "index": sec.index,
                "title": sec.title,
                "level": sec.level,
                "has_script": bool(sec.script.strip()),
                "has_code": bool(sec.code_text.strip()),
                "quiz_count": len(sec.quizzes),
            })
        payload = {
            "source_id": source.source_id,
            "title": source.title,
            "author": source.author,
            "description": source.description,
            "sections": sections,
        }
        return [{"uri": uri, "mimeType": "application/json", "text": json_pretty(payload)}]

    raise ValueError(f"unknown resource URI: {uri}")


def make_tools_list(tool_specs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    tools = []
    for name, spec in tool_specs.items():
        tools.append(
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
            }
        )
    return {"tools": tools}


def tool_call(kb: KnowledgeBase, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name == "kb_add_source":
        path = str(args.get("path") or "").strip()
        if not path:
            raise ValueError("path is required")
        recursive = parse_bool(args.get("recursive"), True)
        return kb.add_source_path(path, recursive=recursive)

    if tool_name == "kb_list_sources":
        return kb.list_sources()

    if tool_name == "kb_remove_source":
        source_id = str(args.get("source_id") or "").strip()
        if not source_id:
            raise ValueError("source_id is required")
        return kb.remove_source(source_id)

    if tool_name == "kb_reload":
        return kb.reload(str(args.get("source_id") or "").strip())

    if tool_name == "kb_get_catalog":
        return kb.get_catalog(str(args.get("source_id") or "").strip())

    if tool_name == "kb_search":
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        source_id = str(args.get("source_id") or "").strip()
        limit = int(args.get("limit") or 5)
        include_match_details = parse_bool(
            args.get("include_match_details"),
            parse_bool(args.get("include_content"), False),
        )
        include_quizzes = parse_bool(args.get("include_quizzes"), True)
        include_markdown = parse_bool(args.get("include_markdown"), False)
        return kb.search(
            query,
            source_id=source_id,
            limit=limit,
            include_match_details=include_match_details,
            include_quizzes=include_quizzes,
            include_markdown=include_markdown,
        )

    if tool_name == "kb_get_section":
        source_id = str(args.get("source_id") or "").strip()
        if not source_id:
            raise ValueError("source_id is required")
        section_id = str(args.get("section_id") or "").strip()
        raw_index = args.get("section_index")
        section_index = None if raw_index is None or str(raw_index).strip() == "" else int(raw_index)
        include_quizzes = parse_bool(args.get("include_quizzes"), True)
        include_markdown = parse_bool(args.get("include_markdown"), False)
        return kb.get_section(
            source_id,
            section_id=section_id,
            section_index=section_index,
            include_quizzes=include_quizzes,
            include_markdown=include_markdown,
        )

    if tool_name == "kb_read_document":
        source_id = str(args.get("source_id") or "").strip()
        if not source_id:
            raise ValueError("source_id is required")
        fmt = str(args.get("format") or "summary").strip()
        return kb.read_document(source_id, fmt)

    raise ValueError(f"unknown tool: {tool_name}")


def run_mcp_loop(kb: KnowledgeBase) -> None:
    specs = make_tool_specs()
    tools_payload = make_tools_list(specs)

    while True:
        msg = read_framed_message()
        if msg is None:
            return

        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params") or {}

        if not method:
            if msg_id is not None:
                write_error(msg_id, -32600, "invalid request")
            continue

        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Fay 课程知识库检索服务。\n\n"
                    "【核心规则】回答用户问题前，务必先调用 kb_search 检索知识库，基于结果回答，不要猜测。\n\n"
                    "【使用流程】\n"
                    "直接调用 kb_search（用户原句即可） → 基于返回的章节内容回答。\n"
                    "如果结果中 images 不为空，src 是可访问的 HTTP 图片地址，请用 Markdown 图片语法 ![描述](src) 嵌入回复中展示给用户。\n\n"
                    "【其他工具】仅在需要时使用：\n"
                    "- kb_list_sources / kb_add_source — 知识库为空时排查和补充\n"
                    "- kb_get_section — 需要精确读取某章节详情时\n"
                    "- kb_get_catalog — 需要了解课程目录结构时"
                ),
            }
            if msg_id is not None:
                write_response(msg_id, result)
            continue

        if method == "notifications/initialized":
            continue

        if method == "ping":
            if msg_id is not None:
                write_response(msg_id, {"pong": True})
            continue

        if method == "resources/list":
            if msg_id is not None:
                write_response(msg_id, _build_resources_list(kb))
            continue

        if method == "resources/read":
            if msg_id is not None:
                uri = str(params.get("uri") or "").strip()
                try:
                    contents = _read_resource(kb, uri)
                    write_response(msg_id, {"contents": contents})
                except Exception as exc:
                    write_error(msg_id, -32602, f"resource read failed: {exc}")
            continue

        if method == "tools/list":
            if msg_id is not None:
                write_response(msg_id, tools_payload)
            continue

        if method == "tools/call":
            if msg_id is None:
                continue
            name = str(params.get("name") or "").strip()
            arguments = params.get("arguments") or {}
            if not isinstance(arguments, dict):
                arguments = {}
            try:
                result = tool_call(kb, name, arguments)
                write_response(
                    msg_id,
                    {"content": [{"type": "text", "text": json_pretty(result)}], "isError": False},
                )
            except Exception as exc:
                write_response(
                    msg_id,
                    {
                        "content": [{"type": "text", "text": f"ERROR: {exc}"}],
                        "isError": True,
                    },
                )
            continue

        if msg_id is not None:
            write_error(msg_id, -32601, f"method not found: {method}")


def preload_sources(kb: KnowledgeBase, source_paths: Sequence[str], recursive: bool) -> None:
    for item in source_paths:
        try:
            result = kb.add_source_path(item, recursive=recursive)
            loaded_count = int(result.get("loaded_count") or 0)
            skipped_count = int(result.get("skipped_count") or 0)
            write_stderr(
                f"[{SERVER_NAME}] preloaded {item} (loaded={loaded_count}, skipped={skipped_count})"
            )
        except Exception as exc:
            write_stderr(f"[{SERVER_NAME}] preload failed for {item}: {exc}")


def _snapshot_directory(source_paths: Sequence[str], recursive: bool) -> Dict[str, float]:
    """Build a dict mapping resolved zip file paths to their mtime."""
    snapshot: Dict[str, float] = {}
    for item in source_paths:
        path = Path(item).expanduser().resolve()
        if path.is_file() and path.suffix.lower() in ZIP_EXTS:
            try:
                snapshot[str(path)] = os.path.getmtime(path)
            except OSError:
                pass
        elif path.is_dir():
            for discovered in discover_source_files(path, recursive):
                try:
                    snapshot[str(discovered)] = os.path.getmtime(discovered)
                except OSError:
                    pass
    return snapshot


def _start_directory_watcher(
    kb: KnowledgeBase,
    source_paths: Sequence[str],
    recursive: bool,
    interval: float = 60.0,
) -> threading.Event:
    """Start a daemon thread that re-scans source directories every `interval` seconds.

    Returns a threading.Event that can be set to stop the watcher.
    """
    stop_event = threading.Event()
    last_snapshot: Dict[str, float] = _snapshot_directory(source_paths, recursive)

    def _watcher() -> None:
        nonlocal last_snapshot
        while not stop_event.is_set():
            stop_event.wait(interval)
            if stop_event.is_set():
                break
            try:
                current = _snapshot_directory(source_paths, recursive)
                if current == last_snapshot:
                    continue
                # Detect added / changed files
                changed_paths: List[str] = []
                for fpath, mtime in current.items():
                    if fpath not in last_snapshot or last_snapshot[fpath] != mtime:
                        changed_paths.append(fpath)
                # Detect removed files
                removed_paths = set(last_snapshot) - set(current)

                if changed_paths:
                    write_stderr(
                        f"[{SERVER_NAME}] directory watcher: {len(changed_paths)} file(s) changed/added, reloading..."
                    )
                    for fpath in changed_paths:
                        try:
                            source = load_source_from_path(Path(fpath))
                            kb.sources[source.source_id] = source
                            write_stderr(f"[{SERVER_NAME}]   loaded: {Path(fpath).name}")
                        except Exception as exc:
                            write_stderr(f"[{SERVER_NAME}]   failed: {Path(fpath).name}: {exc}")

                if removed_paths:
                    write_stderr(
                        f"[{SERVER_NAME}] directory watcher: {len(removed_paths)} file(s) removed"
                    )
                    ids_to_remove = []
                    for sid, src in kb.sources.items():
                        if src.path in removed_paths:
                            ids_to_remove.append(sid)
                    for sid in ids_to_remove:
                        removed_src = kb.sources.pop(sid, None)
                        if removed_src:
                            write_stderr(f"[{SERVER_NAME}]   removed: {removed_src.source_name}")

                if changed_paths or removed_paths:
                    kb._rebuild_chunk_index()

                last_snapshot = current
            except Exception as exc:
                write_stderr(f"[{SERVER_NAME}] directory watcher error: {exc}")

    thread = threading.Thread(target=_watcher, daemon=True, name="kb-dir-watcher")
    thread.start()
    write_stderr(f"[{SERVER_NAME}] directory watcher started (interval={int(interval)}s)")
    return stop_event


def main() -> int:
    global _image_cache_dir, _image_base_url

    parser = argparse.ArgumentParser(description="Fay course knowledge base MCP server (native course zip only)")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Course zip file or directory to preload. Repeat this option to add multiple sources.",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Disable recursive discovery when --source points to a directory.",
    )
    parser.add_argument(
        "--watch-interval",
        type=int,
        default=60,
        help="Directory re-scan interval in seconds (default: 60). Set to 0 to disable.",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="",
        help="Directory for cached image files. Defaults to a temp directory.",
    )
    parser.add_argument(
        "--image-port",
        type=int,
        default=DEFAULT_IMAGE_PORT,
        help=f"Port for the image HTTP server (default: {DEFAULT_IMAGE_PORT}). Set to 0 to disable.",
    )
    parser.add_argument(
        "--fay-url",
        type=str,
        default="http://127.0.0.1:5000",
        help="Fay local service URL. Used for embedding via /v1/embeddings passthrough.",
    )
    args = parser.parse_args()

    # 初始化 embedding（通过 Fay 透传）
    global _fay_url
    if args.fay_url:
        _fay_url = args.fay_url.rstrip("/")
        write_stderr(f"[{SERVER_NAME}] embedding 已启用 (via Fay passthrough): {_fay_url}/v1/embeddings")
    else:
        write_stderr(f"[{SERVER_NAME}] embedding 未配置，仅使用 token 匹配")

    # Set up image cache and HTTP server
    if args.image_port != 0:
        if args.cache_dir:
            _image_cache_dir = Path(args.cache_dir).expanduser().resolve()
            _image_cache_dir.mkdir(parents=True, exist_ok=True)
        else:
            _image_cache_dir = Path(tempfile.mkdtemp(prefix="fay_kb_images_"))
        actual_port = _start_image_http_server(_image_cache_dir, args.image_port)
        _image_base_url = f"http://127.0.0.1:{actual_port}"
        write_stderr(f"[{SERVER_NAME}] image cache dir: {_image_cache_dir}")

    kb = KnowledgeBase()
    recursive = not args.no_recursive
    preload_sources(kb, args.source, recursive=recursive)
    write_stderr(f"[{SERVER_NAME}] ready with {len(kb.sources)} source(s)")

    stop_event = None
    if args.source and args.watch_interval > 0:
        stop_event = _start_directory_watcher(kb, args.source, recursive, float(args.watch_interval))

    write_stderr(f"[{SERVER_NAME}] waiting for MCP stdio messages...")

    try:
        run_mcp_loop(kb)
    except KeyboardInterrupt:
        pass
    finally:
        if stop_event:
            stop_event.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

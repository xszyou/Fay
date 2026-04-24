"""
core/memory_service.py

Fay 记忆操作的唯一权威入口。
=====================================
设计动机：
    过去，"写入/检索一条记忆" 这件事散落在多处：
      * 对话线程里 (`remember_conversation_thread`)
      * 观察线程里 (`remember_observation_thread`)
      * 夜间画像/反思任务里 (`perform_user_portrait_analysis` / `perform_daily_reflection`)
      * 未来还会被 MCP server、flask_server、前端 API 调用
    如果每个调用点都直接操作 `agent.memory_stream`，就会出现：
      * 打 tag 的规范不一致（外部 agent 可能漏打 `kind:` 或 `source:`）
      * 落盘时机散乱（有人只写内存，有人立刻刷盘）
      * 画像/反思字段读取方式不统一
    本模块把这些操作收拢成薄适配层：
      * 规范化 tags（按 `kind:/source:/persistent:/...` 命名空间）
      * 走既有的 `create_agent` → `append_prepared_node` 通道
      * 对外暴露简单函数：remember / search / get_recent / get_active_rules /
        get_reflections / get_user_profile / get_schema
    `faymcp/mcp_server.py` 的记忆工具和 Fay 内部流程都应只依赖本模块，
    而不是直接碰 `memory_stream` 或 `agents` 字典。

与既有代码的关系：
    - 不取代 `remember_conversation_thread`：对话内容的归档仍走原路径，
      那里做了"先算 importance/embedding，后持锁"的拆分，是对话延迟敏感
      路径，保持现状。
    - 新的外部写入（外部 agent/MCP/前端 API）全部走本模块 remember()。
      本模块内部也做了"先算 importance/embedding，后持锁"的拆分，并会
      在持锁期间立刻把 nodes.json / embeddings.json 刷盘，避免 Fay 异常
      重启丢失外部写入。
"""

from __future__ import annotations

import os
import json
import threading
from typing import Iterable

from utils import util

# 走既有的 agent / memory_stream / member_db 通道，避免重复实现。
# 这些都是现成函数：
#   - create_agent / get_user_memory_dir / agent_lock / get_current_time_step
#     来自 llm/nlp_cognitive_stream.py
#   - get_text_embedding / generate_importance_score 在同一处被封装
from llm import nlp_cognitive_stream as ncs
from genagents.modules.memory_stream import (
    generate_importance_score,
)
from simulation_engine.gpt_structure import get_text_embedding
from core import member_db


# -----------------------------------------------------------------------------
# Schema：kind 枚举 + tag 命名空间规范
# -----------------------------------------------------------------------------

# kind 是"记忆本身是什么"的粗分类，枚举固定。外部 agent 只能选其中之一。
KIND_ENUM = [
    "decision",    # 决策/选择了某个方案
    "event",       # 发生了一件事（已完成/已观察）
    "fact",        # 一条中立的事实
    "rule",        # 一条应长期生效的规则/约束
    "error",       # 出错/失败的经历
    "insight",     # 反思/洞察/总结（一般由 fay 反思生成，也可由外部 agent 写入）
    "preference",  # 用户或主体的偏好
    "observation", # 观察（默认值，当外部 agent 拿不准选哪个时用）
]

# tag 命名空间约定：所有 tag 建议带前缀，便于检索与过滤。
#   kind:<KIND_ENUM>              —— 由本模块根据参数自动打，不要手填
#   source:<来源标识>             —— 谁写入的：fay_self / claude_code / cursor / user / fay_reflection / ...
#   persistent:true               —— 对 kind=rule 表示常驻提醒；对其他 kind 表示该条记忆值得长期保留
#   domain:<领域>                 —— 业务领域，如 quant / homecare / education / companion / life_assistant
#   strategy:<策略名>             —— 量化/工程场景下的策略标识
#   symbol:<标的/实体>            —— 股票代码、设备编号、学员编号等
#   session:<会话ID>              —— 某次外部 agent 会话的标识，便于事后串起来看
#   schedule:<表达式>             —— 如 "hourly" / "daily" / "cron:0 * * * *"，提醒何时触发
#   date:<YYYY-MM-DD>             —— 发生日期（由调用方或本模块按需打）
TAG_NAMESPACES = [
    "kind", "source", "persistent", "domain", "strategy",
    "symbol", "session", "schedule", "date",
]


def get_schema() -> dict:
    """返回 kind 枚举和 tag 命名空间规范，供 MCP 工具描述或外部 agent 查询。"""
    return {
        "kind_enum": list(KIND_ENUM),
        "tag_namespaces": list(TAG_NAMESPACES),
        "notes": (
            "所有 tag 建议带 `<namespace>:<value>` 前缀。kind 必须从 kind_enum 里选；"
            "kind=rule 时应同时设置 persistent=true，才会被 get_active_rules 检索到。"
            "fay 适用于多种数字人场景——量化交易、居家养老陪伴、教育辅导、生活助理、智能家居等——"
            "`domain:` tag 用于区分业务领域。"
        ),
    }


# -----------------------------------------------------------------------------
# Tag 规范化
# -----------------------------------------------------------------------------

def _normalize_tags(
    kind: str | None,
    source: str | None,
    persistent: bool | None,
    extra_tags: Iterable[str] | None,
) -> list[str]:
    """把结构化参数 + extra_tags 合成一份去重排序后的 tag 列表。

    kind 不合法时会退到 'observation' 并发 warn 日志，而不是抛异常——外部
    agent 可能偶尔传来新 kind，宁可写入、打警告，也不要让记忆丢失。
    """
    tags: set[str] = set()

    if kind:
        k = str(kind).strip().lower()
        if k not in KIND_ENUM:
            util.log(1, f"[memory_service] 未知 kind='{kind}'，按 observation 写入并标记 kind:unknown")
            tags.add("kind:observation")
            tags.add(f"kind:unknown:{k}")
        else:
            tags.add(f"kind:{k}")

    if source:
        s = str(source).strip()
        if s:
            tags.add(f"source:{s}")

    if persistent:
        tags.add("persistent:true")

    if extra_tags:
        for t in extra_tags:
            if not isinstance(t, str):
                continue
            t = t.strip()
            if t:
                tags.add(t)

    return sorted(tags)


# -----------------------------------------------------------------------------
# 落盘
# -----------------------------------------------------------------------------

_flush_lock = threading.Lock()


def _flush_agent_to_disk(username: str | None, agent) -> None:
    """把 agent 的 memory_stream 序列化到磁盘。外部写入路径专用。

    - 夜间定时任务有自己的落盘逻辑，因此我们只在外部 remember() 调用时触发本函数，
      防止高频写入撞车。
    - 不持 agent_lock：调用方已经在持锁期间完成了内存修改，这里只是 I/O。
    """
    try:
        memory_dir = ncs.get_user_memory_dir(username)
        memory_stream_dir = os.path.join(memory_dir, "memory_stream")
        os.makedirs(memory_stream_dir, exist_ok=True)

        nodes_data = []
        for node in agent.memory_stream.seq_nodes:
            if node is not None and hasattr(node, "package"):
                try:
                    nodes_data.append(node.package())
                except Exception as e:
                    util.log(1, f"[memory_service] 打包节点失败: {str(e)}")

        with _flush_lock:
            with open(os.path.join(memory_stream_dir, "nodes.json"), "w", encoding="utf-8") as f:
                json.dump(nodes_data, f, ensure_ascii=False, indent=2)
            with open(os.path.join(memory_stream_dir, "embeddings.json"), "w", encoding="utf-8") as f:
                json.dump(agent.memory_stream.embeddings or {}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        util.log(1, f"[memory_service] 落盘失败: {str(e)}")


# -----------------------------------------------------------------------------
# 对外 API
# -----------------------------------------------------------------------------

def remember(
    username: str | None,
    content: str,
    *,
    kind: str | None = "observation",
    source: str | None = None,
    persistent: bool = False,
    extra_tags: Iterable[str] | None = None,
    node_type: str = "observation",
    flush: bool = True,
) -> dict:
    """写入一条记忆节点。

    参数:
        username: 目标用户。None 走全局/默认用户。
        content: 记忆文本。
        kind: 从 KIND_ENUM 选一个。默认 observation。
        source: 来源标识（fay_self / claude_code / cursor / user / ...）。
        persistent: 是否长期保留。kind=rule 时应显式传 True。
        extra_tags: 额外 tag（建议带命名空间前缀，如 "domain:quant", "symbol:AAPL"）。
        node_type: memory_stream 的节点类型：observation / conversation / reflection。
            外部调用一般用 observation。
        flush: 是否立刻把 nodes.json / embeddings.json 刷到磁盘。默认 True。

    返回:
        {"ok": True, "node_id": int, "tags": [...]}  或  {"ok": False, "error": "..."}
    """
    if not content or not str(content).strip():
        return {"ok": False, "error": "content 为空"}

    text = str(content).strip()
    tags = _normalize_tags(kind, source, persistent, extra_tags)

    # 1) 锁外：算 importance 与 embedding，避免阻塞其它对话流程
    try:
        importance = generate_importance_score([text])[0]
    except Exception as e:
        util.log(1, f"[memory_service] 生成 importance 失败，使用默认值: {str(e)}")
        importance = 1
    try:
        embedding = get_text_embedding(text)
    except Exception as e:
        util.log(1, f"[memory_service] 生成 embedding 失败，使用空向量: {str(e)}")
        embedding = []

    # 2) 持锁：写内存数据结构
    try:
        agent = ncs.create_agent(username)
        if agent is None or agent.memory_stream is None:
            return {"ok": False, "error": "agent 未就绪"}
        with ncs.agent_lock:
            time_step = ncs.get_current_time_step(username)
            ms = agent.memory_stream
            new_node = ms.append_prepared_node(
                time_step, node_type, text, importance, embedding,
                pointer_id=None, tags=tags,
            )
    except Exception as e:
        util.log(1, f"[memory_service] 写入记忆失败: {str(e)}")
        return {"ok": False, "error": str(e)}

    # 3) 锁外：落盘
    if flush:
        _flush_agent_to_disk(username, agent)

    return {
        "ok": True,
        "node_id": getattr(new_node, "node_id", None),
        "tags": tags,
        "importance": importance,
    }


def search(
    username: str | None,
    query: str,
    *,
    n: int = 10,
    filter_tags_all: Iterable[str] | None = None,
    filter_tags_any: Iterable[str] | None = None,
    node_type: str = "all",
) -> list[dict]:
    """按语义相关度（默认权重）检索记忆，支持 tag AND/OR 过滤。"""
    if not query or not str(query).strip():
        return []
    try:
        agent = ncs.create_agent(username)
        if agent is None or agent.memory_stream is None:
            return []
        with ncs.agent_lock:
            time_step = ncs.get_current_time_step(username)
            retrieved = agent.memory_stream.retrieve(
                [query], time_step, n_count=n, curr_filter=node_type,
                stateless=True,
                filter_tags_all=list(filter_tags_all) if filter_tags_all else None,
                filter_tags_any=list(filter_tags_any) if filter_tags_any else None,
            )
        nodes = retrieved.get(query, [])
        return [_node_to_dict(n) for n in nodes]
    except Exception as e:
        util.log(1, f"[memory_service] 检索记忆失败: {str(e)}")
        return []


def get_recent(
    username: str | None,
    *,
    n: int = 20,
    filter_tags_all: Iterable[str] | None = None,
    node_type: str = "all",
) -> list[dict]:
    """按时间倒序返回最近 N 条记忆，可选 tag 过滤。"""
    try:
        agent = ncs.create_agent(username)
        if agent is None or agent.memory_stream is None:
            return []
        with ncs.agent_lock:
            seq = list(agent.memory_stream.seq_nodes)
        if node_type != "all":
            seq = [x for x in seq if x.node_type == node_type]
        if filter_tags_all:
            req = set(filter_tags_all)
            seq = [x for x in seq if req.issubset(set(x.tags or []))]
        seq = sorted(seq, key=lambda x: x.created, reverse=True)[:n]
        return [_node_to_dict(x) for x in seq]
    except Exception as e:
        util.log(1, f"[memory_service] 获取最近记忆失败: {str(e)}")
        return []


def get_active_rules(username: str | None, *, n: int = 50) -> list[dict]:
    """返回所有 `kind:rule` + `persistent:true` 的记忆，按重要度倒序。

    这是"请在每小时检查策略有无问题"之类的长期指令的主要出口，
    外部 agent 或 fay 本身在每次对话/每次轮询前可以拉一次。
    """
    try:
        agent = ncs.create_agent(username)
        if agent is None or agent.memory_stream is None:
            return []
        with ncs.agent_lock:
            seq = list(agent.memory_stream.seq_nodes)
        required = {"kind:rule", "persistent:true"}
        matched = [x for x in seq if required.issubset(set(x.tags or []))]
        matched = sorted(matched, key=lambda x: (x.importance, x.created), reverse=True)[:n]
        return [_node_to_dict(x) for x in matched]
    except Exception as e:
        util.log(1, f"[memory_service] 获取活跃规则失败: {str(e)}")
        return []


def get_reflections(username: str | None, *, n: int = 10) -> list[dict]:
    """返回最近的反思节点（kind:insight + source:fay_reflection）。"""
    try:
        agent = ncs.create_agent(username)
        if agent is None or agent.memory_stream is None:
            return []
        with ncs.agent_lock:
            seq = list(agent.memory_stream.seq_nodes)
        matched = [
            x for x in seq
            if x.node_type == "reflection"
            or "kind:insight" in (x.tags or [])
        ]
        matched = sorted(matched, key=lambda x: x.created, reverse=True)[:n]
        return [_node_to_dict(x) for x in matched]
    except Exception as e:
        util.log(1, f"[memory_service] 获取反思失败: {str(e)}")
        return []


def get_user_profile(username: str | None) -> dict:
    """从 T_Member 取 portrait 与 extra_info，打成统一结构。"""
    try:
        db = member_db.new_instance()
        user = username or "User"
        portrait = db.get_user_portrait(user) or ""
        extra = db.get_extra_info(user) or ""
        return {"username": user, "portrait": portrait, "extra_info": extra}
    except Exception as e:
        util.log(1, f"[memory_service] 获取用户画像失败: {str(e)}")
        return {"username": username, "portrait": "", "extra_info": "", "error": str(e)}


# -----------------------------------------------------------------------------
# 内部工具
# -----------------------------------------------------------------------------

def _node_to_dict(node) -> dict:
    """把 ConceptNode 转成对外的轻量 dict（不包含 embedding）。"""
    return {
        "node_id": getattr(node, "node_id", None),
        "node_type": getattr(node, "node_type", ""),
        "content": getattr(node, "content", ""),
        "importance": getattr(node, "importance", 0),
        "datetime": getattr(node, "datetime", ""),
        "created": getattr(node, "created", 0),
        "pointer_id": getattr(node, "pointer_id", None),
        "tags": list(getattr(node, "tags", []) or []),
    }

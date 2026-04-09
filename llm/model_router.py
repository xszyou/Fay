# -*- coding: utf-8 -*-
"""
大小模型交互路由模块

设计思路：
- 小模型（轻量/低成本）：处理简单问答、闲聊、意图识别等低复杂度任务
- 大模型（强推理）：处理复杂推理、工具编排、多步规划、长文生成等高复杂度任务
- 路由器：基于规则的本地分类，零额外 LLM 调用开销

路由策略（规则优先，不依赖小模型返回置信度）：
1. 有 MCP 工具可用时 → 大模型（工具编排需要强推理）
2. 命中"升级关键词"时 → 大模型（用户明确要求深度处理）
3. 文本长度 / 问号数量超阈值 → 大模型（复杂多步问题）
4. 其余情况 → 小模型
"""

import re
import threading
from typing import Optional, Tuple, Literal

from langchain_openai import ChatOpenAI

from utils import util
import utils.config_util as cfg

# 路由决策类型
RouteDecision = Literal["small", "large"]

# 模块级锁，保护 LLM 实例的懒加载
_init_lock = threading.Lock()

# 懒加载的模型实例
_small_llm: Optional[ChatOpenAI] = None
_large_llm: Optional[ChatOpenAI] = None

# 上次初始化时使用的配置指纹，用于检测配置变更后重建实例
_small_llm_fingerprint: Optional[str] = None
_large_llm_fingerprint: Optional[str] = None

# ─── 规则路由配置 ───────────────────────────────────────────

# 命中任一关键词 → 升级到大模型
_UPGRADE_KEYWORDS = {
    # 深度分析类
    "详细分析", "深入分析", "深入讲解", "详细解释", "深度解读",
    "帮我分析", "系统分析", "全面分析", "仔细分析",
    # 代码 / 技术类
    "写代码", "写个代码", "编程", "代码", "debug", "调试",
    "bug", "报错", "函数", "算法", "脚本", "编译",
    "python", "java", "javascript", "sql", "html", "css",
    # 长文创作类
    "写一篇", "写篇", "帮我写", "写个方案", "写个报告",
    "写论文", "写文章", "写总结", "写计划", "写邮件",
    "翻译", "翻译一下", "帮我翻译",
    # 推理 / 数学类
    "推理", "证明", "计算", "求解", "数学",
    "逻辑", "为什么会", "原因是什么", "怎么推导",
    # 对比 / 总结类
    "对比", "比较", "区别是什么", "优缺点",
    "总结一下", "归纳", "梳理",
    # 工具 / 搜索类
    "搜索", "查一下", "帮我查", "搜一下", "上网",
}

# 命中任一正则 → 升级到大模型
_UPGRADE_PATTERNS = [
    re.compile(r"(帮我|请).{0,4}(写|生成|创建|设计|制作|画|做)"),  # "帮我写..."
    re.compile(r"如何.{2,}"),           # "如何实现..." 通常是技术问题
    re.compile(r"怎么.{4,}"),           # "怎么用Python..." 较长说明复杂
    re.compile(r"\d+[\+\-\*\/\^]\d+"),  # 数学表达式
    re.compile(r"```"),                 # 包含代码块
    re.compile(r"step.by.step|一步一步|逐步", re.IGNORECASE),
]

# 输入文本长度阈值：超过此字符数认为是复杂请求
_LENGTH_THRESHOLD = 100

# 问号数量阈值：多个问号通常意味着多步问题
_QUESTION_MARK_THRESHOLD = 2


def _build_fingerprint(api_key: Optional[str], base_url: Optional[str], model: Optional[str]) -> str:
    """构建配置指纹，用于检测配置变更。"""
    return f"{api_key}|{base_url}|{model}"


def _ensure_small_llm() -> Optional[ChatOpenAI]:
    """懒加载并返回小模型实例，配置变更时自动重建。"""
    global _small_llm, _small_llm_fingerprint

    api_key = cfg.small_model_api_key
    base_url = cfg.small_model_base_url
    model = cfg.small_model_engine

    if not all([api_key, base_url, model]):
        return None

    fp = _build_fingerprint(api_key, base_url, model)
    if _small_llm is not None and _small_llm_fingerprint == fp:
        return _small_llm

    with _init_lock:
        # double-check
        if _small_llm is not None and _small_llm_fingerprint == fp:
            return _small_llm
        try:
            _small_llm = ChatOpenAI(
                model=model,
                base_url=base_url,
                api_key=api_key,
                streaming=True,
            )
            _small_llm_fingerprint = fp
            util.log(1, f"小模型已初始化: {model} @ {base_url}")
        except Exception as exc:
            util.log(1, f"小模型初始化失败: {exc}")
            _small_llm = None
    return _small_llm


def _ensure_large_llm() -> Optional[ChatOpenAI]:
    """懒加载并返回大模型实例（即原有的主模型），配置变更时自动重建。"""
    global _large_llm, _large_llm_fingerprint

    api_key = cfg.key_gpt_api_key
    base_url = cfg.gpt_base_url
    model = cfg.gpt_model_engine

    if not all([api_key, base_url, model]):
        return None

    fp = _build_fingerprint(api_key, base_url, model)
    if _large_llm is not None and _large_llm_fingerprint == fp:
        return _large_llm

    with _init_lock:
        if _large_llm is not None and _large_llm_fingerprint == fp:
            return _large_llm
        try:
            _large_llm = ChatOpenAI(
                model=model,
                base_url=base_url,
                api_key=api_key,
                streaming=True,
            )
            _large_llm_fingerprint = fp
            util.log(1, f"大模型已初始化: {model} @ {base_url}")
        except Exception as exc:
            util.log(1, f"大模型初始化失败: {exc}")
            _large_llm = None
    return _large_llm


def is_enabled() -> bool:
    """检查大小模型交互功能是否已启用且配置完整。"""
    cfg.load_config()
    if not cfg.model_interaction_enabled:
        return False
    # 小模型必须有独立配置
    if not all([cfg.small_model_api_key, cfg.small_model_base_url, cfg.small_model_engine]):
        return False
    # 大模型（主模型）必须有配置
    if not all([cfg.key_gpt_api_key, cfg.gpt_base_url, cfg.gpt_model_engine]):
        return False
    return True


def classify_request(content: str, has_tools: bool = False) -> Tuple[RouteDecision, str]:
    """
    基于规则对用户请求进行路由分类，零额外 LLM 调用。

    Args:
        content: 用户输入文本
        has_tools: 当前是否有可用的 MCP 工具

    Returns:
        (route_decision, reason)
        - route_decision: "small" 或 "large"
        - reason: 分类理由
    """
    # 规则 1：有工具可用 → 大模型
    if has_tools:
        return "large", "检测到可用工具，需要大模型进行工具编排"

    if not content or not content.strip():
        return "small", "空输入，小模型处理"

    text = content.strip()

    # 规则 2：关键词命中 → 大模型
    text_lower = text.lower()
    for kw in _UPGRADE_KEYWORDS:
        if kw in text_lower:
            return "large", f"命中升级关键词: {kw}"

    # 规则 3：正则模式命中 → 大模型
    for pattern in _UPGRADE_PATTERNS:
        if pattern.search(text):
            return "large", f"命中升级模式: {pattern.pattern}"

    # 规则 4：文本过长 → 大模型（长输入通常意味着复杂需求）
    if len(text) > _LENGTH_THRESHOLD:
        return "large", f"输入长度({len(text)})超过阈值({_LENGTH_THRESHOLD})"

    # 规则 5：多个问号 → 大模型（多个子问题）
    question_marks = text.count("?") + text.count("？")
    if question_marks >= _QUESTION_MARK_THRESHOLD:
        return "large", f"检测到{question_marks}个问号，可能是多步问题"

    # 默认 → 小模型
    return "small", "未命中升级规则，小模型处理"


def get_llm_for_route(route: RouteDecision) -> ChatOpenAI:
    """
    根据路由决策返回对应的 LLM 实例。

    Args:
        route: "small" 或 "large"

    Returns:
        ChatOpenAI 实例
    """
    if route == "small":
        llm = _ensure_small_llm()
        if llm is not None:
            return llm
        util.log(1, "[路由] 小模型不可用，回退到大模型")

    llm = _ensure_large_llm()
    if llm is not None:
        return llm

    # 最终兜底：使用模块级的全局 llm（原有逻辑）
    util.log(1, "[路由] 大小模型均不可用，使用全局 llm 实例")
    from llm.nlp_cognitive_stream import llm as global_llm
    return global_llm


def get_route_info() -> dict:
    """返回当前路由配置状态信息，供 API / 调试使用。"""
    cfg.load_config()
    return {
        "enabled": is_enabled(),
        "model_interaction_enabled": bool(cfg.model_interaction_enabled),
        "small_model": {
            "engine": cfg.small_model_engine,
            "base_url": cfg.small_model_base_url,
            "configured": bool(cfg.small_model_engine and cfg.small_model_base_url and cfg.small_model_api_key),
        },
        "large_model": {
            "engine": cfg.gpt_model_engine,
            "base_url": cfg.gpt_base_url,
            "configured": bool(cfg.gpt_model_engine and cfg.gpt_base_url and cfg.key_gpt_api_key),
        },
    }

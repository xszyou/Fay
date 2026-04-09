# -*- coding: utf-8 -*-
"""
大小模型交互路由模块

路由逻辑非常简单：
- 有 MCP 工具需要调用 → 大模型（工具编排需要强推理能力）
- 纯对话无工具 → 小模型（轻量快速，降低成本）
"""

import threading
from typing import Optional, Literal

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
    if not all([cfg.small_model_api_key, cfg.small_model_base_url, cfg.small_model_engine]):
        return False
    if not all([cfg.key_gpt_api_key, cfg.gpt_base_url, cfg.gpt_model_engine]):
        return False
    return True


def classify_request(has_tools: bool = False) -> RouteDecision:
    """
    根据是否有工具可用决定路由。

    Args:
        has_tools: 当前是否有可用的 MCP 工具

    Returns:
        "small" 或 "large"
    """
    if has_tools:
        return "large"
    return "small"


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

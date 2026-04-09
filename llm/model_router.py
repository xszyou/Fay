# -*- coding: utf-8 -*-
"""
大小模型交互路由模块

设计思路：
- 小模型（轻量/低成本）：处理简单问答、闲聊、意图识别等低复杂度任务
- 大模型（强推理）：处理复杂推理、工具编排、多步规划、长文生成等高复杂度任务
- 路由器：基于小模型的意图分类结果，决定由哪个模型处理当前请求

路由策略：
1. 小模型先对用户输入进行意图分类和复杂度评估
2. 简单任务（闲聊、问候、简单事实问答）由小模型直接回复
3. 复杂任务（推理、工具调用、代码、分析）升级到大模型处理
4. 小模型置信度不足时主动升级到大模型
"""

import json
import threading
from typing import Optional, Tuple, Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

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


ROUTE_CLASSIFY_PROMPT = """\
你是一个任务复杂度分类器。根据用户的输入，判断该任务应该由"小模型"还是"大模型"处理。

## 分类标准

**小模型处理（输出 "small"）**：
- 日常问候、闲聊、打招呼
- 简单事实性问答（天气、时间、基础常识）
- 简短的情感回应、安慰、鼓励
- 简单的信息查询或确认
- 上下文不复杂的简短对话

**大模型处理（输出 "large"）**：
- 需要多步推理或逻辑分析的问题
- 代码编写、调试、技术问题
- 需要调用工具/搜索/计算的任务
- 长文创作、文案撰写、翻译
- 复杂的数据分析或总结
- 涉及专业领域知识的深度问答
- 用户明确要求"详细分析"、"深入讲解"等
- 多轮追问、需要综合上下文的复杂对话

## 输出格式

严格按照以下JSON格式输出，不要输出任何其他内容：
{"route": "small"或"large", "confidence": 0.0到1.0之间的数字, "reason": "简短的分类理由"}
"""


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


def classify_request(content: str, has_tools: bool = False) -> Tuple[RouteDecision, float, str]:
    """
    使用小模型对用户请求进行意图分类，决定路由方向。

    Args:
        content: 用户输入文本
        has_tools: 当前是否有可用的 MCP 工具

    Returns:
        (route_decision, confidence, reason)
        - route_decision: "small" 或 "large"
        - confidence: 0.0~1.0 置信度
        - reason: 分类理由
    """
    # 如果有工具可用，直接路由到大模型（工具编排需要强推理能力）
    if has_tools:
        return "large", 1.0, "检测到可用工具，需要大模型进行工具编排"

    small_llm = _ensure_small_llm()
    if small_llm is None:
        return "large", 1.0, "小模型不可用，回退到大模型"

    try:
        messages = [
            SystemMessage(content=ROUTE_CLASSIFY_PROMPT),
            HumanMessage(content=content),
        ]
        response = small_llm.invoke(messages)
        result_text = response.content.strip()

        # 尝试解析 JSON（兼容模型可能输出的 markdown code block）
        if result_text.startswith("```"):
            # 去掉 ```json ... ``` 包裹
            lines = result_text.split("\n")
            result_text = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            )

        result = json.loads(result_text)
        route = result.get("route", "large")
        confidence = float(result.get("confidence", 0.5))
        reason = result.get("reason", "")

        # 置信度不足时升级到大模型
        if route == "small" and confidence < 0.7:
            util.log(1, f"[路由] 小模型置信度不足({confidence:.2f})，升级到大模型: {reason}")
            return "large", confidence, f"置信度不足，升级: {reason}"

        util.log(1, f"[路由] 决策={route}, 置信度={confidence:.2f}, 理由={reason}")
        return route, confidence, reason

    except json.JSONDecodeError as exc:
        util.log(1, f"[路由] 分类结果解析失败: {exc}, 原始输出: {result_text}")
        return "large", 0.5, "分类结果解析失败，回退到大模型"
    except Exception as exc:
        util.log(1, f"[路由] 分类请求失败: {exc}")
        return "large", 0.5, f"分类异常，回退到大模型: {exc}"


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

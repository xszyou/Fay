# -*- coding: utf-8 -*-
"""
大小模型协作 - 执行管理器

小模型做第一轮规划，若需要工具则交给大模型在后台线程执行。
按用户隔离，每用户最多一个执行线程。
执行完毕后回调通知小模型生成最终回复。
"""

import enum
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from utils import util
import utils.config_util as cfg


class ExecutionStatus(enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionState:
    """单个用户的执行状态"""
    username: str
    status: ExecutionStatus = ExecutionStatus.IDLE
    conversation_id: str = ""

    # 小模型传给大模型的输入上下文
    original_request: str = ""
    unverified_response: str = ""  # 规划器先输出的未核实回复（兜底核实场景用）
    first_plan: Dict[str, Any] = field(default_factory=dict)
    system_prompt: str = ""
    messages_buffer: List[Dict] = field(default_factory=list)
    memory_context: str = ""
    observation: Optional[str] = None
    prestart_context: str = ""
    tool_registry: Dict = field(default_factory=dict)

    # 大模型执行过程
    tool_results: List[Dict] = field(default_factory=list)
    audit_log: List[str] = field(default_factory=list)
    current_step: str = ""
    progress_messages: List[str] = field(default_factory=list)

    # 大模型产出的结果
    final_tool_context: str = ""
    final_response_hint: str = ""
    error: Optional[str] = None

    # 控制
    cancel_flag: bool = False
    modify_request: Optional[str] = None

    # 时间
    start_time: float = 0
    end_time: float = 0

    # 完成回调
    on_complete: Optional[Callable] = None


class ExecutionManager:
    """按用户隔离的执行管理器，每用户最多一个执行线程。"""

    def __init__(self):
        self._states: Dict[str, ExecutionState] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.RLock()

    def get_state(self, username: str) -> Optional[ExecutionState]:
        with self._lock:
            return self._states.get(username)

    def is_busy(self, username: str) -> bool:
        with self._lock:
            state = self._states.get(username)
            return state is not None and state.status == ExecutionStatus.RUNNING

    def has_result(self, username: str) -> bool:
        with self._lock:
            state = self._states.get(username)
            return state is not None and state.status in (
                ExecutionStatus.DONE,
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
            )

    def submit(self, state: ExecutionState) -> bool:
        """提交执行任务。若用户已有运行中任务返回 False。"""
        with self._lock:
            existing = self._states.get(state.username)
            if existing and existing.status == ExecutionStatus.RUNNING:
                return False
            state.status = ExecutionStatus.RUNNING
            state.start_time = time.time()
            self._states[state.username] = state

            t = threading.Thread(
                target=self._run_execution,
                args=(state,),
                name=f"big-model-exec-{state.username}",
                daemon=True,
            )
            self._threads[state.username] = t
            t.start()
            return True

    def cancel(self, username: str) -> bool:
        with self._lock:
            state = self._states.get(username)
            if state and state.status == ExecutionStatus.RUNNING:
                state.cancel_flag = True
                state.status = ExecutionStatus.CANCELLED
                return True
            return False

    def modify(self, username: str, instruction: str) -> bool:
        with self._lock:
            state = self._states.get(username)
            if state and state.status == ExecutionStatus.RUNNING:
                state.modify_request = instruction
                return True
            return False

    def consume_result(self, username: str) -> Optional[ExecutionState]:
        """取走并清理执行结果，小模型拿到结果后调用。"""
        with self._lock:
            state = self._states.get(username)
            if state and state.status in (
                ExecutionStatus.DONE,
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
            ):
                self._states[username] = ExecutionState(username=username)
                return state
            return None

    def _run_execution(self, state: ExecutionState):
        try:
            _big_model_execute(state)
        except Exception as e:
            util.log(1, f"大模型执行异常: {e}")
            state.error = str(e)
            state.status = ExecutionStatus.FAILED
        finally:
            state.end_time = time.time()
            if state.status == ExecutionStatus.RUNNING:
                state.status = ExecutionStatus.DONE
            if state.on_complete:
                try:
                    state.on_complete(state)
                except Exception as cb_err:
                    util.log(1, f"执行完成回调异常: {cb_err}")


# ---------------------------------------------------------------------------
# 大/小模型实例工厂
# ---------------------------------------------------------------------------

def _get_llm_instance(role: str = "small", streaming: bool = True) -> ChatOpenAI:
    """
    获取 LLM 实例。
    role="big"  → 优先用 system.conf 中的 big_model_* 配置，无配置时降级为小模型
    role="small" → 使用 system.conf 中的 gpt_* 配置
    """
    cfg.load_config()

    if role == "big":
        if cfg.big_model_engine:
            actual_base_url = cfg.big_model_base_url or cfg.gpt_base_url
            actual_api_key = cfg.big_model_api_key or cfg.key_gpt_api_key
            util.log(1, f"[LLM工厂] 使用大模型: model={cfg.big_model_engine}, base_url={actual_base_url}")
            return ChatOpenAI(
                model=cfg.big_model_engine,
                base_url=actual_base_url,
                api_key=actual_api_key,
                streaming=streaming,
                timeout=120,
                max_retries=2,
            )
        # 无大模型配置，降级为小模型
        util.log(1, f"[LLM工厂] 请求大模型但未配置 big_model_engine，降级为小模型: {cfg.gpt_model_engine}")

    # small / 降级：使用原始 gpt 配置
    util.log(1, f"[LLM工厂] 使用小模型: model={cfg.gpt_model_engine}, base_url={cfg.gpt_base_url}")
    return ChatOpenAI(
        model=cfg.gpt_model_engine,
        base_url=cfg.gpt_base_url,
        api_key=cfg.key_gpt_api_key,
        streaming=streaming,
        timeout=60,
        max_retries=1,
    )


# ---------------------------------------------------------------------------
# 大模型后台执行
# ---------------------------------------------------------------------------

def _format_tools_for_execution(tool_registry) -> str:
    """为执行循环格式化可用工具列表（精简版）。"""
    if not tool_registry:
        return "（无）"
    parts = []
    for name, spec in tool_registry.items():
        desc = getattr(spec, "description", "") or ""
        example = ""
        if hasattr(spec, "example_args") and spec.example_args:
            example = json.dumps(spec.example_args, ensure_ascii=False)
        parts.append(f"- {name}: {desc}" + (f" 示例args: {example}" if example else ""))
    return "\n".join(parts)


def _build_execution_next_step_messages(state: ExecutionState) -> list:
    """
    为大模型执行循环构建"下一步决策"的 prompt。
    与初始规划器不同，这里聚焦于：任务完成了没有？还需要调什么工具？
    """
    # 已完成的工具摘要（放宽截断，避免大模型因看不全输出而重复调同一工具）
    done_parts = []
    for r in state.tool_results:
        call = r.get("call", {})
        s = "成功" if r.get("success") else "失败"
        out = (r.get("output") or r.get("error") or "")[:1500]
        done_parts.append(f"  - {call.get('name')}({json.dumps(call.get('args', {}), ensure_ascii=False)}): {s}, 输出: {out}")
    done_summary = "\n".join(done_parts) if done_parts else "  （暂无）"

    tools_text = _format_tools_for_execution(state.tool_registry)

    # 获取知识库课程列表（帮助大模型做精准定向搜索）
    knowledge_sources_hint = ""
    try:
        from faymcp import mcp_runtime
        resource_text = mcp_runtime.get_all_resource_texts()
        if resource_text:
            knowledge_sources_hint = resource_text[:800]
    except Exception:
        pass

    system_content = (
        '你是一个任务执行器，负责逐步调用工具完成用户请求。请严格输出合法 JSON。\n'
        '\n'
        '输出格式只有两种：\n'
        '1. 还需要调用工具: {"action": "tool", "tool": "工具名", "args": {...}}\n'
        '2. 任务已完成: {"action": "finish", "message": "简短总结执行结果"}\n'
        '\n'
        '判断规则：\n'
        '- 对照用户的原始请求，检查是否所有要求都已满足\n'
        '- 如果用户要求获取多个项目（如"8章内容都读出来"），必须逐个调用工具，不能只做一部分就结束\n'
        '- 工具返回的结果中如果包含列表/目录，且用户要求查看详情，需要逐项调用详情工具\n'
        '- 【严格遵守】调用前先看【已完成的工具调用】列表，凡是已经成功执行过的"同名+同参数"调用，绝对不要再调一次——直接用已有输出\n'
        '- 无参数工具（args 为 {}）调用一次就够，不要反复调用期望得到不同结果\n'
        '- 工具失败可以换参数重试一次，但同样参数不要重复调用\n'
        '- 只有当用户的所有要求都已满足时，才输出 finish\n'
        '\n搜索策略：\n'
        '- 如果 kb_search 的结果不够相关（匹配的课程标题与用户问的主题明显不符），换关键词重试\n'
        '- 可以用 kb_list_sources 查看所有课程列表，找到最相关的课程后用 source_id 定向搜索\n'
        '- 优先从标题最匹配的课程中获取信息\n'
        f'\n可用工具：\n{tools_text}\n'
    )
    if knowledge_sources_hint:
        system_content += f'\n知识库中的课程：\n{knowledge_sources_hint}\n'
    system_content += f'\n已完成的工具调用：\n{done_summary}'

    # ---- 同步规划器拥有的完整上下文，确保大模型决策准确 ----
    context_parts = []

    # 人设
    if state.system_prompt and state.system_prompt.strip():
        context_parts.append(f"【角色设定】\n{state.system_prompt.strip()}")

    # 关联记忆
    if state.memory_context and state.memory_context.strip():
        context_parts.append(f"【关联记忆】\n{state.memory_context.strip()}")

    # 观察
    if state.observation and str(state.observation).strip():
        context_parts.append(f"【其他观察】\n{str(state.observation).strip()}")

    # 预启动工具结果
    if state.prestart_context and state.prestart_context.strip():
        context_parts.append(f"【预启动工具结果】\n{state.prestart_context.strip()}")

    # 对话历史（全量同步）
    if state.messages_buffer:
        dialogue_lines = []
        for m in state.messages_buffer:
            role = m.get("role", "")
            text = m.get("content") or ""
            if role and text:
                label = "用户" if role in ("user", "human") else "助手"
                dialogue_lines.append(f"  {label}: {text}")
        if dialogue_lines:
            context_parts.append("【对话历史】\n" + "\n".join(dialogue_lines))

    if context_parts:
        system_content += "\n\n" + "\n\n".join(context_parts)

    # ---- 核实模式：当存在未核实回复且尚未调用任何工具时，强制先调工具 ----
    verify_block = ""
    if state.unverified_response and not state.tool_results:
        verify_block = (
            "\n\n【核实模式 - 必须遵守】\n"
            "你刚才已经基于自身知识回答了用户，回答内容如下：\n"
            f"---\n{state.unverified_response[:500]}\n---\n"
            "你已经告诉用户'等等，我再帮你核实一下…'，所以这一轮的任务是：\n"
            "1. 从可用工具中挑一个合适的来核实上面回答的事实性内容（如知识库搜索、网络搜索、计算工具等）\n"
            "2. 严禁这一步直接 finish，必须先调一个工具\n"
            "3. 如果实在没有任何工具适合核实该问题，再输出 finish 并在 message 中说明'没有合适的工具核实'\n"
        )
    system_content += verify_block

    user_content = f"用户原始请求: {state.original_request}\n\n请决定下一步操作。"

    return [
        SystemMessage(content=system_content),
        HumanMessage(content=user_content),
    ]


def _extract_decision(text: str) -> Optional[Dict[str, Any]]:
    """从大模型输出中提取决策对象。

    支持三种格式：
    1. 纯 JSON：{"action": "tool", "tool": "X", "args": {...}} / {"action": "finish", "message": "..."}
    2. 混合内容：自然语言 + JSON 块（常见于 MiniMax/GPT）
    3. XML tool_call：<minimax:tool_call><invoke name="X"><arg name="k">v</arg></invoke></minimax:tool_call>
       或 Claude 风格 <function_calls><invoke name="X">...</invoke></function_calls>

    返回 None 表示既非工具调用也非明确的 finish（由调用方当作 finish 处理并把原文作为消息）。
    """
    if not text:
        return None

    # 1) 直接尝试整段 JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "action" in data:
            return data
    except json.JSONDecodeError:
        pass

    # 2) 扫描第一个平衡的 {...} 块并尝试解析
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        data = json.loads(candidate)
                        if isinstance(data, dict) and "action" in data:
                            return data
                    except json.JSONDecodeError:
                        pass
                    break
        start = text.find("{", start + 1)

    # 3) XML 风格 tool call（MiniMax / Claude 风格）
    invoke_match = re.search(
        r'<invoke\s+name\s*=\s*"([^"]+)"\s*>([\s\S]*?)</invoke>',
        text,
        flags=re.IGNORECASE,
    )
    if invoke_match:
        tool_name = invoke_match.group(1).strip()
        body = invoke_match.group(2)
        args: Dict[str, Any] = {}
        for m in re.finditer(
            r'<(?:parameter|arg)\s+name\s*=\s*"([^"]+)"\s*>([\s\S]*?)</(?:parameter|arg)>',
            body,
            flags=re.IGNORECASE,
        ):
            key = m.group(1).strip()
            val = m.group(2).strip()
            # 尝试把值解析为 JSON（数字/bool/对象），失败就当字符串
            try:
                args[key] = json.loads(val)
            except (json.JSONDecodeError, ValueError):
                args[key] = val
        return {"action": "tool", "tool": tool_name, "args": args}

    return None


def _big_model_execute(state: ExecutionState):
    """大模型后台线程入口：从小模型的第一轮规划结果开始执行工具循环。"""
    from llm.nlp_cognitive_stream import (
        _remove_think_from_text,
        _strip_json_code_fence,
    )

    util.log(1, f"[大模型执行] {state.username}: 后台线程启动，first_plan={state.first_plan}")
    big_llm = _get_llm_instance("big", streaming=False)
    tool_registry = state.tool_registry
    max_steps = 30

    # 小模型未指定 first_plan（如非 kb_search 场景）→ 先让大模型自行规划首步
    if not (state.first_plan and state.first_plan.get("name")):
        state.current_step = "大模型规划首步..."
        first_messages = _build_execution_next_step_messages(state)
        util.log(1, f"[大模型执行] {state.username}: 调用大模型规划首步...")
        try:
            first_response = big_llm.invoke(first_messages)
        except Exception as exc:
            util.log(1, f"[大模型执行] {state.username}: 大模型首步调用失败: {exc}")
            state.audit_log.append(f"大模型首步调用失败: {exc}")
            state.error = f"大模型首步调用失败: {exc}"
            state.current_step = "执行完成"
            return
        first_content = getattr(first_response, "content", "")
        first_trimmed = _strip_json_code_fence(_remove_think_from_text(first_content.strip()))
        util.log(1, f"[大模型执行] {state.username}: 首步返回: {first_trimmed[:200]}")
        first_decision = _extract_decision(first_trimmed)
        if first_decision is None:
            state.final_response_hint = first_trimmed
            state.current_step = "执行完成"
            return
        first_action = first_decision.get("action")
        if first_action == "tool":
            state.first_plan = {
                "name": first_decision.get("tool"),
                "args": first_decision.get("args") or {},
            }
        elif first_action in ("finish", "finish_text"):
            state.final_response_hint = first_decision.get("message", "")
            state.current_step = "执行完成"
            return
        else:
            state.audit_log.append(f"未知首步决策: {first_decision}")
            state.current_step = "执行完成"
            return

    current_action = state.first_plan  # {"name": ..., "args": ...}

    while len(state.tool_results) < max_steps:
        if state.cancel_flag:
            state.current_step = "已取消"
            return

        # 处理运行中修改指令
        if state.modify_request:
            instruction = state.modify_request
            state.modify_request = None
            state.audit_log.append(f"收到修改指令: {instruction}")

        if current_action is None:
            break

        tool_name = current_action.get("name")
        tool_args = current_action.get("args") or {}
        state.current_step = f"正在执行工具: {tool_name}"
        util.log(1, f"[大模型执行] {state.username}: {state.current_step}")

        spec = tool_registry.get(tool_name)
        if not spec:
            state.audit_log.append(f"未知工具: {tool_name}")
            state.error = f"未知工具: {tool_name}"
            break

        attempts = sum(
            1 for r in state.tool_results
            if r.get("call", {}).get("name") == tool_name
            and r.get("call", {}).get("args") == tool_args
        )
        success, output, error = spec.executor(tool_args, attempts)

        result = {
            "call": {"name": tool_name, "args": tool_args},
            "success": success,
            "output": output,
            "error": error,
            "attempt": attempts + 1,
        }
        state.tool_results.append(result)
        status_text = "成功" if success else "失败"
        state.audit_log.append(f"工具 {tool_name} 第{attempts+1}次: {status_text}")
        state.progress_messages.append(
            f"[TOOL] {tool_name} {status_text}: {(output or error or '')[:200]}"
        )

        # 大模型决策下一步（使用专用的执行 prompt）
        state.current_step = "大模型规划下一步..."
        next_step_messages = _build_execution_next_step_messages(state)
        util.log(1, f"[大模型执行] {state.username}: 调用大模型决策下一步...")
        try:
            response = big_llm.invoke(next_step_messages)
        except Exception as exc:
            util.log(1, f"[大模型执行] {state.username}: 大模型调用失败: {exc}")
            state.audit_log.append(f"大模型调用失败: {exc}")
            state.error = f"大模型调用失败: {exc}"
            break

        content = getattr(response, "content", "")
        trimmed = _remove_think_from_text(content.strip())
        trimmed = _strip_json_code_fence(trimmed)
        util.log(1, f"[大模型执行] {state.username}: 大模型返回: {trimmed[:200]}")

        decision = _extract_decision(trimmed)
        if decision is None:
            # 既非工具调用也非结构化 finish，直接把原文作为最终提示
            state.final_response_hint = trimmed
            break

        action = decision.get("action")
        if action == "tool":
            new_tool = decision.get("tool")
            new_args = decision.get("args") or {}
            # 防重复调用检测：扫描整个历史，任一已成功的同名同参调用 → 终止
            duplicate_hit = any(
                r.get("success")
                and r.get("call", {}).get("name") == new_tool
                and r.get("call", {}).get("args") == new_args
                for r in state.tool_results
            )
            if duplicate_hit:
                state.audit_log.append(
                    f"检测到重复调用（{new_tool} 同参数已成功过），终止循环"
                )
                state.final_response_hint = decision.get("message", "")
                break
            current_action = {"name": new_tool, "args": new_args}
        elif action in ("finish", "finish_text"):
            state.final_response_hint = decision.get("message", "")
            break
        else:
            state.audit_log.append(f"未知决策: {decision}")
            break

    # 汇总工具结果（给小模型生成最终回复用，保留足够内容）
    summary_parts = []
    for r in state.tool_results:
        call = r.get("call", {})
        s = "成功" if r.get("success") else "失败"
        output_text = (r.get("output") or r.get("error") or "无")[:2000]
        summary_parts.append(
            f"- {call.get('name')}({json.dumps(call.get('args', {}), ensure_ascii=False)}): "
            f"{s}, 输出: {output_text}"
        )
    state.final_tool_context = "\n".join(summary_parts)
    state.current_step = "执行完成"
    util.log(1, f"[大模型执行] {state.username}: 执行完成，共 {len(state.tool_results)} 步")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------
_manager = ExecutionManager()


def get_execution_manager() -> ExecutionManager:
    return _manager

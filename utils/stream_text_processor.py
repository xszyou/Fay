# -*- coding: utf-8 -*-
import time
from utils import util
from core import stream_manager
from utils.stream_state_manager import get_state_manager


class StreamTextProcessor:
    """
    安全的流式文本处理器，负责将长文本按句子切分并逐句写入流，
    同时具备超时、迭代上限、缓存上限等保护，避免死循环与性能问题。
    """

    def __init__(self, min_length=10, max_iterations=100, timeout_seconds=30, max_cache_size=10240):
        """
        初始化流式文本处理器

        参数:
            min_length: 最小发送长度阈值
            max_iterations: 最大循环次数限制
            timeout_seconds: 超时时间（秒）
            max_cache_size: 最大缓存大小（字符数）
        """
        self.min_length = min_length
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.max_cache_size = max_cache_size
        # 常用中英文分句标点（UTF-8）
        self.punctuation_marks = ["，", "。", "；", "：", "、", "！", "？", ".", "!", "?", "\n"]

    def process_stream_text(self, text, username, is_qa=False, session_type="stream"):
        """
        安全地处理流式文本分割与发送

        参数:
            text: 要处理的文本
            username: 用户名
            is_qa: 是否为 Q&A 模式
            session_type: 会话类型

        返回:
            bool: 处理是否成功
        """
        if not text or not text.strip():
            return True

        # 捕获本次流式处理对应的会话ID（用于精确隔离）
        sm = stream_manager.new_instance()
        conversation_id = sm.get_conversation_id(username)

        # 获取状态管理器并开始新会话（若未开始或会话不匹配则对齐）
        state_manager = get_state_manager()
        session_info = state_manager.get_session_info(username)
        if (not session_info) or (session_info.get('conversation_id') != conversation_id):
            state_manager.start_new_session(username, session_type, conversation_id=conversation_id)

        try:
            return self._safe_process_text(text, username, is_qa, state_manager, conversation_id)
        except Exception as e:
            util.log(1, f"流式文本处理出错: {str(e)}")
            # 发生异常时，直接发送完整文本作为备用方案
            self._send_fallback_text(text, username, state_manager, conversation_id)
            return False

    def _safe_process_text(self, text, username, is_qa, state_manager, conversation_id):
        """
        安全的文本处理核心逻辑，包含缓存溢出保护
        """
        accumulated_text = text
        iteration_count = 0
        start_time = time.time()

        # 缓存溢出检查
        if len(accumulated_text) > self.max_cache_size:
            util.log(1, f"文本缓存溢出，长度: {len(accumulated_text)}, 限制: {self.max_cache_size}")
            # 截断文本到安全大小
            accumulated_text = accumulated_text[:self.max_cache_size]
            util.log(1, f"文本已截断到: {len(accumulated_text)} 字符")

        # 主处理循环，带安全保护
        first_sentence_sent = False  # 跟踪是否已发送第一个句子
        while accumulated_text and iteration_count < self.max_iterations:
            # 超时检查
            if time.time() - start_time > self.timeout_seconds:
                util.log(1, f"流式处理超时，剩余文本长度: {len(accumulated_text)}")
                break

            # 动态缓存大小检查
            if len(accumulated_text) > self.max_cache_size:
                util.log(1, f"处理过程中缓存溢出，强制发送剩余文本")
                break

            iteration_count += 1

            # 查找标点符号位置
            punct_indices = self._find_punctuation_indices(accumulated_text)

            if not punct_indices:
                # 没有标点符号，退出循环
                break

            # 尝试发送一个句子
            sent_successfully = False
            for punct_index in punct_indices:
                sentence_text = accumulated_text[:punct_index + 1]

                if len(sentence_text) >= self.min_length:
                    # 使用状态管理器准备句子
                    marked_text, is_first, is_end = state_manager.prepare_sentence(
                        username,
                        sentence_text,
                        force_first=(not first_sentence_sent),  # 第一段 True，其它 False
                        force_end=False,
                        is_qa=is_qa,
                        conversation_id=conversation_id,
                    )

                    success = stream_manager.new_instance().write_sentence(
                        username, marked_text, conversation_id=conversation_id
                    )
                    if success:
                        accumulated_text = accumulated_text[punct_index + 1:].lstrip()
                        first_sentence_sent = True  # 标记已发送第一个句子
                        sent_successfully = True
                        break
                    else:
                        util.log(1, f"发送句子失败: {marked_text[:50]}...")

            # 如果这轮没有成功发送任何内容，退出循环防止死循环
            if not sent_successfully:
                break

        # 发送剩余文本，如果是最后的文本则标记为结束
        if accumulated_text:
            marked_text, _, _ = state_manager.prepare_sentence(
                username,
                accumulated_text,
                force_first=(not first_sentence_sent),  # 如果还没发送过句子，这是第一段
                force_end=True,
                is_qa=is_qa,
                conversation_id=conversation_id,
            )
            stream_manager.new_instance().write_sentence(
                username, marked_text, conversation_id=conversation_id
            )
            first_sentence_sent = True
        elif not first_sentence_sent:
            # 如果整个文本都没有找到合适的分割点，作为完整句子发送
            marked_text, _, _ = state_manager.prepare_sentence(
                username, text, force_first=True, force_end=True, conversation_id=conversation_id
            )
            stream_manager.new_instance().write_sentence(
                username, marked_text, conversation_id=conversation_id
            )
        else:
            # 如果没有剩余文本，需要确保最后发送的句子包含结束标记
            session_info = state_manager.get_session_info(username)
            if session_info and not session_info.get("is_end_sent", False):
                marked_text, _, _ = state_manager.prepare_sentence(
                    username, "", force_first=False, force_end=True, conversation_id=conversation_id
                )
                stream_manager.new_instance().write_sentence(
                    username, marked_text, conversation_id=conversation_id
                )

        # 结束会话
        state_manager.end_session(username, conversation_id=conversation_id)

        # 记录处理统计
        if iteration_count >= self.max_iterations:
            util.log(1, f"流式处理达到最大迭代次数限制: {self.max_iterations}")

        return True

    def _find_punctuation_indices(self, text):
        """
        安全地查找标点符号位置
        """
        try:
            indices = []
            for punct in self.punctuation_marks:
                try:
                    index = text.find(punct)
                    if index != -1:
                        indices.append(index)
                except Exception as e:
                    util.log(1, f"查找标点符号 '{punct}' 时出错: {str(e)}")
                    continue

            return sorted([i for i in indices if i != -1])
        except Exception as e:
            util.log(1, f"查找标点符号时出错: {str(e)}")
            return []

    def _send_fallback_text(self, text, username, state_manager, conversation_id):
        """
        备用发送方案：直接发送完整文本（含首尾标记）
        """
        try:
            # 使用状态管理器准备完整文本
            marked_text, _, _ = state_manager.prepare_sentence(
                username, text, force_first=True, force_end=True, conversation_id=conversation_id
            )
            stream_manager.new_instance().write_sentence(
                username, marked_text, conversation_id=conversation_id
            )
            util.log(1, "使用备用方案发送完整文本")
        except Exception as e:
            util.log(1, f"备用发送方案也失败: {str(e)}")


# 全局单例实例
_processor_instance = None


def get_processor():
    """
    获取流式文本处理器单例
    """
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = StreamTextProcessor()
    return _processor_instance

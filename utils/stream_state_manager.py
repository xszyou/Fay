import threading
import time
from enum import Enum
from utils import util


class StreamState(Enum):
    """句子流的会话内状态枚举"""
    IDLE = "idle"
    FIRST_SENTENCE = "first"
    MIDDLE_SENTENCE = "middle"
    LAST_SENTENCE = "last"
    COMPLETED = "completed"


class StreamStateManager:
    """
    流式会话状态管理器（统一管理 isfirst/isend 标记）。
    通过 conversation_id 感知并对齐会话，避免跨会话状态串线。
    """

    def __init__(self):
        self.lock = threading.RLock()
        # username -> state info
        self.user_states = {}

    def start_new_session(self, username, session_type="stream", conversation_id=None):
        """
        启动或重置指定用户的流式会话。

        参数:
            username: 用户名
            session_type: 会话类型（stream, qa, auto_play 等）
            conversation_id: 外部对齐的会话ID；为 None 时将尝试从 StreamManager 获取

        返回:
            conversation_id（如果未知可能为 None）
        """
        with self.lock:
            if conversation_id is None:
                try:
                    from core import stream_manager  # lazy import to avoid cycles
                    conversation_id = stream_manager.new_instance().get_conversation_id(username)
                except Exception:
                    conversation_id = None

            self.user_states[username] = {
                "session_type": session_type,
                "state": StreamState.IDLE,
                "sentence_count": 0,
                "start_time": time.time(),
                "last_update": time.time(),
                "is_first_sent": False,
                "is_end_sent": False,
                "conversation_id": conversation_id,
            }
            return conversation_id

    def prepare_sentence(self, username, text, force_first=False, force_end=False, is_qa=False, conversation_id=None):
        """
        准备要发送的句子：根据需要追加首尾标记并安全更新状态。

        返回: (marked_text, is_first, is_end)
        """
        with self.lock:
            # 与当前会话对齐（若提供或可获取）
            current_cid = conversation_id
            if current_cid is None:
                try:
                    from core import stream_manager
                    current_cid = stream_manager.new_instance().get_conversation_id(username)
                except Exception:
                    current_cid = None

            if username not in self.user_states:
                self.start_new_session(username, conversation_id=current_cid)

            state_info = self.user_states[username]
            if state_info.get("conversation_id") != current_cid:
                # 会话已切换，重置状态
                self.start_new_session(username, session_type=state_info.get("session_type", "stream"), conversation_id=current_cid)
                state_info = self.user_states[username]

            state_info["last_update"] = time.time()

            # 判定是否为首句
            is_first = False
            if force_first or (not state_info["is_first_sent"] and state_info["sentence_count"] == 0):
                is_first = True
                state_info["is_first_sent"] = True
                state_info["state"] = StreamState.FIRST_SENTENCE
            elif state_info["sentence_count"] > 0:
                state_info["state"] = StreamState.MIDDLE_SENTENCE

            # 判定是否为尾句
            is_end = bool(force_end)
            if is_end:
                state_info["is_end_sent"] = True
                state_info["state"] = StreamState.LAST_SENTENCE

            # 句子计数 +1
            state_info["sentence_count"] += 1

            # 附加隐藏标记
            marked_text = text
            if is_first and not marked_text.endswith("_<isfirst>"):
                marked_text += "_<isfirst>"
            if is_end and not marked_text.endswith("_<isend>"):
                marked_text += "_<isend>"
            if is_qa and not marked_text.endswith("_<isqa>"):
                marked_text += "_<isqa>"
            return marked_text, is_first, is_end

    def end_session(self, username, conversation_id=None):
        """
        结束当前会话（此处不再追加任何结束标记，仅更新状态）。
        """
        with self.lock:
            if username not in self.user_states:
                util.log(1, f"警告：尝试结束一个不存在的会话 [{username}]")
                return ""

            state_info = self.user_states[username]
            if conversation_id is not None and state_info.get("conversation_id") != conversation_id:
                util.log(1, f"警告：end_session 会话不一致，当前={state_info.get('conversation_id')}，传入={conversation_id}")
                return ""

            if state_info["state"] != StreamState.COMPLETED:
                state_info["state"] = StreamState.COMPLETED
                # 若未发送过结束标记，给出警告日志
                if not state_info["is_end_sent"]:
                    util.log(1, "警告：本次会话未发送结束标记即已结束（可能存在异常路径）")
            return ""

    def get_session_info(self, username, conversation_id=None):
        with self.lock:
            info = self.user_states.get(username)
            if not info:
                return None
            if conversation_id is not None and info.get("conversation_id") != conversation_id:
                return None
            return info.copy()

    def is_session_active(self, username, conversation_id=None):
        with self.lock:
            info = self.user_states.get(username)
            if not info:
                return False
            if conversation_id is not None and info.get("conversation_id") != conversation_id:
                return False
            return info["state"] != StreamState.COMPLETED

    def cleanup_expired_sessions(self, timeout_seconds=300):
        """
        清理超时未更新的会话，并与 StreamManager 协同释放资源（避免死锁）。
        """
        # 1) 在持有自身锁时快照需要清理的会话项
        with self.lock:
            now = time.time()
            expired = []  # [(username, conversation_id, state)]
            for username, state_info in self.user_states.items():
                if now - state_info["last_update"] > timeout_seconds:
                    expired.append(
                        (
                            username,
                            state_info.get("conversation_id", ""),
                            state_info.get("state", None),
                        )
                    )

        # 2) 释放自身锁后调用 StreamManager，避免锁顺序反转导致死锁
        sm = None
        try:
            from core import stream_manager
            sm = stream_manager.new_instance()
        except Exception as e:
            util.log(1, f"清理过期会话：无法获取 StreamManager，仅删除状态。错误={e}")

        for username, state_cid, _ in expired:
            try:
                if sm is not None:
                    current_cid = sm.get_conversation_id(username)
                    # 仅在会话ID一致时清理流与音频，避免误清刚切换的新会话
                    if (state_cid or "") == (current_cid or ""):
                        sm.clear_Stream_with_audio(username)
                    else:
                        util.log(1, f"跳过流清理（会话ID不一致）user={username}, state_cid={state_cid}, current_cid={current_cid}")
            except Exception as e:
                util.log(1, f"清理过期会话：清理 StreamManager 资源时出错 user={username}: {e}")

        # 3) 最后在锁内删除仍然指向相同会话的状态
        with self.lock:
            for username, state_cid, _ in expired:
                info = self.user_states.get(username)
                if info and (info.get("conversation_id", "") == (state_cid or "")):
                    util.log(1, f"已清理过期会话：{state_cid}")
                    del self.user_states[username]

    def force_reset_user_state(self, username):
        """
        强制重置用户状态，并安全清理 StreamManager 侧资源（避免死锁）。
        """
        # 在锁内读取当前会话ID
        cid = None
        with self.lock:
            if username in self.user_states:
                cid = self.user_states[username].get("conversation_id", "")

        # 在不持有本地锁的情况下清理 StreamManager 资源
        try:
            from core import stream_manager
            sm = stream_manager.new_instance()
            sm.clear_Stream_with_audio(username)
        except Exception as e:
            util.log(1, f"强制重置：清理 StreamManager 资源失败 {username}: {e}")

        # 若状态仍然匹配该会话，再次加锁后删除
        with self.lock:
            if username in self.user_states:
                # 如果 cid 为空/相同则删除；否则视为已切换到新会话，跳过删除
                cur_cid = self.user_states[username].get("conversation_id", "")
                if (not cid) or (cur_cid == cid):
                    del self.user_states[username]
                    util.log(1, f"已强制重置用户状态 {username}, 会话 {cid}")

    def get_all_active_sessions(self):
        """获取所有未标记为 COMPLETED 的活动会话信息（浅拷贝）。"""
        with self.lock:
            active = {}
            for username, state_info in self.user_states.items():
                if state_info["state"] != StreamState.COMPLETED:
                    active[username] = state_info.copy()
            return active


_state_manager_instance = None
_state_manager_lock = threading.Lock()


def get_state_manager():
    """获取全局 StreamStateManager 单例实例（线程安全惰性初始化）。"""
    global _state_manager_instance
    if _state_manager_instance is None:
        with _state_manager_lock:
            if _state_manager_instance is None:
                _state_manager_instance = StreamStateManager()
    return _state_manager_instance


def start_cleanup_thread():
    """启动定时清理线程，周期性清理超时会话。"""
    def cleanup_worker():
        while True:
            try:
                time.sleep(60)
                get_state_manager().cleanup_expired_sessions()
            except Exception as e:
                util.log(1, f"清理过期会话时发生错误: {str(e)}")

    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    util.log(1, "流式状态管理器清理线程已启动")


# 自动启动清理线程
start_cleanup_thread()

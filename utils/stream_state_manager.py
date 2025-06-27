import threading
import time
from utils import util
from enum import Enum

class StreamState(Enum):
    """流式状态枚举"""
    IDLE = "idle"           # 空闲状态
    FIRST_SENTENCE = "first"  # 第一句话
    MIDDLE_SENTENCE = "middle"  # 中间句子
    LAST_SENTENCE = "last"    # 最后一句话
    COMPLETED = "completed"   # 完成状态

class StreamStateManager:
    """
    流式状态管理器 - 统一管理isfirst/isend标记
    解决多处设置标记导致的状态不一致问题
    """
    
    def __init__(self):
        self.lock = threading.RLock()
        self.user_states = {}  # 用户名 -> 状态信息
        self.session_counters = {}  # 用户名 -> 会话计数器
    
    def start_new_session(self, username, session_type="stream"):
        """
        开始新的流式会话
        
        参数:
            username: 用户名
            session_type: 会话类型 (stream, qa, auto_play等)
        
        返回:
            session_id: 会话ID
        """
        with self.lock:
            if username not in self.session_counters:
                self.session_counters[username] = 0
            
            self.session_counters[username] += 1
            session_id = f"{username}_{session_type}_{self.session_counters[username]}_{int(time.time())}"
            
            self.user_states[username] = {
                'session_id': session_id,
                'session_type': session_type,
                'state': StreamState.IDLE,
                'sentence_count': 0,
                'start_time': time.time(),
                'last_update': time.time(),
                'is_first_sent': False,
                'is_end_sent': False
            }
            
            util.log(1, f"开始新会话: {session_id}")
            return session_id
    
    def prepare_sentence(self, username, text, force_first=False, force_end=False):
        """
        准备发送句子，自动添加适当的标记

        参数:
            username: 用户名
            text: 文本内容
            force_first: 强制设为第一句
            force_end: 强制设为最后一句

        返回:
            tuple: (处理后的文本, 是否为第一句, 是否为最后一句)
        """
        with self.lock:
            if username not in self.user_states:
                # 如果没有活跃会话，自动创建一个
                self.start_new_session(username)

            state_info = self.user_states[username]
            state_info['last_update'] = time.time()

            # 判断是否为第一句
            is_first = False
            if force_first or (not state_info['is_first_sent'] and state_info['sentence_count'] == 0):
                is_first = True
                state_info['is_first_sent'] = True
                state_info['state'] = StreamState.FIRST_SENTENCE
            elif state_info['sentence_count'] > 0:
                state_info['state'] = StreamState.MIDDLE_SENTENCE

            # 判断是否为最后一句
            is_end = force_end
            if is_end:
                state_info['is_end_sent'] = True
                state_info['state'] = StreamState.LAST_SENTENCE

            # 更新句子计数
            state_info['sentence_count'] += 1

            # 构造带标记的文本
            marked_text = text
            if is_first and not marked_text.endswith('_<isfirst>'):
                marked_text += "_<isfirst>"
            if is_end and not marked_text.endswith('_<isend>'):
                marked_text += "_<isend>"
            return marked_text, is_first, is_end
    
    def end_session(self, username):
        """
        结束当前会话

        参数:
            username: 用户名

        返回:
            str: 空字符串（结束标记应该已经附加到最后一句话上）
        """
        with self.lock:
            if username not in self.user_states:
                util.log(1, f"警告: 尝试结束不存在的会话 [{username}]")
                return ""

            state_info = self.user_states[username]

            # 标记会话为完成状态
            if state_info['state'] != StreamState.COMPLETED:
                state_info['state'] = StreamState.COMPLETED

                session_duration = time.time() - state_info['start_time']

                # 检查是否已经发送过结束标记
                if not state_info['is_end_sent']:
                    util.log(1, f"警告: 会话结束但未发送过结束标记，可能存在逻辑问题")

            return ""  # 不再返回单独的_<isend>标记
    
    def get_session_info(self, username):
        """
        获取用户的会话信息
        
        参数:
            username: 用户名
            
        返回:
            dict: 会话信息
        """
        with self.lock:
            if username in self.user_states:
                return self.user_states[username].copy()
            return None
    
    def is_session_active(self, username):
        """
        检查用户是否有活跃的会话
        
        参数:
            username: 用户名
            
        返回:
            bool: 是否有活跃会话
        """
        with self.lock:
            if username not in self.user_states:
                return False
            
            state_info = self.user_states[username]
            return state_info['state'] not in [StreamState.COMPLETED]
    
    def cleanup_expired_sessions(self, timeout_seconds=300):
        """
        清理过期的会话
        
        参数:
            timeout_seconds: 超时时间（秒）
        """
        with self.lock:
            current_time = time.time()
            expired_users = []
            
            for username, state_info in self.user_states.items():
                if current_time - state_info['last_update'] > timeout_seconds:
                    expired_users.append(username)
            
            for username in expired_users:
                util.log(1, f"清理过期会话: {self.user_states[username]['session_id']}")
                del self.user_states[username]
    
    def force_reset_user_state(self, username):
        """
        强制重置用户状态（用于异常恢复）
        
        参数:
            username: 用户名
        """
        with self.lock:
            if username in self.user_states:
                old_session = self.user_states[username]['session_id']
                del self.user_states[username]
                util.log(1, f"强制重置用户状态: {username}, 旧会话: {old_session}")
    
    def get_all_active_sessions(self):
        """
        获取所有活跃会话的信息
        
        返回:
            dict: 用户名 -> 会话信息
        """
        with self.lock:
            active_sessions = {}
            for username, state_info in self.user_states.items():
                if state_info['state'] != StreamState.COMPLETED:
                    active_sessions[username] = state_info.copy()
            return active_sessions

# 全局单例实例
_state_manager_instance = None
_state_manager_lock = threading.Lock()

def get_state_manager():
    """
    获取流式状态管理器单例
    
    返回:
        StreamStateManager: 状态管理器实例
    """
    global _state_manager_instance
    if _state_manager_instance is None:
        with _state_manager_lock:
            if _state_manager_instance is None:
                _state_manager_instance = StreamStateManager()
    return _state_manager_instance

# 定时清理过期会话的线程
def start_cleanup_thread():
    """
    启动定时清理线程
    """
    import threading
    
    def cleanup_worker():
        while True:
            try:
                time.sleep(60)  # 每分钟清理一次
                get_state_manager().cleanup_expired_sessions()
            except Exception as e:
                util.log(1, f"清理过期会话时出错: {str(e)}")
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    util.log(1, "流式状态管理器清理线程已启动")

# 自动启动清理线程
start_cleanup_thread()

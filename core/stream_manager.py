# -*- coding: utf-8 -*-
import threading
import time
from utils import stream_sentence
from scheduler.thread_manager import MyThread
import fay_booter
from core import member_db
from core.interact import Interact

# 全局变量，用于存储StreamManager的单例实例
__streams = None
# 线程锁，用于保护全局变量的访问
__streams_lock = threading.Lock()

def new_instance(max_sentences=1024):
    """
    创建并返回StreamManager的单例实例
    :param max_sentences: 最大句子缓存数量
    :return: StreamManager实例
    """
    global __streams
    with __streams_lock:
        if __streams is None:
            __streams = StreamManager(max_sentences)
    return __streams

class StreamManager:
    """
    流管理器类，用于管理和处理文本流数据
    """
    def __init__(self, max_sentences=3):
        """
        初始化StreamManager
        :param max_sentences: 每个流的最大句子缓存数量
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        # 使用两个独立的锁，避免死锁
        self.stream_lock = threading.RLock()   # 流读写操作锁（可重入锁，允许同一线程多次获取）
        self.control_lock = threading.Lock()   # 控制标志锁（用于停止生成标志）
        self.streams = {}  # 存储用户ID到句子缓存的映射
        self.nlp_streams = {}  # 存储用户ID到句子缓存的映射
        self.max_sentences = max_sentences  # 最大句子缓存数量
        self.listener_threads = {}  # 存储用户ID到监听线程的映射
        self.running = True  # 控制监听线程的运行状态
        self._initialized = True  # 标记是否已初始化
        self.msgid = ""  # 消息ID
        self.stop_generation_flags = {}  # 存储用户的停止生成标志
        self.conversation_ids = {}  # 存储每个用户的会话ID（conv_前缀）


    def set_current_conversation(self, username, conversation_id, session_type=None):
        """设置当前会话ID（conv_*）并对齐状态管理器的会话。
        session_type 可选；未提供则沿用已存在状态的类型或默认 'stream'。
        """
        with self.control_lock:
            self.conversation_ids[username] = conversation_id

        # 对齐 StreamStateManager 的会话，以防用户名级状态跨会话串线
        try:
            from utils.stream_state_manager import get_state_manager  # 延迟导入避免循环依赖
            smgr = get_state_manager()
            info = smgr.get_session_info(username)
            if (not info) or (info.get('conversation_id') != conversation_id):
                smgr.start_new_session(
                    username,
                    session_type if session_type else (info.get('session_type') if info else 'stream'),
                    conversation_id=conversation_id,
                )
        except Exception:
            # 状态对齐失败不阻断主流程
            pass

    def get_conversation_id(self, username):
        """获取当前会话ID（可能为空字符串）"""
        with self.control_lock:
            return self.conversation_ids.get(username, "")

    def _get_Stream_internal(self, username):
        """
        内部方法：获取指定用户ID的文本流（不加锁，调用者必须已持有stream_lock）
        :param username: 用户名
        :return: 对应的句子缓存对象
        """
        if username not in self.streams or username not in self.nlp_streams:
            # 创建新的流缓存
            self.streams[username] = stream_sentence.SentenceCache(self.max_sentences)
            self.nlp_streams[username] = stream_sentence.SentenceCache(self.max_sentences)

            # 启动监听线程（如果还没有）
            if username not in self.listener_threads:
                stream = self.streams[username]
                nlp_stream = self.nlp_streams[username]
                thread = MyThread(target=self.listen, args=(username, stream, nlp_stream), daemon=True)
                self.listener_threads[username] = thread
                thread.start()

        return self.streams[username], self.nlp_streams[username]
    
    def get_Stream(self, username):
        """
        获取指定用户ID的文本流，如果不存在则创建新的（线程安全）
        :param username: 用户名
        :return: 对应的句子缓存对象
        """
        # 使用stream_lock保护流的读写操作
        with self.stream_lock:
            return self._get_Stream_internal(username)

    def write_sentence(self, username, sentence, conversation_id=None, session_version=None):
        """
        写入句子到指定用户的文本流（线程安全）
        :param username: 用户名
        :param sentence: 要写入的句子
        :param conversation_id: 句子产生时的会话ID（可选，优先于版本判断）
        :param session_version: 句子产生时的会话版本（可选，兼容旧路径）
        :return: 写入是否成功
        """
        # 检查句子长度，防止过大的句子导致内存问题
        if len(sentence) > 10240:  # 10KB限制
            sentence = sentence[:10240]

        # 若当前处于停止状态且这不是新会话的首句，则丢弃写入，避免残余输出
        with self.control_lock:
            stop_flag = self.stop_generation_flags.get(username, False)
            current_cid = self.conversation_ids.get(username, "")
        if stop_flag and ('_<isfirst>' not in sentence):
            return False

        # 优先使用会话ID进行校验
        if conversation_id is not None and conversation_id != current_cid:
            return False
        # 兼容旧逻辑：按版本校验
        

        # 检查是否包含_<isfirst>标记（可能在句子中间）
        if '_<isfirst>' in sentence:
            # 收到新处理的第一个句子，重置停止标志，允许后续处理
            with self.control_lock:
                self.stop_generation_flags[username] = False
        
        # 使用stream_lock保护写入操作
        with self.stream_lock:
            try:
                # 使用内部方法避免重复加锁
                Stream, nlp_Stream = self._get_Stream_internal(username)
                # 将会话ID以隐藏标签形式附在主流句子尾部，便于入口解析
                tag_cid = conversation_id if conversation_id is not None else current_cid
                tagged_sentence = f"{sentence}__<cid={tag_cid}>__" if tag_cid else sentence
                success = Stream.write(tagged_sentence)
                # 让 NLP 流也携带隐藏的会话ID，便于前端按会话过滤
                nlp_success = nlp_Stream.write(tagged_sentence)
                return success and nlp_success
            except Exception as e:
                print(f"写入句子时出错: {e}")
                return False

    def _clear_Stream_internal(self, username):
        """
        内部清除文本流方法，不获取锁（调用者必须已持有锁）
        :param username: 用户名
        """
        if username in self.streams:
            self.streams[username].clear()
        if username in self.nlp_streams:
            self.nlp_streams[username].clear()

        # 清除后写入一条结束标记，分别通知主流与NLP流结束
        try:
            # 确保流存在（监听线程也会在首次创建时启动）
            stream, nlp_stream = self._get_Stream_internal(username)
            cid = self.conversation_ids.get(username, "")
            end_marker = "_<isend>"
            # 主流带会话ID隐藏标签，供下游按会话拦截
            tagged = f"{end_marker}__<cid={cid}>__" if cid else end_marker
            stream.write(tagged)
            # NLP 流也写入带会话ID的结束标记，前端会按会话过滤
            nlp_stream.write(tagged)
        except Exception:
            # 忽略写入哨兵失败
            pass

    def set_stop_generation(self, username, stop=True):
        """
        设置指定用户的停止生成标志
        :param username: 用户名
        :param stop: 是否停止，默认True
        """
        with self.control_lock:
            self.stop_generation_flags[username] = stop

    def should_stop_generation(self, username, conversation_id=None, session_version=None):
        """
        检查指定用户是否应该停止生成
        :param username: 用户名
        :return: 是否应该停止
        """
        with self.control_lock:
            flag = self.stop_generation_flags.get(username, False)
            if flag:
                return True
            # 优先按会话ID判断
            current_cid = self.conversation_ids.get(username, "")
            if conversation_id is not None and conversation_id != current_cid:
                return True
            # 兼容旧逻辑：按版本判断
            return False

    # 内部方法已移除，直接使用带锁的公共方法

    def _clear_user_specific_audio(self, username, sound_queue):
        """
        清理特定用户的音频队列项，保留其他用户的音频
        :param username: 要清理的用户名
        :param sound_queue: 音频队列
        """
        import queue
        from utils import util
        temp_items = []
        
        # 使用非阻塞方式提取所有项，避免死锁
        try:
            while True:
                item = sound_queue.get_nowait()  # 非阻塞获取
                file_url, audio_length, interact = item
                item_user = interact.data.get('user', '')
                if item_user != username:
                    temp_items.append(item)  # 保留非目标用户的项
                # 目标用户的项直接丢弃（不添加到 temp_items）
        except queue.Empty:
            # 队列空了，正常退出循环
            pass
        
        # 将保留的项重新放入队列（使用非阻塞方式）
        for item in temp_items:
            try:
                sound_queue.put_nowait(item)  # 非阻塞放入
            except queue.Full:
                # 队列满的情况很少见，如果发生则记录日志
                util.printInfo(1, username, "音频队列已满，跳过部分音频项")
                break


    def _clear_audio_queue(self, username):
        """
        清空指定用户的音频队列
        :param username: 用户名
        注意：此方法假设调用者已持有必要的锁
        """
        fay_core = fay_booter.feiFei
        # 只清理特定用户的音频项，保留其他用户的音频
        self._clear_user_specific_audio(username, fay_core.sound_query)

    def clear_Stream_with_audio(self, username):
        """
        清除指定用户ID的文本流数据和音频队列（完全清除）
        注意：分步操作，避免锁嵌套
        :param username: 用户名
        """
        # 第一步：切换会话版本，令现有读/写循环尽快退出
        # 不在清理时递增会话版本，由新交互开始时统一递增

        # 第二步：设置停止标志（独立操作）
        with self.control_lock:
            self.stop_generation_flags[username] = True

        # 第三步：清除音频队列（Queue线程安全，不需要锁）
        self._clear_audio_queue(username)

        # reset think state for username on force stop
        try:
            uid_tmp = member_db.new_instance().find_user(username)
            if uid_tmp is not None:
                fei = fay_booter.feiFei
                if fei is not None:
                    fei.think_mode_users[uid_tmp] = False
                    if uid_tmp in getattr(fei, 'think_time_users', {}):
                        del fei.think_time_users[uid_tmp]
                    if uid_tmp in getattr(fei, 'think_display_state', {}):
                        del fei.think_display_state[uid_tmp]
        except Exception:
            pass
        
        # 第四步：清除文本流（独立操作）
        with self.stream_lock:
            self._clear_Stream_internal(username)
        


    def listen(self, username, stream, nlp_stream):
        while self.running:
            sentence = stream.read()
            if sentence:
                self.execute(username, sentence)
            else:
                time.sleep(0.1)

    def execute(self, username, sentence):
        """
        执行句子处理逻辑
        :param username: 用户名
        :param sentence: 要处理的句子
        """
        # 从句子尾部解析隐藏的会话ID标签
        producer_cid = None
        try:
            import re as _re
            m = _re.search(r"__<cid=([^>]+)>__", sentence)
            if m:
                producer_cid = m.group(1)
                sentence = sentence.replace(m.group(0), "")
        except Exception:
            producer_cid = None

        # 检查停止标志（使用control_lock）
        with self.control_lock:
            should_stop = self.stop_generation_flags.get(username, False)

        if should_stop:
            return

        # 进一步进行基于会话ID/版本的快速拦截（避免进入下游 say）
        try:
            current_cid = getattr(self, 'conversation_ids', {}).get(username, "")
            check_cid = producer_cid if producer_cid is not None else current_cid
            if self.should_stop_generation(username, conversation_id=check_cid):
                return
        except Exception:
            pass

        # 处理句子标记（无锁，避免长时间持有锁）
        is_first = "_<isfirst>" in sentence
        is_end = "_<isend>" in sentence
        is_qa = "_<isqa>" in sentence
        sentence = sentence.replace("_<isfirst>", "").replace("_<isend>", "").replace("_<isqa>", "")
        
        # 执行实际处理（无锁，避免死锁）
        if sentence or is_first or is_end or is_qa:
            fay_core = fay_booter.feiFei
            # 附带当前会话ID，方便下游按会话控制输出
            effective_cid = producer_cid if producer_cid is not None else getattr(self, 'conversation_ids', {}).get(username, "")
            interact = Interact("stream", 1, {"user": username, "msg": sentence, "isfirst": is_first, "isend": is_end, "conversation_id": effective_cid})
            fay_core.say(interact, sentence, type="qa" if is_qa else "")  # 调用核心处理模块进行响应
        time.sleep(0.01)  # 短暂休眠以控制处理频率





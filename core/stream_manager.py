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
        self.lock = threading.Lock()  # 线程锁，用于保护streams字典的访问
        self.streams = {}  # 存储用户ID到句子缓存的映射
        self.nlp_streams = {}  # 存储用户ID到句子缓存的映射
        self.max_sentences = max_sentences  # 最大句子缓存数量
        self.listener_threads = {}  # 存储用户ID到监听线程的映射
        self.running = True  # 控制监听线程的运行状态
        self._initialized = True  # 标记是否已初始化
        self.msgid = ""  # 消息ID

    def get_Stream(self, username):
        """
        获取指定用户ID的文本流，如果不存在则创建新的（线程安全）
        :param username: 用户名
        :return: 对应的句子缓存对象
        """
        # 注意：这个方法应该在已经获得锁的情况下调用
        # 如果从外部调用，需要先获得锁

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

    def write_sentence(self, username, sentence):
        """
        写入句子到指定用户的文本流（线程安全）
        :param username: 用户名
        :param sentence: 要写入的句子
        :return: 写入是否成功
        """
        # 检查句子长度，防止过大的句子导致内存问题
        if len(sentence) > 10240:  # 10KB限制
            sentence = sentence[:10240]

        # 使用锁保护获取和写入操作
        with self.lock:
            # 检查是否包含_<isfirst>标记（可能在句子中间）
            if '_<isfirst>' in sentence:
                # 清空文本流
                self._clear_Stream_internal(username)
                # 清空音频队列（打断时需要清空音频）
                self._clear_audio_queue(username)
            try:
                Stream, nlp_Stream = self.get_Stream(username)
                success = Stream.write(sentence)
                nlp_success = nlp_Stream.write(sentence)
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

    def _clear_audio_queue(self, username):
        """
        清空指定用户的音频队列
        :param username: 用户名
        """
        import queue
        fay_core = fay_booter.feiFei
        fay_core.sound_query = queue.Queue()

    def clear_Stream(self, username):
        """
        清除指定用户ID的文本流数据（外部调用接口，仅清除文本流）
        :param username: 用户名
        """
        with self.lock:
            self._clear_Stream_internal(username)

    def clear_Stream_with_audio(self, username):
        """
        清除指定用户ID的文本流数据和音频队列（完全清除）
        :param username: 用户名
        """
        with self.lock:
            self._clear_Stream_internal(username)
            self._clear_audio_queue(username)

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
        fay_core = fay_booter.feiFei

        is_first = "_<isfirst>" in sentence
        is_end = "_<isend>" in sentence
        sentence = sentence.replace("_<isfirst>", "").replace("_<isend>", "")

        if sentence or is_first or is_end :
            interact = Interact("stream", 1, {"user": username, "msg": sentence, "isfirst" : is_first, "isend" : is_end})
            fay_core.say(interact, sentence)  # 调用核心处理模块进行响应
        time.sleep(0.01)  # 短暂休眠以控制处理频率
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

    def get_Stream(self, uid):
        """
        获取指定用户ID的文本流，如果不存在则创建新的
        :param uid: 用户ID
        :return: 对应的句子缓存对象
        """
        need_start_thread = False
        stream = None
        nlp_stream = None
        
        with self.lock:
            if uid not in self.streams or uid not in self.nlp_streams:
                self.streams[uid] = stream_sentence.SentenceCache(self.max_sentences)
                self.nlp_streams[uid] = stream_sentence.SentenceCache(self.max_sentences)
                need_start_thread = True
                stream = self.streams[uid]
                nlp_stream = self.nlp_streams[uid]
                
                if need_start_thread:
                    thread = MyThread(target=self.listen, args=(uid, stream, nlp_stream), daemon=True)
                    self.listener_threads[uid] = thread
                    thread.start()
            else:
                stream = self.streams[uid]
                nlp_stream = self.nlp_streams[uid]
                
        return stream, nlp_stream

    def write_sentence(self, uid, sentence):
        """
        写入句子到指定用户的文本流
        :param uid: 用户ID
        :param sentence: 要写入的句子
        :return: 写入是否成功
        """
        if sentence.endswith('_<isfirst>'):
            self.clear_Stream(uid)
        Stream, nlp_Stream = self.get_Stream(uid)
        success = Stream.write(sentence)
        nlp_success = nlp_Stream.write(sentence)
        return success and nlp_success

    def clear_Stream(self, uid):
        """
        清除指定用户ID的文本流数据
        :param uid: 用户ID
        """
        with self.lock:
            if uid in self.streams:
                self.streams[uid].clear()
            if uid in self.nlp_streams:
                self.nlp_streams[uid].clear()

    def listen(self, uid, stream, nlp_stream):
        username = member_db.new_instance().find_username_by_uid(uid)
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
            # 处理普通消息，区分是否是会话的第一句
        if sentence.endswith('_<isfirst>'):
            sentence = sentence[:-len('_<isfirst>')]
            interact = Interact("stream", 1, {'user': username, 'msg': sentence, 'isfirst': True})
        elif sentence.endswith('_<isend>'):
            sentence = sentence[:-len('_<isend>')]
            interact = Interact("stream", 1, {'user': username, 'msg': sentence, 'isend': True})
        else:
            interact = Interact("stream", 1, {'user': username, 'msg': sentence})
        fay_core.say(interact, sentence)  # 调用核心处理模块进行响应
        # MyThread(target=fay_core.say, args=[interact, sentence]).start()  # 异步处理方式（已注释）
        time.sleep(0.01)  # 短暂休眠以控制处理频率
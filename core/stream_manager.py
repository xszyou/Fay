import threading
import time
from utils import stream_sentence
from scheduler.thread_manager import MyThread
import fay_booter
from core import member_db
from core.interact import Interact

__streams = None
__streams_lock = threading.Lock()

def new_instance(max_sentences=1024):
    global __streams
    with __streams_lock:
        if __streams is None:
            __streams = StreamManager(max_sentences)
    return __streams

class StreamManager:
    def __init__(self, max_sentences=3):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self.lock = threading.Lock()
        self.streams = {}
        self.max_sentences = max_sentences
        self.listener_threads = {}
        self.running = True
        self._initialized = True
        self.msgid = ""

    def get_Stream(self, uid):
        need_start_thread = False
        with self.lock:
            if uid not in self.streams:
                self.streams[uid] = stream_sentence.SentenceCache(self.max_sentences)
                need_start_thread = True
        if need_start_thread:
            thread = MyThread(target=self.listen, args=(uid,), daemon=True)
            with self.lock:
                self.listener_threads[uid] = thread
            thread.start()
        return self.streams[uid]

    def write_sentence(self, uid, sentence):
        if sentence.endswith('_<isfirst>'):
            self.clear_Stream(uid)
        Stream = self.get_Stream(uid)
        success = Stream.write(sentence)
        return success

    def clear_Stream(self, uid):
        with self.lock:
            if uid in self.streams:
                self.streams[uid].clear()


    def listen(self, uid):
        Stream = self.streams[uid]
        username = member_db.new_instance().find_username_by_uid(uid)
        while self.running:
            sentence = Stream.read()
            if sentence:
                self.execute(username, sentence)
            else:
                time.sleep(0.1)

    def execute(self, username, sentence):
        fay_core = fay_booter.feiFei
        if sentence.endswith('_<hello>'):
            sentence = sentence[:-len('_<hello>')]
            interact = Interact("hello", 1, {'user': username, 'msg': sentence})
        else:
            if sentence.endswith('_<isfirst>'):
                sentence = sentence[:-len('_<isfirst>')]
                interact = Interact("stream", 1, {'user': username, 'msg': sentence, 'isfirst': True})
            else:
                interact = Interact("stream", 1, {'user': username, 'msg': sentence, 'isfirst': False})
        fay_core.say(interact, sentence)
        # MyThread(target=fay_core.say, args=[interact, sentence]).start()
        time.sleep(0.1)
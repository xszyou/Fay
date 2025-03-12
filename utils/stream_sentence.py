import threading
import functools

def synchronized(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return func(self, *args, **kwargs)
    return wrapper

class SentenceCache:
    def __init__(self, max_sentences):
        self.lock = threading.Lock()
        self.buffer = [None] * max_sentences
        self.max_sentences = max_sentences
        self.writeIndex = 0
        self.readIndex = 0
        self.idle = 0


    @synchronized
    def write(self, sentence):
        # 如果缓冲区已满，则无法写入
        if self.idle == self.max_sentences:
            print("缓存区不够用")
            return False
        self.buffer[self.writeIndex] = sentence
        self.writeIndex = (self.writeIndex + 1) % self.max_sentences
        self.idle += 1
        return True

    @synchronized
    def read(self):
        # 如果缓冲区为空，没有可读的句子
        if self.idle == 0:
            return None
        sentence = self.buffer[self.readIndex]
        self.buffer[self.readIndex] = None
        self.readIndex = (self.readIndex + 1) % self.max_sentences
        self.idle -= 1
        return sentence

    @synchronized
    def clear(self):
        self.buffer = [None] * self.max_sentences
        self.writeIndex = 0
        self.readIndex = 0
        self.idle = 0

if __name__ == '__main__':
    cache = SentenceCache(3)
    cache.write("这是第一句话。")
    cache.write("这是第二句话。")
    print(cache.read())  # 读出第一句话
    cache.write("这是第三句话。")
    print(cache.read())  # 读出第二句话
    print(cache.read())  # 读出第三句话
    print(cache.read())  # 无内容，返回None

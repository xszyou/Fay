from io import BytesIO
import threading
import functools

def synchronized(func):
  @functools.wraps(func)
  def wrapper(self, *args, **kwargs):
    with self.lock:
      return func(self, *args, **kwargs)
  return wrapper

class StreamCache:
    def __init__(self, maxbytes):
        self.lock = threading.Lock()
        self.bytesio = BytesIO()
        self.writeSeek = 0
        self.readSeek = 0
        self.maxbytes = maxbytes
        self.idle = 0
        
    @synchronized
    def write(self, bs):
        # print("写:{},{}".format(len(bs),bs), end=' ')
        if self.idle >= self.maxbytes:
            print("缓存区不够用")
        self.bytesio.seek(self.writeSeek)
        if self.writeSeek + len(bs) <= self.maxbytes:
            self.bytesio.write(bs)
        else:
            self.bytesio.write(bs[0:self.maxbytes - self.writeSeek])
            self.bytesio.seek(0)
            self.bytesio.write(bs[self.maxbytes - self.writeSeek:])
        self.idle += len(bs)
        self.writeSeek = self.bytesio.tell()
        if self.writeSeek >= self.maxbytes - 1:
            self.writeSeek = 0

    
    @synchronized
    def read(self, length, exception_on_overflow = False):
        if self.idle < length:
            return None
        # print("读:{}".format(length), end=' ')
        self.bytesio.seek(self.readSeek)
        if self.readSeek + length <= self.maxbytes:
            bs = self.bytesio.read(length)
        else:
            bs = self.bytesio.read(self.maxbytes - self.readSeek)
            self.bytesio.seek(0)
            bs.append(self.bytesio.read(self.readSeek + length - self.maxbytes))

        self.idle -= length
        self.readSeek = self.bytesio.tell()
        if self.readSeek >= self.maxbytes - 1:
           self.readSeek = 0
        return bs

    @synchronized
    def clear(self):
        self.bytesio = BytesIO()
        self.writeSeek = 0
        self.readSeek = 0
        self.idle = 0

if __name__ == '__main__':
    streamCache = StreamCache(5)
    streamCache.write(b'\x01\x02')
    streamCache.write(b'\x03\x04\x00')
    print(streamCache.read(2))
    print(streamCache.read(3))
    streamCache.write(b'\x05\x06')
    print(streamCache.read(2))
    print(streamCache.read(2))
    print(streamCache.read(3))


    


    



        
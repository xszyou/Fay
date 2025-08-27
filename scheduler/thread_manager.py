import ctypes
import threading
from threading import Thread


class MyThread(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        Thread.__init__(self, group=group, target=target, name=name, args=args, kwargs=kwargs, daemon=daemon)
        add_thread(self)

    def get_id(self):
        # returns id of the respective thread
        if hasattr(self, '_thread_id'):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id

    def raise_exception(self):
        thread_id = self.get_id()
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('Exception raise failure')


__thread_list = []


def add_thread(thread: MyThread):
    if thread not in __thread_list:
        __thread_list.append(thread)


def remove_thread(thread: MyThread):
    if thread in __thread_list:
        __thread_list.remove(thread)


def stopAll():
    """停止所有MyThread线程"""
    if not __thread_list:
        return
    
    # 先尝试正常停止
    stopped_threads = []
    for thread in __thread_list[:]:  # 使用副本避免修改时出错
        try:
            if thread.is_alive():
                thread.raise_exception()
                stopped_threads.append(thread)
        except Exception as e:
            print(f"停止线程异常: {e}")
    
    # 等待线程结束，但设置超时避免无限等待
    import time
    for thread in stopped_threads:
        try:
            thread.join(timeout=2.0)  # 最多等待2秒
            if thread.is_alive():
                print(f"线程 {thread.name} 超时未结束")
        except Exception as e:
            print(f"等待线程结束异常: {e}")
    
    # 清空线程列表
    __thread_list.clear()

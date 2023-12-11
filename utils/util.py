import codecs
import os
import sys
import random
import time

from core import wsa_server
from scheduler.thread_manager import MyThread
from utils import config_util

LOGS_FILE_URL = "logs/log-" + time.strftime("%Y%m%d%H%M%S") + ".log"


def random_hex(length):
    result = hex(random.randint(0, 16 ** length)).replace('0x', '').lower()
    if len(result) < length:
        result = '0' * (length - len(result)) + result
    return result


def __write_to_file(text):
    if not os.path.exists("logs"):
        os.mkdir("logs")
    file = codecs.open(LOGS_FILE_URL, 'a', 'utf-8')
    file.write(text + "\n")
    file.close()


def printInfo(level, sender, text, send_time=-1):
    if send_time < 0:
        send_time = time.time()
    format_time = time.strftime('%H:%M:%S', time.localtime(send_time))
    logStr = '[{}][{}] {}'.format(format_time, sender, text)
    print(logStr)
    if level >= 3:
        wsa_server.get_web_instance().add_cmd({"panelMsg": text})
        if not config_util.config["interact"]["playSound"]: # 非展板播放
            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': text}}
            wsa_server.get_instance().add_cmd(content)
    MyThread(target=__write_to_file, args=[logStr]).start()


def log(level, text):
    printInfo(level, "系统", text)

class DisablePrint:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout
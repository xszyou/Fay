import codecs
import os
import random
import time

from core import wsa_server
from scheduler.thread_manager import MyThread

from urllib.parse import urlparse
from profanity import profanity
import ahocorasick
import re

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
    MyThread(target=__write_to_file, args=[logStr]).start()


def log(level, text):
    printInfo(level, "系统", text)

def is_url_check(url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False
        
def profanity_content(content):
    return profanity.contains_profanity(content)

def check_sensitive_words(file_path, text):
        with open(file_path, 'r', encoding='utf-8') as file:
            sensitive_words = [line.strip() for line in file.readlines()]

        # 创建 Aho-Corasick 自动机
        automaton = ahocorasick.Automaton()

        # 添加违禁词到自动机中
        for word in sensitive_words:
            automaton.add_word(word, word)

        # 构建自动机的转移函数和失效函数
        automaton.make_automaton()

        # 在文本中搜索违禁词
        for _, found_word in automaton.iter(text):
            log(1, f"命中本地违禁词：{found_word}")
            return found_word

        return None

def is_punctuation_string(string):
        # 使用正则表达式匹配标点符号
        pattern = r'^[^\w\s]+$'
        return re.match(pattern, string) is not None

def replace_emoji(string):
     content = re.sub(r'\[.*?\]', '', string)
     return content
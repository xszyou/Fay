import codecs
import os
import sys
import random
import time
import socket

from core import wsa_server
from scheduler.thread_manager import MyThread
from utils import config_util

LOGS_FILE_URL = "logs/log-" + time.strftime("%Y%m%d%H%M%S") + ".log"


def get_local_ip():
    """
    获取本机IP地址
    
    返回:
        str: 本机IP地址，如果获取失败则返回127.0.0.1
    """
    try:
        # 创建一个临时socket连接，用于获取本机IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 连接任意可用地址（不需要真正建立连接）
        s.connect(("8.8.8.8", 80))
        # 获取本机IP地址
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        log(1, f"获取本机IP地址失败: {str(e)}")
        return "127.0.0.1"


def random_hex(length):
    result = hex(random.randint(0, 16 ** length)).replace('0x', '').lower()
    if len(result) < length:
        result = '0' * (length - len(result)) + result
    return result


def __write_to_file(text):
    """
    将文本写入日志文件
    
    参数:
        text: 要写入的文本
    """
    try:
        if not os.path.exists("logs"):
            os.mkdir("logs")
        with codecs.open(LOGS_FILE_URL, 'a', 'utf-8') as file:
            file.write(text + "\n")
    except Exception as e:
        print(f"写入日志文件时出错: {str(e)}")


def printInfo(level, sender, text, send_time=-1):
    """
    打印并记录信息
    
    参数:
        level: 日志级别
        sender: 发送者
        text: 日志内容
        send_time: 发送时间，默认为当前时间
    """
    try:
        # 确保text是字符串类型
        if not isinstance(text, str):
            text = str(text)
            
        if send_time < 0:
            send_time = time.time()
        format_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(send_time)) + f".{int(send_time % 1 * 10)}"
        logStr = '[{}][{}] {}'.format(format_time, sender, text)
        
        # 使用print函数打印日志，确保编码正确
        print(logStr)
        
        if level >= 3:
            # 发送日志到WebSocket服务器
            if wsa_server.get_web_instance().is_connected(sender):
                wsa_server.get_web_instance().add_cmd({"panelMsg": text} if sender == "系统" else {"panelMsg": text, "Username" : sender})
            if wsa_server.get_instance().is_connected(sender):
                content = {'Topic': 'human', 'Data': {'Key': 'log', 'Value': text}} if sender == "系统" else  {'Topic': 'human', 'Data': {'Key': 'log', 'Value': text}, "Username" : sender}
                wsa_server.get_instance().add_cmd(content)
            
            # 异步写入日志文件
            MyThread(target=__write_to_file, args=[logStr]).start()
    except Exception as e:
        print(f"处理日志时出错: {str(e)}")


def log(level, text):
    """
    记录系统日志
    
    参数:
        level: 日志级别
        text: 日志内容
    """
    try:
        # 确保text是字符串类型
        if not isinstance(text, str):
            text = str(text)
        printInfo(level, "系统", text)
    except Exception as e:
        print(f"记录系统日志时出错: {str(e)}")


class DisablePrint:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout
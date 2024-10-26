#入口文件main
import os
os.environ['PATH'] += os.pathsep + os.path.join(os.getcwd(), "test", "ovr_lipsync", "ffmpeg", "bin")
import sys
import time
import re
from utils import config_util
from asr import ali_nls
from core import wsa_server
from gui import flask_server
from gui.window import MainWindow
from core import content_db


#载入配置
config_util.load_config()

#是否为普通模式（桌面模式）
if config_util.start_mode == 'common':
    from PyQt5 import QtGui
    from PyQt5.QtWidgets import QApplication

#音频清理
def __clear_samples():
    if not os.path.exists("./samples"):
        os.mkdir("./samples")
    for file_name in os.listdir('./samples'):
        if file_name.startswith('sample-'):
            os.remove('./samples/' + file_name)

#日志文件清理
def __clear_logs():
    if not os.path.exists("./logs"):
        os.mkdir("./logs")
    for file_name in os.listdir('./logs'):
        if file_name.endswith('.log'):
            os.remove('./logs/' + file_name)
#ip替换
def replace_ip_in_file(file_path, new_ip):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    content = re.sub(r"127\.0\.0\.1", new_ip, content)
    content = re.sub(r"localhost", new_ip, content)
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)           
                   
if __name__ == '__main__':
    __clear_samples()
    __clear_logs()

    #init_db
    contentdb = content_db.new_instance()
    contentdb.init_db()

    #ip替换
    if config_util.fay_url != "127.0.0.1":
        replace_ip_in_file("gui/static/js/index.js", config_util.fay_url)

    #启动数字人接口服务
    ws_server = wsa_server.new_instance(port=10002)
    ws_server.start_server()

    #启动UI数据接口服务
    web_ws_server = wsa_server.new_web_instance(port=10003)
    web_ws_server.start_server()

    #启动阿里云asr
    if config_util.ASR_mode == "ali":
        ali_nls.start()

    #启动http服务器
    flask_server.start()

    #普通模式下启动窗口
    if config_util.start_mode == 'common':    
        app = QApplication(sys.argv)
        app.setWindowIcon(QtGui.QIcon('icon.png'))
        win = MainWindow()
        time.sleep(1)
        win.show()
        app.exit(app.exec_())
    else:
        while True:
            time.sleep(1) 

#入口文件main
import os
os.environ['PATH'] += os.pathsep + os.path.join(os.getcwd(), "test", "ovr_lipsync", "ffmpeg", "bin")
import sys
import time
import psutil
import re
import argparse
from utils import config_util, util
from asr import ali_nls
from core import wsa_server
from gui import flask_server
from core import content_db
import fay_booter
from scheduler.thread_manager import MyThread
from core.interact import Interact

#载入配置
config_util.load_config()

#是否为普通模式（桌面模式）
if config_util.start_mode == 'common':
    from PyQt5 import QtGui
    from PyQt5.QtWidgets import QApplication
    from gui.window import MainWindow

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

def __create_memory():
    if not os.path.exists("./memory"):
        os.mkdir("./memory")

def kill_process_by_port(port):
    for conn in psutil.net_connections(kind='inet'):
        if conn.laddr.port == port and conn.pid:
            try:
                proc = psutil.Process(conn.pid)
                proc.terminate()
                proc.wait()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass


#控制台输入监听
def console_listener():
    while True:
        try:
            text = input()
        except EOFError:
            util.log(1, "控制台已经关闭")
            break
        
        args = text.split(' ')

        if len(args) == 0 or len(args[0]) == 0:
            continue

        if args[0] == 'help':
            util.log(1, 'in <msg> \t通过控制台交互')
            util.log(1, 'restart \t重启服务')
            util.log(1, 'start \t\t启动服务')
            util.log(1, 'stop \t\t关闭服务')
            util.log(1, 'exit \t\t结束程序')

        elif args[0] == 'stop' and fay_booter.is_running():
            fay_booter.stop()
        
        elif args[0] == 'start' and not fay_booter.is_running():
            fay_booter.start()

        elif args[0] == 'restart' and fay_booter.is_running():
            fay_booter.stop()
            time.sleep(0.1)
            fay_booter.start()

        elif args[0] == 'in' and fay_booter.is_running():
            if len(args) == 1:
                util.log(1, '错误的参数！')
            msg = text[3:len(text)]
            util.printInfo(3, "控制台", '{}: {}'.format('控制台', msg))
            interact = Interact("console", 1, {'user': 'User', 'msg': msg})
            thr = MyThread(target=fay_booter.feiFei.on_interact, args=[interact])
            thr.start()

        elif args[0]=='exit':
            if  fay_booter.is_running():
                fay_booter.stop()
                time.sleep(0.1)
                util.log(1,'程序正在退出..')
            ports =[10001, 10002, 10003, 5000, 9001]
            for port in ports:
                kill_process_by_port(port)
            sys.exit(0)
        else:
            util.log(1, '未知命令！使用 \'help\' 获取帮助.')



if __name__ == '__main__':
    __clear_samples()
    __create_memory()
    __clear_logs()

    #init_db
    contentdb = content_db.new_instance()
    contentdb.init_db()

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

    #启动mcp service
    util.log(1, '启动mcp service...')
    from faymcp import mcp_service
    MyThread(target=mcp_service.start).start()

    #监听控制台
    util.log(1, '注册命令...')
    MyThread(target=console_listener).start()

    util.log(1, 'restart \t重启服务')
    util.log(1, 'start \t\t启动服务')
    util.log(1, 'stop \t\t关闭服务')
    util.log(1, 'exit \t\t结束程序')
    util.log(1, '使用 \'help\' 获取帮助.')
    if config_util.start_mode == 'web':
        util.log(1, '请通过浏览器访问 http://127.0.0.1:5000/ 管理您的Fay')

    parser = argparse.ArgumentParser(description="start自启动")
    parser.add_argument('command', nargs='?', default='', help="start")

    parsed_args = parser.parse_args()
    if parsed_args.command.lower() == 'start':
        MyThread(target=fay_booter.start).start()


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

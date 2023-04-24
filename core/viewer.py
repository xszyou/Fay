from abc import abstractmethod
import json
import random
import time
import requests
import websocket
import ssl

from core.interact import Interact
from scheduler.thread_manager import MyThread
from utils import config_util, util

USER_URL = 'https://www.douyin.com/user/'

interact_datas = []
import json
import time
import ssl
import websocket


running = False
class WS_Client:
    def __init__(self, host):
        self.__ws = None
        self.__host = host
        self.__connect(host)

    def on_message(self, ws, message):
        global interact_datas
        try:
            
            data = json.loads(message)
            if data["Type"] == 1:#留言
                if len(interact_datas) >= 5:
                    interact_datas.pop()
                interact = Interact("live", 1, {"user": json.loads(data["Data"])["User"]["Nickname"], "msg": json.loads(data["Data"])["Content"]})
                interact_datas.append(interact)
            if data["Type"] == 3:#进入
                if len(interact_datas) >= 5:
                    interact_datas.pop()
                interact_datas.append(Interact("live", 2, {"user": json.loads(data["Data"])["User"]["Nickname"], "msg": "来了"}))
            #...
        except Exception as e:
            pass

    def on_close(self, ws, code, msg):
        pass

    def on_error(self, ws, error):
        util.log(1, "弹幕监听WebSocket error. Reconnecting...")
        time.sleep(5)
        self.__connect(self.__host)

    def on_open(self, ws):
        pass

    def __connect(self, host):
        global running
        while running:
            try:
                self.__ws = websocket.WebSocketApp(host,
                                                   on_message=self.on_message,
                                                   on_error=self.on_error,
                                                   on_close=self.on_close)
                self.__ws.on_open = self.on_open
                self.__ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
                util.log(1, "弹幕监听WebSocket success.")
                break
            except Exception as e:
                break

    def close(self):
        self.__ws.close()


class Viewer:

    def __init__(self):
        global running
        running = True
        self.live_started = False
        self.dy_msg_ws = None

    def __start(self):
        MyThread(target=self.__run_dy_msg_ws).start() #获取抖音监听内容
        self.live_started = True
        MyThread(target=self.__get_package_listen_interact_runnable).start()

    def __run_dy_msg_ws(self):
        self.dy_msg_ws = WS_Client('ws://127.0.0.1:8888')

    def start(self):
        MyThread(target=self.__start).start()

    def is_live_started(self):
        return self.live_started

    
    #Add by xszyou on 20230412.通过抓包监测互动数据
    def __get_package_listen_interact_runnable(self):
        global interact_datas
        global running
        while running:
            if not self.live_started:
                continue
            
            for interact in interact_datas:
                MyThread(target=self.on_interact, args=[interact, time.time()]).start()
            interact_datas.clear()

    def stop(self):
        global running
        running = False
        if self.dy_msg_ws:
            self.dy_msg_ws.close()
            self.dy_msg_ws = None
            
    
    @abstractmethod
    def on_interact(self, interact, event_time):
        pass

    @abstractmethod
    def on_change_state(self, is_live_started):
        pass

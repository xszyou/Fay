"""
基于阿里达摩院流失代码适配Fay项目而来
"""
from threading import Thread
import websocket, ssl
from websocket import ABNF
from websocket import create_connection
import json
import time
import ssl
import _thread as thread

from core import wsa_server
from utils import config_util as cfg
from utils import util

import argparse
import traceback
import threading

class FunASRWSS:

    # 初始化(模型选择2pass-online，online，offline， 2pass)
    def __init__(self, host="127.0.0.1",
                 port="10197",
                 is_ssl=True,
                 chunk_size="0, 10, 5",
                 chunk_interval=10,
                 mode="online",
                 wav_name="default"):
        
        self.host = host
        self.port = port

        self.chunk_size=chunk_size
        self.chunk_interval=chunk_interval
        self.mode=mode
        self.wav_name=wav_name

        if cfg.local_asr_ip != None:
            self.host = cfg.local_asr_ip
        if cfg.local_asr_port != None:
            self.port = cfg.local_asr_port

        try:
            if is_ssl == True:
                self.ssl_context = ssl.SSLContext()
                self.ssl_context.check_hostname = False
                self.ssl_context.verify_mode = ssl.CERT_NONE
                self.__URL = "wss://{}:{}".format(self.host, self.port)
                self.ssl_opt={"cert_reqs": ssl.CERT_NONE}
            else:
                self.__URL = "ws://{}:{}".format(self.host, self.port)
                self.ssl_context = None
                self.ssl_opt=None
            self.host = cfg.local_asr_ip
            self.port = cfg.local_asr_port
            print("connect to", self.__URL)

            self.__ws = None
            self.__connected = False
            self.__frames = []
            self.__state = 0
            self.__closing = False
            self.__task_id = ''
            self.done = False
            self.finalResults = ""
            self.__reconnect_delay = 1
            self.__reconnecting = False
            
            # self.__ws = websocket.WebSocketApp(self.__URL, on_message=self.on_message,on_close=self.on_close,on_error=self.on_error,subprotocols=["binary"])
            # self.__ws.run_forever(sslopt={"cert_reqs": self.ssl_opt})
            # print("connect to url to test===============",self.__URL)
            # self.websocket=create_connection(self.__URL, ssl=self.ssl_context, sslopt=self.ssl_opt)
            # self.thread_msg = threading.Thread(target=FunASRWSS.on_message2, args=(self,))
            # self.thread_msg.start()
            # message = json.dumps({"mode": mode,
            #                     "chunk_size": chunk_size,
            #                     "encoder_chunk_look_back": 4,
            #                     "decoder_chunk_look_back": 1,
            #                     "chunk_interval": chunk_interval,
            #                     "wav_name": wav_name,
            #                     "is_speaking": True})
            # self.websocket.send(message)
            # print("send json",message)
            
        except Exception as e:
                print("Exception:", e)
                traceback.print_exc()

    def __on_msg(self):
        pass
    
    def on_message2(self):
        print(f"Received on_message2:===========")
        try:
         while(True):
           msg=self.websocket.recv()
           if msg is None or len(msg) == 0:
             continue
           msg = json.loads(msg)
           
           self.msg_queue.put(msg)
        except Exception as e:
            print("client closed")

    # 收到websocket消息的处理
    def on_message(self, ws, message):
        print(f"Received message: {message}")
        try:
            self.done = True
            self.finalResults = message
            wsa_server.get_web_instance().add_cmd({"panelMsg": self.finalResults})
            if not cfg.config["interact"]["playSound"]: # 非展板播放
                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': self.finalResults}}
                wsa_server.get_instance().add_cmd(content)
            self.__on_msg()

        except Exception as e:
            print(e)

        if self.__closing:
            try:
                self.__ws.close()
            except Exception as e:
                print(e)

    def close2(self,timeout=1):
        message = json.dumps({"is_speaking": False})
        self.websocket.send(message)
        # sleep for timeout seconds to wait for result
        time.sleep(timeout)
        msg=""
        while(not self.msg_queue.empty()):
            msg = self.msg_queue.get()
        
        self.websocket.close()
        # only resturn the last msg
        return msg

    # 收到websocket错误的处理
    def on_close(self, ws, code, msg):
        self.__connected = False
        util.log(1, f"### CLOSE:{msg}")
        self.__ws = None
        self.__attempt_reconnect()

    # 收到websocket错误的处理
    def on_error(self, ws, error):
        self.__connected = False
        util.log(1, f"### error:{error}")
        self.__ws = None
        self.__attempt_reconnect()

    #重连
    def __attempt_reconnect(self):
        if not self.__reconnecting:
            self.__reconnecting = True
            util.log(1, "尝试重连funasr...")
            while not self.__connected:
                time.sleep(self.__reconnect_delay)
                self.start()
                self.__reconnect_delay *= 2  
            self.__reconnect_delay = 1  
            self.__reconnecting = False

    # feed data to asr engine, wait_time means waiting for result until time out
    def feed_chunk(self, chunk, wait_time=0.01):
        try:
            self.websocket.send(chunk,  ABNF.OPCODE_BINARY)
            # loop to check if there is a message, timeout in 0.01s
            while(True):
               msg = self.msg_queue.get(timeout=wait_time)
               if self.msg_queue.empty():
                  break
                  
            return msg
        except:
            return ""
    
    # 收到websocket连接建立的处理
    def on_open(self, ws):
        util.log(1, "Connection opened......")
        self.__connected = True

        def run(*args):
            while self.__connected:
                try:
                    if len(self.__frames) > 0:
                        frame = self.__frames[0]

                        self.__frames.pop(0)
                        util.log(1, "=============frame====================")
                        util.log(1, frame)
                        util.log(1, "=============frame====================")
                        if type(frame) == dict:
                            ws.send(json.dumps(frame))
                        elif type(frame) == bytes:
                            ws.send(frame, websocket.ABNF.OPCODE_BINARY)
                        # print('发送 ------> ' + str(type(frame)))
                except Exception as e:
                    print(e)
                time.sleep(0.04)

        thread.start_new_thread(run, ())

    def __connect(self):
        self.finalResults = ""
        self.done = False
        self.__frames.clear()
        websocket.enableTrace(True)
        util.log(1, "__connect 111111111111......")
        self.__ws = websocket.WebSocketApp(self.__URL, on_message=self.on_message,on_close=self.on_close,on_error=self.on_error)
        # #util.log(1, "__connect222222222222 ......")
        self.__ws.on_open = self.on_open
        # self.__ws=create_connection(uri, ssl=ssl_context, sslopt=ssl_opt)
        # #util.log(1, "__connect23333333333333 ......")
        self.__ws.run_forever(sslopt={"cert_reqs": self.ssl_opt})

    def add_frame(self, frame):
        util.log(1, '------add_frame-------------')
        util.log(1, frame)
        util.log(1, '------add_frame-------------')
        self.__frames.append(frame)

    def send(self, buf):
        util.log(1, '------send-------------')
        util.log(1, buf)
        util.log(1, '------send-------------')
        self.__frames.append(buf)

    def send_url(self, url):
        frame = {'url' : url}
        util.log(1, '------send_url-------------')
        util.log(1, frame)
        util.log(1, '------send_url-------------')
        self.__ws.send(json.dumps(frame))

    def start(self):
        util.log(1, '------start-------------')
        Thread(target=self.__connect, args=[]).start()
        data = {
                'vad_need':False,
                'state':'StartTranscription'
        }

        message = json.dumps({"mode": self.mode,
                                "chunk_size": self.chunk_size,
                                "encoder_chunk_look_back": 4,
                                "decoder_chunk_look_back": 1,
                                "chunk_interval": self.chunk_interval,
                                "wav_name": self.wav_name,
                                "is_speaking": True})
        self.add_frame(message)

    def end(self):
        if self.__connected:
            try:
                for frame in self.__frames:
                    self.__frames.pop(0)
                    if type(frame) == dict:
                        self.__ws.send(json.dumps(frame))
                    elif type(frame) == bytes:
                        self.__ws.send(frame, websocket.ABNF.OPCODE_BINARY)
                    time.sleep(0.4)
                self.__frames.clear()
                frame = {'vad_need':False,'state':'StopTranscription'}
                message = {"mode": self.mode,
                                "chunk_size": self.chunk_size,
                                "encoder_chunk_look_back": 4,
                                "decoder_chunk_look_back": 1,
                                "chunk_interval": self.chunk_interval,
                                "wav_name": self.wav_name,
                                "is_speaking": True}
                self.__ws.send(json.dumps(message))
            except Exception as e:
                print(e)
        self.__closing = True
        self.__connected = False

from threading import Thread

import websocket
import json
import time
import ssl
import _thread as thread
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

from core import wsa_server, song_player
from scheduler.thread_manager import MyThread
from utils import util
from utils import config_util as cfg

__running = True
__my_thread = None
_token = ''


def __post_token():
    global _token
    __client = AcsClient(
        cfg.key_ali_nls_key_id,
        cfg.key_ali_nls_key_secret,
        "cn-shanghai"
    )

    __request = CommonRequest()
    __request.set_method('POST')
    __request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')
    __request.set_version('2019-02-28')
    __request.set_action_name('CreateToken')
    _token = json.loads(__client.do_action_with_exception(__request))['Token']['Id']


def __runnable():
    while __running:
        __post_token()
        time.sleep(60 * 60 * 12)


def start():
    MyThread(target=__runnable).start()


class ALiNls:
    # 初始化
    def __init__(self):
        self.__URL = 'wss://nls-gateway-cn-shenzhen.aliyuncs.com/ws/v1'
        self.__ws = None
        self.__connected = False
        self.__frames = []
        self.__state = 0
        self.__closing = False
        self.__task_id = ''
        self.done = False
        self.finalResults = ""

    def __create_header(self, name):
        if name == 'StartTranscription':
            self.__task_id = util.random_hex(32)
        header = {
            "appkey": cfg.key_ali_nls_app_key,
            "message_id": util.random_hex(32),
            "task_id": self.__task_id,
            "namespace": "SpeechTranscriber",
            "name": name
        }
        return header

    def __on_msg(self):
        if "暂停" in self.finalResults or "不想听了" in self.finalResults or "别唱了" in self.finalResults:
            song_player.stop()

    # 收到websocket消息的处理
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            header = data['header']
            name = header['name']
            if name == 'SentenceEnd':
                self.done = True
                self.finalResults = data['payload']['result']
                wsa_server.get_web_instance().add_cmd({"panelMsg": self.finalResults})
                if not cfg.config["interact"]["playSound"]: # 非展板播放
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': self.finalResults}}
                    wsa_server.get_instance().add_cmd(content)
                self.__on_msg()
            elif name == 'TranscriptionResultChanged':
                self.finalResults = data['payload']['result']
                wsa_server.get_web_instance().add_cmd({"panelMsg": self.finalResults})
                if not cfg.config["interact"]["playSound"]: # 非展板播放
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': self.finalResults}}
                    wsa_server.get_instance().add_cmd(content)
                self.__on_msg()

        except Exception as e:
            print(e)
        # print("### message:", message)
        if self.__closing:
            try:
                self.__ws.close()
            except Exception as e:
                print(e)

    # 收到websocket错误的处理
    def on_close(self, ws, code, msg):
        self.__connected = False
        print("### CLOSE:", msg)

    # 收到websocket错误的处理
    def on_error(self, ws, error):
        print("### error:", error)

    # 收到websocket连接建立的处理
    def on_open(self, ws):
        self.__connected = True

        # print("连接上了！！！")

        def run(*args):
            while self.__connected:
                try:
                    if len(self.__frames) > 0:
                        frame = self.__frames[0]

                        self.__frames.pop(0)
                        if type(frame) == dict:
                            ws.send(json.dumps(frame))
                        elif type(frame) == bytes:
                            ws.send(frame, websocket.ABNF.OPCODE_BINARY)
                        #print('发送 ------> ' + str(type(frame)))
                except Exception as e:
                    print(e)
                time.sleep(0.04)

        thread.start_new_thread(run, ())

    def __connect(self):
        self.finalResults = ""
        self.done = False
        self.__frames.clear()
        self.__ws = websocket.WebSocketApp(self.__URL + '?token=' + _token, on_message=self.on_message)
        self.__ws.on_open = self.on_open
        self.__ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    def add_frame(self, frame):
        self.__frames.append(frame)

    def send(self, buf):
        self.__frames.append(buf)

    def start(self):
        Thread(target=self.__connect, args=[]).start()
        data = {
            'header': self.__create_header('StartTranscription'),
            "payload": {
                "format": "pcm",
                "sample_rate": 16000,
                "enable_intermediate_result": True,
                "enable_punctuation_prediction": False,
                "enable_inverse_text_normalization": True,
                "speech_noise_threshold": -1
            }
        }
        self.add_frame(data)

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
                frame = {"header": self.__create_header('StopTranscription')}
                self.__ws.send(json.dumps(frame))
            except Exception as e:
                print(e)
        self.__closing = True
        self.__connected = False

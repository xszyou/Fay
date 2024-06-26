
import math
import os
import time
import socket

import eyed3
import logging


# 适应模型使用
import numpy as np
import fay_booter
from core import wsa_server
from core.interact import Interact
from scheduler.thread_manager import MyThread
from utils import util, config_util

import pygame
from utils import config_util as cfg
if cfg.tts_module =='openai':
    from ai_module.openai_tts import Speech
else:
    from ai_module.ms_tts_sdk import Speech

import platform
from ai_module import yolov8
from agent import agent_service
import fay_booter
from core import content_db
if platform.system() == "Windows":
    import sys
    sys.path.append("test/ovr_lipsync")
    from test_olipsync import LipSyncGenerator


#文本消息处理（20231211增加：agent操作）
def send_for_answer(msg):
        #记录运行时间
        fay_booter.feiFei.last_quest_time = time.time()

        #消息保存
        contentdb = content_db.new_instance()
        if "执行任务->" not in msg:
            contentdb.add_content('member', 'say', msg.replace('主人语音说了：', '').replace('主人文字说了：', ''))
            wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"member","content":msg.replace('主人语音说了：', '').replace('主人文字说了：', '')}})

        # 发送给数字人端    
        if not config_util.config["interact"]["playSound"]: 
            content = {'Topic': 'Unreal', 'Data': {'Key': 'question', 'Value': msg}}
            wsa_server.get_instance().add_cmd(content)

        #思考中...
        wsa_server.get_web_instance().add_cmd({"panelMsg": "思考中..."})
        if not cfg.config["interact"]["playSound"]: # 非展板播放
            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': "思考中..."}}
            wsa_server.get_instance().add_cmd(content)
        
        #agent 或llm chain处理
        is_use_say_tool, text = agent_service.agent.run(msg)
        wsa_server.get_web_instance().add_cmd({"panelMsg": ""})

      
        interact = Interact("audio", 1, {'user': '', 'msg': text})
        fay_booter.feiFei.on_interact(interact) 

        #消息保存
        contentdb.add_content("fay", "agent", text)
        wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"fay","content":text}})
        util.log(1, 'ReAct Agent或LLM Chain处理总时长：{} ms'.format(math.floor((time.time() - fay_booter.feiFei.last_quest_time) * 1000)))

        #推送数字人
        if not config_util.config["interact"]["playSound"]: 
            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': text}}
            wsa_server.get_instance().add_cmd(content)
            content = {'Topic': 'Unreal', 'Data': {'Key': 'text', 'Value': text}}
            wsa_server.get_instance().add_cmd(content)

        return text


class FeiFei:
    def __init__(self):
        pygame.mixer.init()
        self.q_msg = '你叫什么名字？'
        self.a_msg = 'hi,我叫菲菲，英文名是fay'
        self.connect = False
        self.item_index = 0
        self.deviceSocket = None
        self.deviceConnect = None

        #启动音频输入输出设备的连接服务
        self.deviceSocketThread = MyThread(target=self.__accept_audio_device_output_connect)
        self.deviceSocketThread.start()

        self.X = np.array([1, 0, 0, 0, 0, 0, 0, 0]).reshape(1, -1)  # 适应模型变量矩阵
        # self.W = np.array([0.01577594,1.16119452,0.75828,0.207746,1.25017864,0.1044121,0.4294899,0.2770932]).reshape(-1,1) #适应模型变量矩阵
        self.W = np.array([0.0, 0.6, 0.1, 0.7, 0.3, 0.0, 0.0, 0.0]).reshape(-1, 1)  # 适应模型变量矩阵

        self.wsParam = None
        self.wss = None
        self.sp = Speech()
        self.speaking = False
        self.interactive = []
        self.sleep = False
        self.__running = True
        self.sp.connect()  # 预连接
        self.last_quest_time = time.time()
        self.playing = False
        self.muting = False


    def __auto_speak(self):
        while self.__running:
            time.sleep(0.1)
            if self.speaking or self.sleep:
                continue

            try:
                if len(self.interactive) > 0:
                    interact: Interact = self.interactive.pop()
                    #开启fay eyes，无人时不回复
                    fay_eyes = yolov8.new_instance()            
                    if fay_eyes.get_status():#YOLO正在运行
                        person_count, stand_count, sit_count = fay_eyes.get_counts()
                        if person_count < 1: #看不到人，不互动
                                wsa_server.get_web_instance().add_cmd({"panelMsg": "看不到人，不互动"})
                                if not cfg.config["interact"]["playSound"]: # 非展板播放
                                    content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': "看不到人，不互动"}}
                                    wsa_server.get_instance().add_cmd(content)
                                    continue
                            
                        self.speaking = True
                    self.a_msg = interact.data["msg"]               
                    MyThread(target=self.__say, args=['interact']).start()

            except BaseException as e:
                print(e)

    def on_interact(self, interact: Interact):
        self.interactive.append(interact)
   
    def send_to_panel(self, msg):
        contentdb = content_db.new_instance()
        contentdb.add_content("fay", "agent_handling", msg)
        wsa_server.get_web_instance().add_cmd({"panelReply": {"type": "fay","content": msg}})
    
    # 适应模型计算(用于学习真人的性格特质，开源版本暂不使用)
    def __fay(self, index):
        if 0 < index < 8:
            self.X[0][index] += 1
        # PRED = 1 /(1 + tf.exp(-tf.matmul(tf.constant(self.X,tf.float32), tf.constant(self.W,tf.float32))))
        PRED = np.sum(self.X.reshape(-1) * self.W.reshape(-1))
        if 0 < index < 8:
            print('***PRED:{0}***'.format(PRED))
            print(self.X.reshape(-1) * self.W.reshape(-1))
        return PRED

    # 合成声音
    def __say(self, styleType):
        try:
            if len(self.a_msg) < 1:
                self.speaking = False
            else:
                util.printInfo(1, '菲菲', '({}) {}'.format(config_util.config["attribute"]["voice"], self.a_msg))
                if config_util.config["source"]["tts_enabled"]:
                    util.log(1, '合成音频...')
                    tm = time.time()
                    result = self.sp.to_sample(self.a_msg, config_util.config["attribute"]["voice"])
                    util.log(1, '合成音频完成. 耗时: {} ms 文件:{}'.format(math.floor((time.time() - tm) * 1000), result))
                    if result is not None:            
                        MyThread(target=self.__send_or_play_audio, args=[result, styleType]).start()
                        return result
                else:
                    util.log(1, '问答处理总时长：{} ms'.format(math.floor((time.time() - self.last_quest_time) * 1000)))
                    self.speaking = False
        except BaseException as e:
            print(e)
        self.speaking = False
        return None

    def __play_sound(self, file_url):
        util.log(1, '播放音频...')
        util.log(1, 'agent处理总时长：{} ms'.format(math.floor((time.time() - self.last_quest_time) * 1000)))
        pygame.mixer.music.load(file_url)
        pygame.mixer.music.play()


    def __send_or_play_audio(self, file_url, say_type):
        try:
            try:
                logging.getLogger('eyed3').setLevel(logging.ERROR)
                audio_length = eyed3.load(file_url).info.time_secs #mp3音频长度
            except Exception as e:
                audio_length = 3

            # with wave.open(file_url, 'rb') as wav_file: #wav音频长度
            #     audio_length = wav_file.getnframes() / float(wav_file.getframerate())
            #     print(audio_length)
            # if audio_length <= config_util.config["interact"]["maxInteractTime"] or say_type == "script":
            if config_util.config["interact"]["playSound"]: # 展板播放
                self.__play_sound(file_url)
            else:#发送音频给ue
                #推送ue
                content = {'Topic': 'Unreal', 'Data': {'Key': 'audio', 'Value': os.path.abspath(file_url), 'Text': self.a_msg, 'Time': audio_length, 'Type': say_type}}
                #计算lips
                if platform.system() == "Windows":
                    try:
                        lip_sync_generator = LipSyncGenerator()
                        viseme_list = lip_sync_generator.generate_visemes(os.path.abspath(file_url))
                        consolidated_visemes = lip_sync_generator.consolidate_visemes(viseme_list)
                        content["Data"]["Lips"] = consolidated_visemes
                    except Exception as e:
                        util.log(1, "唇型数字生成失败，无法使用新版ue5工程")
                wsa_server.get_instance().add_cmd(content)

            #推送远程音频
            if self.deviceConnect is not None:
                try:
                    self.deviceConnect.send(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08') # 发送音频开始标志，同时也检查设备是否在线
                    wavfile = open(os.path.abspath(file_url),'rb')
                    data = wavfile.read(1024)
                    total = 0
                    while data:
                        total += len(data)
                        self.deviceConnect.send(data)
                        data = wavfile.read(1024)
                        time.sleep(0.001)
                    self.deviceConnect.send(b'\x08\x07\x06\x05\x04\x03\x02\x01\x00')# 发送音频结束标志
                    util.log(1, "远程音频发送完成：{}".format(total))
                except socket.error as serr:
                    util.log(1,"远程音频输入输出设备已经断开：{}".format(serr))
                    wsa_server.get_web_instance().add_cmd({"remote_audio_connect": False})
                    
            time.sleep(audio_length + 0.5)
            wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
            if not cfg.config["interact"]["playSound"]: # 非展板播放
                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                wsa_server.get_instance().add_cmd(content)
            if config_util.config["interact"]["playSound"]:
                util.log(1, '结束播放！')
            self.speaking = False
        except Exception as e:
            print(e)

    def __device_socket_keep_alive(self):
        while True:
            if self.deviceConnect is not None:
                try:
                    self.deviceConnect.send(b'\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8')#发送心跳包
                except Exception as serr:
                    util.log(1,"远程音频输入输出设备已经断开：{}".format(serr))
                    self.deviceConnect = None
                    wsa_server.get_web_instance().add_cmd({"remote_audio_connect": False})
            time.sleep(5)

    def __accept_audio_device_output_connect(self):
        self.deviceSocket = socket.socket(socket.AF_INET,socket.SOCK_STREAM) 
        self.deviceSocket.bind(("0.0.0.0",10001))   
        self.deviceSocket.listen(1)
        addr = None        
        try:
            while True:
                self.deviceConnect,addr=self.deviceSocket.accept()   #接受TCP连接，并返回新的套接字与IP地址
                MyThread(target=self.__device_socket_keep_alive).start() # 开启心跳包检测
                util.log(1,"远程音频输入输出设备连接上：{}".format(addr))
                wsa_server.get_web_instance().add_cmd({"remote_audio_connect": True})
                while self.deviceConnect: #只允许一个设备连接
                    time.sleep(1)
        except Exception as err:
            pass

    def set_sleep(self, sleep):
        self.sleep = sleep

    def start(self):
        MyThread(target=self.__auto_speak).start()


    def stop(self):
        self.__running = False
        self.speaking = False
        self.playing = False
        self.sp.close()
        wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
        if not cfg.config["interact"]["playSound"]: # 非展板播放
            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
            wsa_server.get_instance().add_cmd(content)
        if self.deviceConnect is not None:
            self.deviceConnect.close()
            self.deviceConnect = None
        if self.deviceSocket is not None:
            self.deviceSocket.close()


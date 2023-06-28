import difflib
import math
import os
import random
import time
import wave
import socket
import json 

import eyed3
from openpyxl import load_workbook

# 适应模型使用
import numpy as np
# import tensorflow as tf
import fay_booter
from ai_module import xf_ltp
from ai_module.ms_tts_sdk import Speech
from core import wsa_server, tts_voice, song_player
from core.interact import Interact
from core.tts_voice import EnumVoice
from scheduler.thread_manager import MyThread
from utils import util, storer, config_util


import pygame
from utils import config_util as cfg
from core.content_db import Content_Db
from datetime import datetime
from ai_module import nlp_rasa
from ai_module import nlp_chatgpt
from ai_module import nlp_gpt
from ai_module import nlp_yuan
from ai_module import yolov8
from ai_module import nlp_VisualGLM

import platform
if platform.system() == "Windows":
    import sys
    sys.path.append("test/ovr_lipsync")
    from test_olipsync import LipSyncGenerator
    
from ai_module import nlp_lingju

modules = {
    "nlp_yuan": nlp_yuan, 
    "nlp_gpt": nlp_gpt,
    "nlp_chatgpt": nlp_chatgpt,
    "nlp_rasa": nlp_rasa,
    "nlp_VisualGLM": nlp_VisualGLM,
    "nlp_lingju": nlp_lingju
}


def determine_nlp_strategy(sendto,msg):
    text = ''
    textlist = []
    try:
        util.log(1, '自然语言处理...')
        tm = time.time()
        cfg.load_config()
        if sendto == 2:
            text = nlp_chatgpt.question(msg)
        else:
            module_name = "nlp_" + cfg.key_chat_module
            selected_module = modules.get(module_name)
            if selected_module is None:
                raise RuntimeError('灵聚key、yuan key、gpt key都没有配置！')   
            if cfg.key_chat_module == 'rasa':
                textlist = selected_module.question(msg)
                text = textlist[0]['text'] 
            else:
                text = selected_module.question(msg)  
            util.log(1, '自然语言处理完成. 耗时: {} ms'.format(math.floor((time.time() - tm) * 1000)))
            if text == '哎呀，你这么说我也不懂，详细点呗' or text == '':
                util.log(1, '[!] 自然语言无语了！')
                text = '哎呀，你这么说我也不懂，详细点呗'  
    except BaseException as e:
        print(e)
        util.log(1, '自然语言处理错误！')
        text = '哎呀，你这么说我也不懂，详细点呗'   

    return text,textlist
    
    



#文本消息处理
def send_for_answer(msg,sendto):
        contentdb = Content_Db()
        contentdb.add_content('member','send',msg)       
        text,textlist = determine_nlp_strategy(sendto,msg)
                
        contentdb.add_content('fay','send',text)
        wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"fay","content":text}})
        if len(textlist) > 1:
            i = 1
            while i < len(textlist):
                  contentdb.add_content('fay','send',textlist[i]['text'])
                  wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"fay","content":textlist[i]['text']}})
                  i+= 1
        return text


class FeiFei:
    def __init__(self):
        pygame.mixer.init()
        self.q_msg = '你叫什么名字？'
        self.a_msg = 'hi,我叫菲菲，英文名是fay'
        self.mood = 0.0  # 情绪值
        self.item_index = 0
        self.deviceSocket = None
        self.deviceConnect = None

        #启动音频输入输出设备的连接服务
        self.deviceSocketThread = MyThread(target=self.__accept_audio_device_output_connect)
        self.deviceSocketThread.start()

        self.X = np.array([1, 0, 0, 0, 0, 0, 0, 0]).reshape(1, -1)  # 适应模型变量矩阵
        # self.W = np.array([0.01577594,1.16119452,0.75828,0.207746,1.25017864,0.1044121,0.4294899,0.2770932]).reshape(-1,1) #适应模型变量矩阵
        self.W = np.array([0.0, 0.6, 0.1, 0.7, 0.3, 0.0, 0.0, 0.0]).reshape(-1, 1)  # 适应模型变量矩阵

        self.command_keyword = [
            [['播放歌曲', '播放音乐', '唱首歌', '放首歌', '听音乐', '你会唱歌吗', '我想首听歌'], 'playSong'],
            [['关闭', '再见', '你走吧'], 'stop'],
            [['静音', '闭嘴', '我想静静'], 'mute'],
            [['取消静音', '你在哪呢', '你可以说话了'], 'unmute'],
            [['换个性别', '换个声音'], 'changeVoice']
        ]

        # 人设提问关键字
        self.attribute_keyword = [
            [['你叫什么名字', '你的名字是什么'], 'name'],
            [['你是男的还是女的', '你是男生还是女生', '你的性别是什么', '你是男生吗', '你是女生吗', '你是男的吗', '你是女的吗', '你是男孩子吗', '你是女孩子吗', ], 'gender', ],
            [['你今年多大了', '你多大了', '你今年多少岁', '你几岁了', '你今年几岁了', '你今年几岁了', '你什么时候出生', '你的生日是什么', '你的年龄'], 'age', ],
            [['你的家乡在哪', '你的家乡是什么', '你家在哪', '你住在哪', '你出生在哪', '你的出生地在哪', '你的出生地是什么', ], 'birth', ],
            [['你的生肖是什么', '你属什么', ], 'zodiac', ],
            [['你是什么座', '你是什么星座', '你的星座是什么', ], 'constellation', ],
            [['你是做什么的', '你的职业是什么', '你是干什么的', '你的职位是什么', '你的工作是什么', '你是做什么工作的'], 'job', ],
            [['你的爱好是什么', '你有爱好吗', '你喜欢什么', '你喜欢做什么'], 'hobby'],
            [['联系方式', '联系你们', '怎么联系客服', '有没有客服'], 'contact']
        ]

        self.wsParam = None
        self.wss = None
        self.sp = Speech()
        self.speaking = False
        self.last_interact_time = time.time()
        self.last_speak_data = ''
        self.interactive = []
        self.sleep = False
        self.__running = True
        self.sp.connect()  # 预连接
        self.last_quest_time = time.time()
        self.playing = False
        self.muting = False

    def __string_similar(self, s1, s2):
        return difflib.SequenceMatcher(None, s1, s2).quick_ratio()

    def __read_qna(self, filename) -> list:
        qna = []
        try:
            wb = load_workbook(filename)
            sheets = wb.worksheets  # 获取当前所有的sheet
            sheet = sheets[0]
            for row in sheet.rows:
                if len(row) >= 2:
                    qna.append([row[0].value.split(";"), row[1].value])
        except BaseException as e:
            print("无法读取Q&A文件 {} -> ".format(filename) + str(e))
        return qna

    def __get_keyword(self, keyword_dict, text):
        last_similar = 0
        last_answer = ''
        for qa in keyword_dict:
            for quest in qa[0]:
                similar = self.__string_similar(text, quest)
                if quest in text:
                    similar += 0.3
                if similar > last_similar:
                    last_similar = similar
                    last_answer = qa[1]
        if last_similar >= 0.6:
            return last_answer
        return None

    def __play_song(self):
        self.playing = True
        song_player.play()
        self.playing = False
        wsa_server.get_web_instance().add_cmd({"panelMsg": ""})

    #检查是否命中指令或q&a
    def __get_answer(self, interleaver, text):
        if interleaver == "mic":
            #指令
            keyword = self.__get_keyword(self.command_keyword, text)
            if keyword is not None:
                if keyword == "playSong":
                    MyThread(target=self.__play_song).start()
                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                elif keyword == "stop":
                    fay_booter.stop()
                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                    wsa_server.get_web_instance().add_cmd({"liveState": 0})
                elif keyword == "mute":
                    self.muting = True
                    self.speaking = True
                    self.a_msg = "好的"
                    MyThread(target=self.__say, args=['interact']).start()
                    time.sleep(0.5)
                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                elif keyword == "unmute":
                    self.muting = False
                    return None
                elif keyword == "changeVoice":
                    voice = tts_voice.get_voice_of(config_util.config["attribute"]["voice"])
                    for v in tts_voice.get_voice_list():
                        if v != voice:
                            config_util.config["attribute"]["voice"] = v.name
                            break
                    config_util.save_config(config_util.config)
                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                return "NO_ANSWER"

        # 人设问答
        keyword = self.__get_keyword(self.attribute_keyword, text)
        if keyword is not None:
            return config_util.config["attribute"][keyword]

        # 全局问答
        answer = self.__get_keyword(self.__read_qna(config_util.config['interact']['QnA']), text)
        if answer is not None:
            return answer

    def __auto_speak(self):
        while self.__running:
            time.sleep(0.8)
            if self.speaking or self.sleep:
                continue

            try:
                if len(self.interactive) > 0:
                    interact: Interact = self.interactive.pop()
                    index = interact.interact_type
                    if index == 1:
                        self.q_msg = interact.data["msg"]

                        #fay eyes
                        fay_eyes = yolov8.new_instance()            
                        if fay_eyes.get_status():#YOLO正在运行
                            person_count, stand_count, sit_count = fay_eyes.get_counts()
                            if person_count < 1: #看不到人，不互动
                                 wsa_server.get_web_instance().add_cmd({"panelMsg": "看不到人，不互动"})
                                 continue

                        answer = self.__get_answer(interact.interleaver, self.q_msg)#确定是否命中指令或q&a
                        if(self.muting): #静音指令正在执行
                            wsa_server.get_web_instance().add_cmd({"panelMsg": "静音指令正在执行，不互动"})
                            continue

                        contentdb = Content_Db()    
                        contentdb.add_content('member','speak',self.q_msg)
                        wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"member","content":self.q_msg}})
                        text = ''
                        textlist = []
                        self.speaking = True
                        if answer is None:
                            wsa_server.get_web_instance().add_cmd({"panelMsg": "思考中..."})
                            text,textlist = determine_nlp_strategy(1,self.q_msg)
                        elif answer != 'NO_ANSWER': #语音内容没有命中指令,回复q&a内容
                            text = answer
                        self.a_msg = text
                        contentdb.add_content('fay','speak',self.a_msg)
                        wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"fay","content":self.a_msg}})
                        if len(textlist) > 1:
                            i = 1
                            while i < len(textlist):
                                contentdb.add_content('fay','speak',textlist[i]['text'])
                                wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"fay","content":textlist[i]['text']}})
                                i+= 1
                    wsa_server.get_web_instance().add_cmd({"panelMsg": self.a_msg})
                    self.last_speak_data = self.a_msg               
                    MyThread(target=self.__say, args=['interact']).start()

            except BaseException as e:
                print(e)

    def on_interact(self, interact: Interact):
        self.interactive.append(interact)
        MyThread(target=self.__update_mood, args=[interact.interact_type]).start()
        MyThread(target=storer.storage_live_interact, args=[interact]).start()


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

    # 发送情绪
    def __send_mood(self):
        while self.__running:
            time.sleep(3)
            if not self.sleep and not config_util.config["interact"]["playSound"]:
                content = {'Topic': 'Unreal', 'Data': {'Key': 'mood', 'Value': self.mood}}
                wsa_server.get_instance().add_cmd(content)

    # 更新情绪
    def __update_mood(self, typeIndex):
        perception = config_util.config["interact"]["perception"]
        if typeIndex == 1:
            try:
                result = xf_ltp.get_sentiment(self.q_msg)
                chat_perception = perception["chat"]
                if result == 2:
                    self.mood = self.mood + (chat_perception / 200.0)
                elif result == 0:
                    self.mood = self.mood - (chat_perception / 100.0)
            except BaseException as e:
                print("[System] 情绪更新错误！")
                print(e)

        elif typeIndex == 2:
            self.mood = self.mood + (perception["join"] / 100.0)

        elif typeIndex == 3:
            self.mood = self.mood + (perception["gift"] / 100.0)

        elif typeIndex == 4:
            self.mood = self.mood + (perception["follow"] / 100.0)

        if self.mood >= 1:
            self.mood = 1
        if self.mood <= -1:
            self.mood = -1

    def __get_mood_voice(self):
        voice = tts_voice.get_voice_of(config_util.config["attribute"]["voice"])
        if voice is None:
            voice = EnumVoice.XIAO_XIAO
        styleList = voice.value["styleList"]
        sayType = styleList["calm"]
        if -1 <= self.mood < -0.5:
            sayType = styleList["angry"]
        if -0.5 <= self.mood < -0.1:
            sayType = styleList["lyrical"]
        if -0.1 <= self.mood < 0.1:
            sayType = styleList["calm"]
        if 0.1 <= self.mood < 0.5:
            sayType = styleList["assistant"]
        if 0.5 <= self.mood <= 1:
            sayType = styleList["cheerful"]
        return sayType

    # 合成声音
    def __say(self, styleType):
        try:
            if len(self.a_msg) < 1:
                self.speaking = False
            else:
                util.printInfo(1, '菲菲', '({}) {}'.format(self.__get_mood_voice(), self.a_msg))
                MyThread(target=storer.storage_live_interact, args=[Interact('Fay', 0, {'user': 'Fay', 'msg': self.a_msg})]).start()
                util.log(1, '合成音频...')
                tm = time.time()
                #文字也推送出去，为了ue5
                if not config_util.config["interact"]["playSound"]: # 非展板播放
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'text', 'Value': self.a_msg}}
                    wsa_server.get_instance().add_cmd(content)
                result = self.sp.to_sample(self.a_msg, self.__get_mood_voice())
                util.log(1, '合成音频完成. 耗时: {} ms 文件:{}'.format(math.floor((time.time() - tm) * 1000), result))
                if result is not None:            
                    MyThread(target=self.__send_or_play_audio, args=[result, styleType]).start()
                    return result
        except BaseException as e:
            print(e)
        self.speaking = False
        return None

    def __play_sound(self, file_url):
        util.log(1, '播放音频...')
        util.log(1, '问答处理总时长：{} ms'.format(math.floor((time.time() - self.last_quest_time) * 1000)))
        pygame.mixer.music.load(file_url)
        pygame.mixer.music.play()


    def __send_or_play_audio(self, file_url, say_type):
        try:
            audio_length = eyed3.load(file_url).info.time_secs #mp3音频长度
            # with wave.open(file_url, 'rb') as wav_file: #wav音频长度
            #     audio_length = wav_file.getnframes() / float(wav_file.getframerate())
            #     print(audio_length)
            # if audio_length <= config_util.config["interact"]["maxInteractTime"] or say_type == "script":
            if config_util.config["interact"]["playSound"]: # 展板播放
                self.__play_sound(file_url)
            else:#发送音频给ue和socket
                #推送ue
                content = {'Topic': 'Unreal', 'Data': {'Key': 'audio', 'Value': os.path.abspath(file_url), 'Time': audio_length, 'Type': say_type}}
                #计算lips
                if platform.system() == "Windows":
                    lip_sync_generator = LipSyncGenerator()
                    viseme_list = lip_sync_generator.generate_visemes(os.path.abspath(file_url))
                    consolidated_visemes = lip_sync_generator.consolidate_visemes(viseme_list)
                    content["Data"]["Lips"] = consolidated_visemes
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
                    
            time.sleep(audio_length + 0.5)
            wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
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
            time.sleep(1)

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
                while self.deviceConnect: #只允许一个设备连接
                    time.sleep(1)
        except Exception as err:
            pass

    def set_sleep(self, sleep):
        self.sleep = sleep

    def start(self):
        MyThread(target=self.__send_mood).start()
        MyThread(target=self.__auto_speak).start()

    def stop(self):
        self.__running = False
        song_player.stop()
        self.speaking = False
        self.playing = False
        self.sp.close()
        wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
        if self.deviceConnect is not None:
            self.deviceConnect.close()
            self.deviceConnect = None
        if self.deviceSocket is not None:
            self.deviceSocket.close()


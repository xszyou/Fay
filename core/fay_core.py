import difflib
import math
import os
import random
import time
import wave

import eyed3
from openpyxl import load_workbook

# 适应模型使用
import numpy as np
# import tensorflow as tf

from ai_module import xf_aiui
from ai_module import xf_ltp
from ai_module.ms_tts_sdk import Speech
from core import wsa_server, tts_voice
from core.tts_voice import EnumVoice
from scheduler.thread_manager import MyThread
from utils import util, storer, config_util

import pygame


class FeiFei:
    def __init__(self):
        pygame.init()
        self.q_msg = '你叫什么名字？'
        self.a_msg = 'hi,我叫菲菲，英文名是fay'
        self.mood = 0.0  # 情绪值
        self.item_index = 0

        self.X = np.array([1, 0, 0, 0, 0, 0, 0, 0]).reshape(1, -1)  # 适应模型变量矩阵
        # self.W = np.array([0.01577594,1.16119452,0.75828,0.207746,1.25017864,0.1044121,0.4294899,0.2770932]).reshape(-1,1) #适应模型变量矩阵
        self.W = np.array([0.0, 0.6, 0.1, 0.7, 0.3, 0.0, 0.0, 0.0]).reshape(-1, 1)  # 适应模型变量矩阵

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

        # 商品提问关键字
        self.explain_keyword = [
            [['是什么'], 'intro'],
            [['怎么用', '使用场景', '有什么作用'], 'usage'],
            [['怎么卖', '多少钱', '售价'], 'price'],
            [['便宜点', '优惠', '折扣', '促销'], 'discount'],
            [['质量', '保证', '担保'], 'promise'],
            [['特点', '优点'], 'character'],
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

    def __get_answer(self, text):

        # 人设问答
        keyword = self.__get_keyword(self.attribute_keyword, text)
        if keyword is not None:
            return config_util.config["attribute"][keyword]

        # 全局问答
        answer = self.__get_keyword(self.__read_qna(config_util.config['interact']['QnA']), text)
        if answer is not None:
            return answer

        items = self.__get_item_list()

        if len(items) > 0:
            item = items[self.item_index]

            # 跨商品物品问答匹配
            for ite in items:
                name = ite["name"]
                if name != item["name"]:
                    if name in text or self.__string_similar(text, name) > 0.6:
                        item = ite
                        break

            # 商品介绍问答
            keyword = self.__get_keyword(self.explain_keyword, text)
            if keyword is not None:
                try:
                    return item["explain"][keyword]
                except BaseException as e:
                    print(e)

            # 商品问答
            answer = self.__get_keyword(self.__read_qna(item["QnA"]), text)
            if answer is not None:
                return answer

            return None

    def __get_list_answer(self, answers, text):
        last_similar = 0
        last_answer = ''
        for mlist in answers:
            for quest in mlist[0]:
                similar = self.__string_similar(text, quest)
                if quest in text:
                    similar += 0.3
                if similar > last_similar:
                    last_similar = similar
                    answer_list = mlist[1]
                    last_answer = answer_list[random.randint(0, len(answer_list) - 1)]
        # print("相似度: {}, 回答: {}".format(last_similar, last_answer))
        if last_similar >= 0.6:
            return last_answer
        return None

    def __auto_speak(self):
        i = 0
        script_index = 0
        while self.__running:
            time.sleep(0.8)
            if self.speaking or self.sleep:
                continue

            try:
                # 简化逻辑：默认执行带货脚本，带货脚本执行其间有人互动，则执行完当前脚本就回应最后三条互动，回应完继续执行带货脚本
                if i <= 3 and len(self.interactive) > i:
                    i += 1
                    interact = self.interactive[0 - i]
                    if interact[0] == 1:
                        self.q_msg = interact[2]
                    index = interact[0]
                    # print("index:{0}".format(index))
                    user_name = interact[1]
                    # self.__isExecute = True #!!!!

                    if index == 1:
                        answer = self.__get_answer(self.q_msg)
                        text = ''
                        if answer is None:
                            try:
                                wsa_server.get_web_instance().add_cmd({"panelMsg": "思考中..."})
                                util.log(1, '自然语言处理...')
                                tm = time.time()
                                text = xf_aiui.question(self.q_msg)
                                util.log(1, '自然语言处理完成. 耗时: {} ms'.format(math.floor((time.time() - tm) * 1000)))
                                if text == '哎呀，你这么说我也不懂，详细点呗' or text == '':
                                    util.log(1, '[!] 自然语言无语了！')
                                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                                    continue
                            except BaseException as e:
                                print(e)
                                util.log(1, '自然语言处理错误！')
                                wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                                continue
                        else:
                            text = answer
                        if len(user_name) == 0:
                            self.a_msg = text
                        else:
                            self.a_msg = user_name + '，' + text

                    elif index == 2:
                        self.a_msg = ['我们的直播间越来越多人咯', '感谢{}的到来'.format(user_name), '欢印{}来到我们的直播间'.format(user_name)][
                            random.randint(0, 2)]

                    elif index == 3:
                        msg = ""
                        for index in range(1, len(interact), 4):
                            try:
                                gift = interact[index + 2]
                                gift_name = '礼物'
                                if gift[0] != -1:
                                    gift_name = gift[1]
                                msg = msg + "{}送给我的{}个{}，".format(interact[index], interact[index + 3], gift_name)
                            except BaseException as e:
                                print("[System] 礼物处理错误！")
                                print(e)
                        self.a_msg = '感谢感谢，感谢' + msg

                    elif index == 4:
                        self.a_msg = '感谢关注'

                    self.last_speak_data = self.a_msg
                    self.speaking = True
                    MyThread(target=self.__say, args=['interact']).start()
                else:
                    i = 0
                    self.interactive.clear()
                    config_items = config_util.config["items"]
                    items = []
                    for item in config_items:
                        if item["enabled"]:
                            items.append(item)
                    if len(items) > 0:
                        if self.item_index >= len(items):
                            self.item_index = 0
                            script_index = 0
                        item = items[self.item_index]
                        script_index = script_index + 1
                        explain_key = self.__get_explain_from_index(script_index)
                        if explain_key is None:
                            self.item_index = self.item_index + 1
                            script_index = 0
                            if self.item_index >= len(items):
                                self.item_index = 0
                            explain_key = self.__get_explain_from_index(script_index)
                        explain = item["explain"][explain_key]
                        if len(explain) > 0:
                            self.a_msg = explain
                            self.last_speak_data = self.a_msg
                            self.speaking = True
                            MyThread(target=self.__say, args=['script']).start()
            except BaseException as e:
                print(e)

    def __get_item_list(self) -> list:
        items = []
        for item in config_util.config["items"]:
            if item["enabled"]:
                items.append(item)
        return items

    def __get_explain_from_index(self, index: int):
        if index == 0:
            return "character"
        if index == 1:
            return "discount"
        if index == 2:
            return "intro"
        if index == 3:
            return "price"
        if index == 4:
            return "promise"
        if index == 5:
            return "usage"
        return None

    def on_interact(self, interact):

        # 合并同类交互
        # 进入
        if interact[0] == 2:
            itr = self.__get_interactive(2)
            if itr is None:
                self.interactive.append(interact)
            else:
                newItr = (2, itr[1] + ', ' + interact[1], itr[2])
                self.interactive.remove(itr)
                self.interactive.append(newItr)

        # 送礼
        elif interact[0] == 3:
            itr = self.__get_interactive(3)
            if itr is None:
                self.interactive.append(interact)
            else:
                newItrList = []
                newItrList.extend(itr)
                newItrList.append(itr[2])
                newItrList.append(itr[3])
                newItrList.append(itr[4])
                self.interactive.remove(itr)
                self.interactive.append(tuple(newItrList))

        # 关注
        elif interact[0] == 4:
            if self.__get_interactive(2) is None:
                self.interactive.append(interact)

        else:
            self.interactive.append(interact)
        MyThread(target=self.__update_mood, args=[interact[0]]).start()
        MyThread(target=storer.storage_live_interact, args=[interact]).start()

    def __get_interactive(self, interactType):
        for interact in self.interactive:
            if interact[0] == interactType:
                return interact
        return None

    # 适应模型计算
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
            if not self.sleep:
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

    def __get_mood(self):
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

    # 合成声音，加上type代表是脚本还是互动
    def __say(self, styleType):
        try:
            if len(self.a_msg) < 1:
                self.speaking = False
            else:
                # print(self.__get_mood().name + self.a_msg)
                util.printInfo(1, '菲菲', '({}) {}'.format(self.__get_mood(), self.a_msg))
                MyThread(target=storer.storage_live_interact, args=[(0, '菲菲', self.a_msg)]).start()
                util.log(1, '合成音频...')
                tm = time.time()
                result = self.sp.to_sample(self.a_msg, self.__get_mood())
                util.log(1, '合成音频完成. 耗时: {} ms'.format(math.floor((time.time() - tm) * 1000)))
                if result is not None:
                    # playsound(result)
                    # with wave.open(result, 'rb') as wav_file:
                    #     wav_length = wav_file.getnframes() / float(wav_file.getframerate())
                    #     time.sleep(wav_length)
                    MyThread(target=self.__send_audio, args=[result, styleType]).start()
                    # MyThread(target=self.__play_audio, args=[result]).start()
                    # MyThread(target=self.__waiting_speaking, args=[result]).start()
                    return result
        except BaseException as e:
            print(e)
        # print("tts失败！！！！！！！！！！！！！")
        self.speaking = False
        return None

    def __play_sound(self, file_url):
        util.log(1, '播放音频...')
        util.log(1, '问答处理总时长：{} ms'.format(math.floor((time.time() - self.last_quest_time) * 1000)))
        pygame.mixer.music.load(file_url)
        pygame.mixer.music.play()

    def __send_audio(self, file_url, say_type):
        try:
            audio_length = eyed3.load(file_url).info.time_secs
            if audio_length <= config_util.config["interact"]["maxInteractTime"] or say_type == "script":
                if config_util.config["interact"]["playSound"]:
                    self.__play_sound(file_url)
                else:
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'audio', 'Value': os.path.abspath(file_url), 'Time': audio_length, 'Type': say_type}}
                    wsa_server.get_instance().add_cmd(content)
                wsa_server.get_web_instance().add_cmd({"panelMsg": self.a_msg})
                time.sleep(audio_length + 0.5)
                wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                if config_util.config["interact"]["playSound"]:
                    util.log(1, '结束播放！')
            self.speaking = False
        except Exception as e:
            print(e)

    # def __send_audio(self, file_url, say_type):
    #     try:
    #         # time.sleep(0.25)
    #         with wave.open(file_url, 'rb') as wav_file:
    #             wav_length = wav_file.getnframes() / float(wav_file.getframerate())
    #         print(wav_length)
    #         if wav_length <= config_util.config["interact"]["maxInteractTime"] or say_type == "script":
    #             if config_util.config["interact"]["playSound"]:
    #                 self.__play_sound(file_url)
    #             else:
    #                 content = {'Topic': 'Unreal', 'Data': {'Key': 'audio', 'Value': os.path.abspath(file_url), 'Time': wav_length, 'Type': say_type}}
    #                 wsa_server.get_instance().add_cmd(content)
    #             time.sleep(wav_length + 0.5)
    #         self.speaking = False
    #     except Exception as e:
    #         print(e)

    def __waiting_speaking(self, file_url):
        try:
            time.sleep(5)
            print('[' + str(int(time.time())) + '][菲菲] [S] [开始发言]')
            with wave.open(file_url, 'rb') as wav_file:
                wav_length = wav_file.getnframes() / float(wav_file.getframerate())
            time.sleep(wav_length)
            self.last_interact_time = time.time()
            self.speaking = False
            print('[' + str(int(time.time())) + '][菲菲] [E] [结束发言]')
            time.sleep(30)
            os.remove(file_url)
        except:
            self.last_interact_time = time.time()
            self.speaking = False

    # 冷场情绪更新
    def __update_mood_runnable(self):
        while self.__running:
            time.sleep(10)
            update = config_util.config["interact"]["perception"]["indifferent"] / 100
            if len(self.interactive) < 1:
                if self.mood > 0:
                    if self.mood > update:
                        self.mood = self.mood - update
                    else:
                        self.mood = 0
                elif self.mood < 0:
                    if self.mood < -update:
                        self.mood = self.mood + update
                    else:
                        self.mood = 0

    def set_sleep(self, sleep):
        self.sleep = sleep

    def start(self):
        MyThread(target=self.__send_mood).start()
        MyThread(target=self.__auto_speak).start()
        MyThread(target=self.__update_mood_runnable).start()

    def stop(self):
        self.__running = False
        self.sp.close()

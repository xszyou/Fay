import difflib
import math
import os
import random
import time
import wave
import socket

import eyed3
from openpyxl import load_workbook
import logging

# 适应模型使用
import numpy as np
# import tensorflow as tf
import fay_booter

from ai_module import baidu_emotion
from ai_module.ms_tts_sdk import Speech
from core import wsa_server, tts_voice, song_player
from core.interact import Interact
from core.tts_voice import EnumVoice
from scheduler.thread_manager import MyThread
from utils import util, storer, config_util
import pygame
from utils import config_util as cfg
from core import qa_service
from ai_module import nlp_cemotion

#nlp
from ai_module import nlp_gpt
from ai_module import nlp_lingju
from ai_module import nlp_rasa
from ai_module import nlp_ChatGLM2

import platform
if platform.system() == "Windows":
    import sys
    sys.path.append("test/ovr_lipsync")
    from test_olipsync import LipSyncGenerator

modules = {
    "nlp_gpt": nlp_gpt,
    "nlp_lingju": nlp_lingju,
    "nlp_rasa": nlp_rasa,
    "nlp_chatglm2": nlp_ChatGLM2,
}




def determine_nlp_strategy(msg,history):
    text = ''
    try:
        util.log(1, '自然语言处理...')
        tm = time.time()
        cfg.load_config()
       
        module_name = "nlp_" + cfg.key_chat_module
        selected_module = modules.get(module_name)
        if selected_module is None:
            raise RuntimeError('灵聚key、yuan key、gpt key都没有配置！')   
        text = selected_module.question(msg,history)    
        util.log(1, '自然语言处理完成. 耗时: {} ms'.format(math.floor((time.time() - tm) * 1000)))
        if text == '哎呀，你这么说我也不懂，详细点呗' or text == '':
            util.log(1, '[!] 自然语言无语了！')
            text = '哎呀，你这么说我也不懂，详细点呗'  
    except BaseException as e:
        print(e)
        util.log(1, '自然语言处理错误！')
        text = '哎呀，你这么说我也不懂，详细点呗'   

    return text
    
__fei_fei = None
def new_instance():
    global __fei_fei
    if __fei_fei is None:
        __fei_fei = FeiFei()
    return __fei_fei

class FeiFei:
    def __init__(self):
        pygame.mixer.init()
        self.q_msg = '你叫什么名字？'
        self.a_msg = 'hi,我叫菲菲，英文名是fay'
        self.mood = 0.0  # 情绪值
        self.old_mood = 0.0
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
        self.last_interact_time = time.time()
        self.last_speak_data = ''
        self.interactive = []
        self.sleep = False
        self.__running = True
        self.sp.connect()  # 预连接
        self.last_quest_time = time.time()
        self.playing = False
        self.muting = False
        self.set_img = ""
        self.chat_list = {}
        self.__play_end = True
        self.__send_time = time.time()
        self.__audio_time = 0
        self.__audio_queue = [] 
        self.cemotion = None

    def __get_answer(self, interleaver, text):

        if interleaver == "mic":
            # 命令
            keyword = qa_service.question('command',text)
            if keyword is not None:
                if keyword == "stop":
                    fay_booter.stop()
                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                    wsa_server.get_instance().add_cmd(content)
                    wsa_server.get_web_instance().add_cmd({"liveState": 0})
                elif keyword == "mute":
                    self.muting = True
                    self.speaking = True
                    self.a_msg = "好的"
                    MyThread(target=self.__say, args=['interact']).start()
                    time.sleep(0.5)
                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                    wsa_server.get_instance().add_cmd(content)
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
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                    wsa_server.get_instance().add_cmd(content)
                return "NO_ANSWER"

        #商品问答
        answer = None
        answer = qa_service.question('goods',text)
        if answer is not None:
            return answer
        
        # 全局问答
        answer = qa_service.question('qa',text)
        if answer is not None:
            return answer
        
        # 人设问答
        keyword = qa_service.question('Persona',text)
        if keyword is not None:
            return config_util.config["attribute"][keyword]

    def __auto_speak(self):
        i = 0
        script_index = 0
        while self.__running:
            time.sleep(0.8)
            if self.speaking or self.sleep:
                continue
            try:
                if i < 3 and self.interactive:
                    interactions_to_handle = self.interactive[-3:] if len(self.interactive) > 3 else self.interactive
                    for interact in interactions_to_handle:
                        i += 1
                        self.interactive.remove(interact)
                        user_name = interact.data.get("user", "")
                        interact_type = interact.interact_type
                        self.q_msg = interact.data.get("msg", "")
                        if interact_type == 1:
                            if not config_util.config["interact"]["playSound"]:
                                wsa_server.get_instance().add_cmd({'Topic': 'Unreal', 'Data': {'Key': 'question', 'Value': self.q_msg}})
                            answer = self.__get_answer(interact.interleaver, self.q_msg)
                            text = answer if answer and answer != 'NO_ANSWER' else determine_nlp_strategy(self.q_msg, self.chat_list[user_name]["history"])
                            self.a_msg = f"{user_name}，{text}" if user_name else text
                            self.chat_list[user_name]["history"].append({"role": "bot", "content": text})

                        elif interact_type == 2:
                            self.a_msg = random.choice([
                                f"哈喽，{user_name}！看到你的名字出现在我的直播间，我的心都快跳出来了！快来跟我互动吧！",
                                f"{user_name}说句话呗，这里好冷，呜呜呜",
                                f"咦！我看见{user_name}来了！终于等到你了！今天我们一起聊聊你感兴趣的话题吧！",
                                f"{user_name}客官里面请！",
                                f"欢迎{user_name}！雅座一位，请~",
                                f"哇塞！{user_name}！你的名字就像一缕阳光，照亮了我的直播间！快来跟我一起享受这美好的时刻吧！",
                                f"欢迎{user_name}！终于等到你了！今天我们一起聊聊你感兴趣的话题吧！",
                                f"哈喽，{user_name}！我觉得你很有气质，可以和你交个朋友吗？",
                                f"咦！亲爱的{user_name}！你终于记起大明湖畔的我了！",
                                f"{user_name}你来啦！你是小哥哥还是小姐姐啊！，你今天看起来好好看啊！快坐下来，让我好好看看你！",
                                f"嘿嘿，{user_name}，，好久不见！你最近过得怎么样？有没有想我啊？记得点关注，不然我可要捣蛋啦！",
                                f"哇哦，{user_name}，你是风儿我是沙，快来点关注，么么哒！",
                                f"嗨，{user_name}！盼星星盼月亮，终于把你盼来了！今天我们要聊点什么呢？",
                                f"哇！{user_name}你来啦！我的直播间里有你才完整！快点关注，不然我要撒娇啦！",
                                f"咦？是{user_name}大驾光临！快点关注，不然我就不让你走啦！",
                                f"哇哦，{user_name}你终于来了！记得多多互动，不然我要哭给你看啦！",
                                f"呀，{user_name}宝宝，欢迎你来玩！别忘了点关注哦，不然我就要闹脾气啦！",
                                f"{user_name}，你来啦！今天我们来聊点什么呢？有什么好玩的事情要和我分享吗？",
                                f"{user_name}来了啊，吃我一拳！",
                                f"哟，{user_name}，今天想聊点什么有趣的呢？",
                                f"嘿，{user_name}，快进来，我刚才还在想着你呢！",
                                f"嘿嘿，{user_name}，终于来了，准备好被我调戏了吗？",
                                f"哇，{user_name}，今天你就是我的超神BUFF！",
                                f"嘿，{user_name}，你来了！今天要不要一起搞个“内卷”局？",
                                f"嘿嘿，{user_name}，你来啦！准备好一起“社交牛逼症”了吗？",
                                f"哇哦，{user_name}，你来了！快来一起“打工人”吧！",
                                f"嗨，{user_name}，有你在，简直就是“安排得明明白白”！",
                                f"哇，{user_name}，你终于来了！我刚刚还和空气聊天呢！",
                                f"喵，{user_name}，准备好一起做可爱爆表的小可爱吗？",
                                f"嘻嘻，{user_name}，你终于来了！你就是我的‘锦鲤’本鲤啊！"
                            ])

                        elif interact_type == 3:
                            gift = interact.data["gift"]
                            self.a_msg = random.choice([
                                f'太感谢 {user_name}送我的{gift}！祝宝宝财运追着跑！运气乐逍遥！',
                                f'太感谢我的小可爱 {user_name}送我的{gift}！宝贝你真牛！真大气！',
                                f'哇！太感谢宝{user_name}送我的{gift}！不服天！不服地！就服宝宝的实力！',
                                f'太感谢{user_name}老板送我的{gift}！老板破费了！老板大气！',
                                f'太感谢我的好朋友{user_name}送我的{gift}！祝您福气满满！微笑甜甜！',
                                f'哇！太感谢{user_name}送我的{gift}！太感谢了！我的好朋友！祝您才华四溢！',
                                f'感谢{user_name}送我的{gift}！太感谢了！我的好朋友！我好开心！么么哒！',
                                f'哇！太感谢我的小可爱{user_name}送我的{gift}！祝您元气满满！开心快乐！',
                                '一口气感谢了那么多礼物！真的太开心了！谢谢宝宝们的礼物！',
                                f'哇，{user_name}送的{gift}真是让我惊喜连连！谢谢你！',
                                f'谢谢{user_name}的{gift}！你的支持是我前进的动力！',
                                f'哇，感谢{user_name}送的{gift}！愿你每天都充满快乐和惊喜！'
                                f'谢谢{user_name}的{gift}！你的慷慨让我感到非常感动！',
                                f'感谢亲爱的{user_name}送的{gift}，你是不是偷偷喜欢我呀？嘿嘿！',
                                f'哇，{user_name}送的{gift}让我激动到原地转圈圈！',
                                f'谢谢{user_name}送的{gift}，你这么宠我，我都要飘了！',
                                f'感谢{user_name}送的{gift}，你是不是要把我宠上天？',
                                f'谢谢{user_name}送的{gift}，你这么好，让我怎么办呢？嘿嘿！',
                                f'感谢{user_name}送的{gift}，你真是我的超级英雄！',
                                f'谢谢{user_name}送的{gift}，你真是太棒了！抱抱你！'
                            ])

                        elif interact_type == 4:
                            self.a_msg = random.choice([
                                f'太感谢我的{user_name}小可爱的关注！我好开心！么么哒！',
                                f'我的天啊！太感谢{user_name}宝贝的关注！宝贝宝贝6！6！6！我给你一路护航！',
                                f'太开心了！谢谢{user_name}宝宝的关注！祝宝宝天天开心！'
                            ])

                        elif interact_type == 5:
                            self.a_msg = random.choice([
                                '收到那么多礼物！我真的太开心了！谢谢宝宝们的礼物！不服天！不服地！就服宝宝们的实力',
                                '哇！收到这么多礼物！我好开心！谢谢宝宝们！',
                                '哇塞，太多礼物了！简直开心得让我飞起来了！谢谢观众姥爷们！'
                            ])

                        elif interact_type == 6:
                            self.a_msg = random.choice([
                                '感谢宝贝们的赞赞，比心比心！',
                                f'谢谢我的宝宝{user_name}的连续点赞了，谢谢你！',
                                f'太感谢宝宝{user_name}的赞赞啦！',
                                '看啊！一闪一闪小赞赞！漫天都是小赞赞！'
                            ])

                        elif interact_type == 7:
                            self.a_msg = random.choice([
                                '看见下面不要钱的辣条了吗？点一点！就是我的好朋友!',
                                '咦?多跟我聊聊天啊！一起来玩耍！',
                                '给个小礼物！我给你画个心喔！',
                                '我这么勤快！还不点点关注？',
                                '各位宝宝们！点点赞，给我加加油吧！',
                                '观众姥爷们!快关注起来！助力我进步一点点！',
                                '亲爱的观众朋友们，关注一下，支持我进步多多！',
                                '大家咋整？我今天状态爆表，不来点个关注撑撑场面吗？',
                                '宝宝们，看到下面的礼物吗？点一点，让我感受到你的爱！',
                                '有没有人来支持一下我啊，让她觉得自己不是一个人在打野!',
                                '点点关注，不仅支持我，还能第一时间看到最新直播内容哦！',
                                '宝宝们，点赞和关注对我来说真的很重要，感谢大家的支持！',
                                '各位亲爱的朋友们，给我送点小礼物吧，让我们一起嗨起来！',
                                '亲爱的观众朋友们，关注一下，支持我一下，不然我要闹小脾气啦！',
                                '有没有小可爱愿意送个小礼物？我会开心到飞起来哦！',
                                '嘿，看到没人点关注，我心里可是会嘀咕嘀咕的哦！',
                                '观众姥爷们，关注一下吧，支持我搞笑不停，不然我要耍赖啦！',
                                '各位宝宝们，送点小礼物，给我加加油，不然我要假哭啦！',
                                '宝宝们，看见不要钱的点赞按钮了吗？快点一下，我会给你一个大大的wink！',
                                '各位小可爱们，送送礼物，给我加加油，不然我要假装哭泣啦！'
                            ])

                        self.last_speak_data = self.a_msg
                        self.speaking = True
                        MyThread(target=self.__say, args=['interact']).start()
                        if len(interactions_to_handle) <= 1:
                            break
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
                            self.set_img = item['img']
                            self.last_speak_data = self.a_msg
                            self.speaking = True
                            self.last_quest_time = time.time()
                            MyThread(target=self.__say, args=['script']).start()
            except BaseException as e:
                print(e)
           

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

    def check_interact(self, content):

        if util.is_url_check(content):
            return False
        
        if util.profanity_content(content):
            return False

        if util.is_punctuation_string(content):
            return False
        
        #本地违禁词
        bad_word =  util.check_sensitive_words(config_util.config["interact"]["badwordsPath"], content)
        if bad_word is not None:
            if config_util.config["interact"]["badwordsDelType"] == "discard":
                return False
            else:
                content = content.replace(bad_word, "*")
                return self.check_interact(content)
        
        return content
        

    def replace_interact(self, content):
        content = content.replace('\n', ',')
        # 表情弹幕过滤
        content = util.replace_emoji(content)
        return content
 


    def on_interact(self, interact: Interact):

        if interact.interact_type == 1:
            content = self.check_interact(interact.data["msg"])
            if content is not False:
                content = self.replace_interact(interact.data["msg"])
                username = self.check_interact(interact.data["user"])
                if username is not False:
                    if self.chat_list.get(interact.data["user"]) is None:
                        self.chat_list[interact.data["user"]] = dict()
                        self.chat_list[interact.data["user"]]["history"] = []  
                    user_history = dict()
                    user_history["role"] = "user"
                    user_history["content"] = interact.data["msg"]            
                    self.chat_list[interact.data["user"]]["history"].append(user_history)
                    self.chat_list[interact.data["user"]]["last_time"] = time.time()
                    self.interactive.append(interact)
            
        # 合并同类交互
        # 进入
        elif interact.interact_type == 2:
            itr = self.__get_interactive(2)
            if itr is None:
                self.interactive.append(interact)
            else:
                newItr = itr.data["user"] + ', ' + interact.data["user"]
                self.interactive.remove(itr)
                self.interactive.append(Interact("live", 2,  {"user": newItr}))

        # 送礼
        elif interact.interact_type == 3:
            gifts = []
            rm_list = []
            for itr in self.interactive:
                
                if itr.interact_type == 3:
                    gifts.append({
                        "user": itr.data["user"],
                        "gift": itr.data["gift"],
                        "amount": itr.data["amount"]
                    })
                    rm_list.append(itr)
                elif itr.interact_type == 5:
                    for gift in itr.data["gifts"]:
                        gifts.append(gift)
                    rm_list.append(itr)
           
            if len(rm_list) > 2:
                for itr in rm_list:
                    self.interactive.remove(itr)
                self.interactive.append(Interact("live", 5,  {"user":'多人',"gifts": gifts}))
            else:
                self.interactive.append(interact)
        # 关注
        elif interact.interact_type == 4:
            if self.__get_interactive(4) is None:
                self.interactive.append(interact)

        else:
            self.interactive.append(interact)
        MyThread(target=self.__update_mood, args=[interact.interact_type]).start()
        MyThread(target=storer.storage_live_interact, args=[interact]).start()

    def __get_interactive(self, interactType) -> Interact:
        for interact in self.interactive:
            if interact is Interact and interact.interact_type == interactType:
                return interact
        return None

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
                if  self.old_mood != self.mood:
                    wsa_server.get_instance().add_cmd(content)
                    self.old_mood = self.mood
           

    # 更新情绪
    def __update_mood(self, typeIndex):
        perception = config_util.config["interact"]["perception"]
        if typeIndex == 1:
            try:
                if cfg.ltp_mode == "cemotion":
                    result = nlp_cemotion.get_sentiment(self.cemotion,self.q_msg)
                    chat_perception = perception["chat"]
                    if result >= 0.5 and result <= 1:
                       self.mood = self.mood + (chat_perception / 200.0)
                    elif result <= 0.2:
                       self.mood = self.mood - (chat_perception / 100.0)
                else:
                    if str(cfg.baidu_emotion_api_key) == '' or str(cfg.baidu_emotion_app_id) == '' or str(cfg.baidu_emotion_secret_key) == '':
                        self.mood = 0
                    else:
                        result = int(baidu_emotion.get_sentiment(self.q_msg))
                        chat_perception = perception["chat"]
                        if result >= 2:
                            self.mood = self.mood + (chat_perception / 200.0)
                        elif result == 0:
                            self.mood = self.mood - (chat_perception / 100.0)
            except BaseException as e:
                print("[System] 情绪更新错误！")
                print(e)
                self.mood = 0

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
                util.printInfo(1, '菲菲', '({}) {}'.format(self.__get_mood(), self.a_msg))
                MyThread(target=storer.storage_live_interact, args=[Interact('Fay', 0, {'user': 'Fay', 'msg': self.a_msg})]).start()
                util.log(1, '合成音频...')
                tm = time.time()
                result = self.sp.to_sample(self.a_msg, self.__get_mood())
                util.log(1, '合成音频完成. 耗时: {} ms 文件:{}'.format(math.floor((time.time() - tm) * 1000), result))
                
                if result is not None:            
                    MyThread(target=self.__send_audio, args=[result, styleType]).start()
                    return result
        except BaseException as e:
            print(e)
           
        # print("tts失败！！！！！！！！！！！！！")
        return None

    def __play_sound(self, file_url):
        util.log(1, '播放音频...')
        util.log(1, '问答处理总时长：{} ms'.format(math.floor((time.time() - self.last_quest_time) * 1000)))
        pygame.mixer.music.load(file_url)
        pygame.mixer.music.play()

    def __send_audio(self, file_url, say_type):
        try:
            if self.__running:  
                if config_util.config["interact"]["playSound"]: # 展板播放
                    self.__play_sound(file_url)
                else:#发送音频给ue和socket
                     #推送ue
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'audio', 'Value': os.path.abspath(file_url), 'Text': self.a_msg,  'Type': say_type}}
                    #计算lips
                    if platform.system() == "Windows":
                        try:
                            lip_sync_generator = LipSyncGenerator()
                            viseme_list = lip_sync_generator.generate_visemes(os.path.abspath(file_url))
                            consolidated_visemes = lip_sync_generator.consolidate_visemes(viseme_list)
                            content["Data"]["Lips"] = consolidated_visemes
                        except Exception as e:
                            print(e)
                            util.log(1, "唇型数字生成失败，无法使用新版ue5工程") 
                        total_time = 0
                        for phoneme in content["Data"]["Lips"]:
                            total_time += phoneme["Time"]
                        content["Data"]["Time"] = total_time/1000
                        audio_length = content["Data"]["Time"] 
                    else:
                        try:
                            logging.getLogger('eyed3').setLevel(logging.ERROR)
                            audio_length = eyed3.load(file_url).info.time_secs #mp3音频长度
                        except Exception as e:
                            audio_length = 3
                    if self.set_img != "":
                         content["Data"]["Image"] = self.set_img 
                         self.set_img = ""   
                    self.__audio_queue.append(content)
                    # wsa_server.get_instance().add_cmd(content)

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

                
                
                    
                wsa_server.get_web_instance().add_cmd({"panelMsg": self.a_msg})
                if not cfg.config["interact"]["playSound"]:
                    if audio_length < 8:
                        time.sleep(2.1)
                    else:
                        time.sleep(audio_length-5)

                    self.speaking = False
                    
                if  cfg.config["interact"]["playSound"]:
                    try:
                        logging.getLogger('eyed3').setLevel(logging.ERROR)
                        audio_length = eyed3.load(file_url).info.time_secs #mp3音频长度
                    except Exception as e:
                        audio_length = 3
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
                    wsa_server.get_web_instance().add_cmd({"remote_audio_connect": False})
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
                wsa_server.get_web_instance().add_cmd({"remote_audio_connect": True})
                while self.deviceConnect: #只允许一个设备连接
                    time.sleep(1)
        except Exception as err:
            pass

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

    def __add_invite(self):
        while self.__running:
            time.sleep(600)
            self.interactive.append(Interact("live", 7,{"user":'主播'}))

    def __send_to_audio(self):
        while self.__running:
            time.sleep(0.5)
            if (time.time() - self.__send_time >= 1 + self.__audio_time) and not self.__play_end:
                    self.set_play_end(True)
            if self.__audio_queue and self.__play_end:
                self.set_play_end(False)
                message = self.__audio_queue.pop(0)
                #文字
                content = {'Topic': 'Unreal', 'Data': {'Key': 'text', 'Value': message["Data"]["Text"]}}
                wsa_server.get_instance().add_cmd(content)
                #音频
                wsa_server.get_instance().add_cmd(message)
                #日志
                message_to_send = message["Data"]["Text"][:20] + '...' if len(message["Data"]["Text"]) > 20 else message["Data"]["Text"]
                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': message_to_send}}
                wsa_server.get_instance().add_cmd(content)
                self.__send_time = time.time()
                self.__audio_time = message["Data"]["Time"]
                time.sleep(self.__audio_time)

    def set_play_end(self,play_end):
        self.__play_end = play_end
        if play_end:
            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
            wsa_server.get_instance().add_cmd(content)
            # if config_util.config["interact"]["playSound"]:
            #     util.log(1, '结束播放！')

    def set_audio_queue(self,queue):
        self.__audio_queue = queue

    def start(self):
        self.__audio_queue = []
        self.__play_end = True
        self.__running = True
        if cfg.ltp_mode == "cemotion":
            from cemotion import Cemotion
            self.cemotion = Cemotion()
        MyThread(target=self.__send_mood).start()
        MyThread(target=self.__auto_speak).start()
        MyThread(target=self.__update_mood_runnable).start()
        MyThread(target=self.__add_invite).start()
        MyThread(target=self.__send_to_audio).start()
    
    def stop(self):
        self.__running = False
        song_player.stop()
        self.speaking = False
        self.playing = False
        self.sp.close()
        self.interactive.clear()
        wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
        content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
        wsa_server.get_instance().add_cmd(content)
        wsa_server.get_instance().clear()
        if self.deviceConnect is not None:
            self.deviceConnect.close()
            self.deviceConnect = None
        if self.deviceSocket is not None:
            self.deviceSocket.close()


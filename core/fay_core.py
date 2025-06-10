#作用是处理交互逻辑，文字输入，语音、文字及情绪的发送、播放及展示输出
import math
from operator import index
import os
import time
import socket
import requests
from pydub import AudioSegment
from queue import Queue
import re  # 添加正则表达式模块用于过滤表情符号

# 适应模型使用
import numpy as np
from ai_module import baidu_emotion
from core import wsa_server
from core.interact import Interact
from tts.tts_voice import EnumVoice
from scheduler.thread_manager import MyThread
from tts import tts_voice
from utils import util, config_util
from core import qa_service
from utils import config_util as cfg
from core import content_db
from ai_module import nlp_cemotion
from llm import nlp_cognitive_stream
from core import stream_manager

from core import member_db
import threading

#加载配置
cfg.load_config()
if cfg.tts_module =='ali':
    from tts.ali_tss import Speech
elif cfg.tts_module == 'gptsovits':
    from tts.gptsovits import Speech
elif cfg.tts_module == 'gptsovits_v3':
    from tts.gptsovits_v3 import Speech    
elif cfg.tts_module == 'volcano':
    from tts.volcano_tts import Speech
else:
    from tts.ms_tts_sdk import Speech

#windows运行推送唇形数据
import platform
if platform.system() == "Windows":
    import sys
    sys.path.append("test/ovr_lipsync")
    from test_olipsync import LipSyncGenerator
    

#可以使用自动播报的标记    
can_auto_play = True
auto_play_lock = threading.RLock()

class FeiFei:
    def __init__(self):
        self.lock = threading.Lock()
        self.nlp_streams = {} # 存储用户ID到句子缓存的映射
        self.nlp_stream_lock = threading.Lock() # 保护nlp_streams字典的锁
        self.mood = 0.0  # 情绪值
        self.old_mood = 0.0
        self.item_index = 0
        self.X = np.array([1, 0, 0, 0, 0, 0, 0, 0]).reshape(1, -1)  # 适应模型变量矩阵
        # self.W = np.array([0.01577594,1.16119452,0.75828,0.207746,1.25017864,0.1044121,0.4294899,0.2770932]).reshape(-1,1) #适应模型变量矩阵
        self.W = np.array([0.0, 0.6, 0.1, 0.7, 0.3, 0.0, 0.0, 0.0]).reshape(-1, 1)  # 适应模型变量矩阵

        self.wsParam = None
        self.wss = None
        self.sp = Speech()
        self.speaking = False #声音是否在播放
        self.__running = True
        self.sp.connect()  #TODO 预连接
        self.cemotion = None
        self.timer = None
        self.sound_query = Queue()
        self.think_mode_users = {}  # 使用字典存储每个用户的think模式状态
    
    def __remove_emojis(self, text):
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # 表情符号
            "\U0001F300-\U0001F5FF"  # 图标符号
            "\U0001F680-\U0001F6FF"  # 交通工具和符号
            "\U0001F1E0-\U0001F1FF"  # 国旗
            "\U00002700-\U000027BF"  # 杂项符号
            "\U0001F900-\U0001F9FF"  # 补充表情符号
            "\U00002600-\U000026FF"  # 杂项符号
            "\U0001FA70-\U0001FAFF"  # 更多表情
            "]+",
            flags=re.UNICODE,
        )
        return emoji_pattern.sub(r'', text)

    #语音消息处理检查是否命中q&a
    def __get_answer(self, interleaver, text):
        answer = None
        # 全局问答
        answer, type = qa_service.QAService().question('qa',text)
        if answer is not None:
            return answer, type
        else:
            return None, None
        
       
    #语音消息处理
    def __process_interact(self, interact: Interact):
        if self.__running:
            try:
                index = interact.interact_type
                username = interact.data.get("user", "User")
                uid = member_db.new_instance().find_user(username)
                if index == 1: #语音文字交互
                    #记录用户问题,方便obs等调用
                    self.write_to_file("./logs", "asr_result.txt",  interact.data["msg"])

                    #同步用户问题到数字人
                    if wsa_server.get_instance().is_connected(username): 
                        content = {'Topic': 'human', 'Data': {'Key': 'question', 'Value': interact.data["msg"]}, 'Username' : interact.data.get("user")}
                        wsa_server.get_instance().add_cmd(content)

                    #记录用户问题
                    content_id = content_db.new_instance().add_content('member','speak',interact.data["msg"], username, uid)
                    if wsa_server.get_web_instance().is_connected(username):
                        wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"member","content":interact.data["msg"], "username":username, "uid":uid, "id":content_id}, "Username" : username})
                    
                    #确定是否命中q&a
                    answer, type = self.__get_answer(interact.interleaver, interact.data["msg"])
                    
                    #大语言模型回复    
                    text = ''
                    if answer is None or type != "qa":
                        if wsa_server.get_web_instance().is_connected(username):
                            wsa_server.get_web_instance().add_cmd({"panelMsg": "思考中...", "Username" : username, 'robot': f'{cfg.fay_url}/robot/Thinking.jpg'})
                        if wsa_server.get_instance().is_connected(username):
                            content = {'Topic': 'human', 'Data': {'Key': 'log', 'Value': "思考中..."}, 'Username' : username, 'robot': f'{cfg.fay_url}/robot/Thinking.jpg'}
                            wsa_server.get_instance().add_cmd(content)
                        text = nlp_cognitive_stream.question(interact.data["msg"], username, interact.data.get("observation", None))

                    else: 
                        text = answer
                        stream_manager.new_instance().write_sentence(username, "_<isfirst>" + text + "_<isend>")
                           
                    #完整文本记录回复并输出到各个终端
                    self.__process_text_output(text, username, uid  )

                    return text      
                
                elif (index == 2):#透传模式，用于适配自动播报控制及agent的通知工具

                    if interact.data.get("text"):
                        text = interact.data.get("text")
                        # 使用统一的文本处理方法，空列表表示没有额外回复
                        self.__process_text_output(text, username, uid)
                        MyThread(target=self.say, args=[interact, text]).start()  
                    return 'success'
   
            except BaseException as e:
                print(e)
                return e
        else:
            return "还没有开始运行"

    #记录问答到log
    def write_to_file(self, path, filename, content):
        if not os.path.exists(path):
            os.makedirs(path)
        full_path = os.path.join(path, filename)
        with open(full_path, 'w', encoding='utf-8') as file:
            file.write(content)
            file.flush()  
            os.fsync(file.fileno()) 

    #触发语音交互
    def on_interact(self, interact: Interact):
        MyThread(target=self.__update_mood, args=[interact]).start()
        #创建用户
        username = interact.data.get("user", "User")
        if member_db.new_instance().is_username_exist(username)  == "notexists":
            member_db.new_instance().add_user(username)
        MyThread(target=self.__process_interact, args=[interact]).start()
        return None

    # 发送情绪
    def __send_mood(self):
         while self.__running:
            time.sleep(3)
            if wsa_server.get_instance().is_connected("User"):
                if  self.old_mood != self.mood:
                    content = {'Topic': 'human', 'Data': {'Key': 'mood', 'Value': self.mood}}
                    wsa_server.get_instance().add_cmd(content)
                    self.old_mood = self.mood

    #TODO 考虑重构这个逻辑  
    # 更新情绪
    def __update_mood(self, interact):
        perception = config_util.config["interact"]["perception"]
        if interact.interact_type == 1:
            try:
                if cfg.ltp_mode == "cemotion":
                    result = nlp_cemotion.get_sentiment(self.cemotion, interact.data["msg"])
                    chat_perception = perception["chat"]
                    if result >= 0.5 and result <= 1:
                       self.mood = self.mood + (chat_perception / 150.0)
                    elif result <= 0.2:
                       self.mood = self.mood - (chat_perception / 100.0)
                else:
                    if str(cfg.baidu_emotion_api_key) == '' or str(cfg.baidu_emotion_app_id) == '' or str(cfg.baidu_emotion_secret_key) == '':
                        self.mood = 0
                    else:
                        result = int(baidu_emotion.get_sentiment(interact.data["msg"]))
                        chat_perception = perception["chat"]
                        if result >= 2:
                            self.mood = self.mood + (chat_perception / 150.0)
                        elif result == 0:
                            self.mood = self.mood - (chat_perception / 100.0)
            except BaseException as e:
                self.mood = 0
                print("[System] 情绪更新错误！")
                print(e)

        elif interact.interact_type == 2:
            self.mood = self.mood + (perception["join"] / 100.0)

        elif interact.interact_type == 3:
            self.mood = self.mood + (perception["gift"] / 100.0)

        elif interact.interact_type == 4:
            self.mood = self.mood + (perception["follow"] / 100.0)

        if self.mood >= 1:
            self.mood = 1
        if self.mood <= -1:
            self.mood = -1

    #获取不同情绪声音
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
    def say(self, interact, text, type = ""): #TODO 对is_end及is_first的处理有问题
        try:
            uid = member_db.new_instance().find_user(interact.data.get('user'))
            is_end = interact.data.get("isend", False)
            is_first = interact.data.get("isfirst", False)

            if is_first and (text is None or text.strip() == ""):
                return None
                
            self.__send_panel_message(text, interact.data.get('user'), uid, 0, type)
            
            # 处理think标签
            is_start_think = False
            
            # 第一步：处理结束标记</think>
            if "</think>" in text:
                # 设置用户退出思考模式
                self.think_mode_users[uid] = False
                
                # 分割文本，提取</think>后面的内容
                # 如果有多个</think>，我们只关心最后一个后面的内容
                parts = text.split("</think>")
                text = parts[-1].strip()
                
                # 如果提取出的文本为空，则不需要继续处理
                if text == "":
                    return None
            
            # 第二步：处理开始标记<think>
            # 注意：这里要检查经过上面处理后的text
            if "<think>" in text:
                is_start_think = True
                self.think_mode_users[uid] = True
                text = "请稍等..."
            
            # 如果既没有结束标记也没有开始标记，但用户当前处于思考模式
            # 这种情况是流式输出中间部分，应该被忽略
            elif "</think>" not in text and "<think>" not in text and self.think_mode_users.get(uid, False):
                return None
                
            if self.think_mode_users.get(uid, False) and is_start_think:
                if wsa_server.get_web_instance().is_connected(interact.data.get('user')):
                    wsa_server.get_web_instance().add_cmd({"panelMsg": "思考中...", "Username" : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Thinking.jpg'})
                if wsa_server.get_instance().is_connected(interact.data.get("user")):
                    content = {'Topic': 'human', 'Data': {'Key': 'log', 'Value': "思考中..."}, 'Username' : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Thinking.jpg'}
                    wsa_server.get_instance().add_cmd(content)

            # 如果用户在think模式中,不进行语音合成
            if self.think_mode_users.get(uid, False) and not is_start_think:
                return None
            
            result = None
            audio_url = interact.data.get('audio')#透传的音频
            if audio_url is not None:#透传音频下载
                file_name = 'sample-' + str(int(time.time() * 1000)) + audio_url[-4:]
                result = self.download_wav(audio_url, './samples/', file_name)
            elif config_util.config["interact"]["playSound"] or wsa_server.get_instance().is_connected(interact.data.get("user")) or self.__is_send_remote_device_audio(interact):#tts
                if text != None and text.replace("*", "").strip() != "":
                    # 先过滤表情符号，然后再合成语音
                    filtered_text = self.__remove_emojis(text.replace("*", ""))
                    if filtered_text is not None and filtered_text.strip() != "":
                        util.printInfo(1,  interact.data.get('user'), '合成音频...')
                        tm = time.time()
                        result = self.sp.to_sample(filtered_text, self.__get_mood_voice())
                        util.printInfo(1,  interact.data.get("user"), "合成音频完成. 耗时: {} ms 文件:{}".format(math.floor((time.time() - tm) * 1000), result))
            else:
                if is_end and wsa_server.get_web_instance().is_connected(interact.data.get('user')):
                    wsa_server.get_web_instance().add_cmd({"panelMsg": "", 'Username' : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Normal.jpg'})

            if result is not None or is_first or is_end:
                if is_end:#如果结束标记，则延迟1秒处理,免得is end比前面的音频tts要快
                    time.sleep(1)          
                MyThread(target=self.__process_output_audio, args=[result, interact, text]).start()
                return result         
                
        except BaseException as e:
            print(e)
        return None
    
    #下载wav
    def download_wav(self, url, save_directory, filename):
        try:
            # 发送HTTP GET请求以获取WAV文件内容
            response = requests.get(url, stream=True)
            response.raise_for_status()  # 检查请求是否成功

            # 确保保存目录存在
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)

            # 构建保存文件的路径
            save_path = os.path.join(save_directory, filename)

            # 将WAV文件内容保存到指定文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)

            return save_path
        except requests.exceptions.RequestException as e:
            print(f"[Error] Failed to download file: {e}")
            return None


    #面板播放声音
    def __play_sound(self):
        try:
            import pygame
            pygame.mixer.init()  # 初始化pygame.mixer，只需要在此处初始化一次, 如果初始化失败，则不播放音频
        except Exception as e:
            util.printInfo(1, "System", "音频播放初始化失败,本机无法播放音频")
            return
        
        while self.__running:
            time.sleep(0.01)
            if not self.sound_query.empty():  # 如果队列不为空则播放音频
                file_url, audio_length, interact = self.sound_query.get()
                is_first = False
                is_end = False
                if interact.data.get('isfirst'):
                    is_first = True
                if interact.data.get('isend'):
                    is_end = True
                if file_url is not None:
                    util.printInfo(1, interact.data.get('user'), '播放音频...')
                    self.speaking = True

                #自动播报关闭
                global auto_play_lock
                global can_auto_play
                with auto_play_lock:
                    if self.timer is not None:
                        self.timer.cancel()
                        self.timer = None
                    can_auto_play = False

                if wsa_server.get_web_instance().is_connected(interact.data.get('user')):
                    wsa_server.get_web_instance().add_cmd({"panelMsg": "播放中 ...", "Username" : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Speaking.jpg'})
                
                if file_url is not None:
                    pygame.mixer.music.load(file_url)
                    pygame.mixer.music.play()

                    # 播放过程中计时，直到音频播放完毕
                    length = 0
                    while length < audio_length:
                        length += 0.01
                        time.sleep(0.01)
                
                if is_end:
                    self.play_end(interact)
                    util.printInfo(1, interact.data.get('user'), '结束播放！')
                if wsa_server.get_web_instance().is_connected(interact.data.get('user')):
                    wsa_server.get_web_instance().add_cmd({"panelMsg": "", "Username" : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Normal.jpg'})
                # 播放完毕后通知
                if wsa_server.get_web_instance().is_connected(interact.data.get("user")):
                    wsa_server.get_web_instance().add_cmd({"panelMsg": "", 'Username': interact.data.get('user')})
    
    #推送远程音频
    def __send_remote_device_audio(self, file_url, interact):
        if file_url is None:
            return
        delkey = None    
        for key, value in fay_booter.DeviceInputListenerDict.items():
            if value.username == interact.data.get("user") and value.isOutput: #按username选择推送，booter.devicelistenerdice按用户名记录
                try:
                    value.deviceConnector.send(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08") # 发送音频开始标志，同时也检查设备是否在线
                    wavfile = open(os.path.abspath(file_url), "rb")
                    data = wavfile.read(102400)
                    total = 0
                    while data:
                        total += len(data)
                        value.deviceConnector.send(data)
                        data = wavfile.read(102400)
                        time.sleep(0.0001)
                    value.deviceConnector.send(b'\x08\x07\x06\x05\x04\x03\x02\x01\x00')# 发送音频结束标志
                    util.printInfo(1, value.username, "远程音频发送完成：{}".format(total))
                except socket.error as serr:
                    util.printInfo(1, value.username, "远程音频输入输出设备已经断开：{}".format(key)) 
                    value.stop()
                    delkey = key
        if delkey:
             value =  fay_booter.DeviceInputListenerDict.pop(delkey)
             if wsa_server.get_web_instance().is_connected(interact.data.get('user')):
                wsa_server.get_web_instance().add_cmd({"remote_audio_connect": False, "Username" : interact.data.get('user')})

    def __is_send_remote_device_audio(self, interact):
        for key, value in fay_booter.DeviceInputListenerDict.items():
            if value.username == interact.data.get("user") and value.isOutput:
                return True
        return False 

    #输出音频处理
    def __process_output_audio(self, file_url, interact, text):
        try:
            try:
                if file_url is None:
                    audio_length = 0
                elif file_url.endswith('.wav'):
                    audio = AudioSegment.from_wav(file_url)
                    audio_length = len(audio) / 1000.0  # 时长以秒为单位
                elif file_url.endswith('.mp3'):
                    audio = AudioSegment.from_mp3(file_url)
                    audio_length = len(audio) / 1000.0  # 时长以秒为单位
            except Exception as e:
                audio_length = 3

            #推送远程音频
            if file_url is not None:
                MyThread(target=self.__send_remote_device_audio, args=[file_url, interact]).start()       

            #发送音频给数字人接口
            if file_url is not None and wsa_server.get_instance().is_connected(interact.data.get("user")):
                content = {'Topic': 'human', 'Data': {'Key': 'audio', 'Value': os.path.abspath(file_url), 'HttpValue': f'{cfg.fay_url}/audio/' + os.path.basename(file_url),  'Text': text, 'Time': audio_length, 'Type': interact.interleaver}, 'Username' : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Speaking.jpg'}
                #计算lips
                if platform.system() == "Windows":
                    try:
                        lip_sync_generator = LipSyncGenerator()
                        viseme_list = lip_sync_generator.generate_visemes(os.path.abspath(file_url))
                        consolidated_visemes = lip_sync_generator.consolidate_visemes(viseme_list)
                        content["Data"]["Lips"] = consolidated_visemes
                    except Exception as e:
                        print(e)
                        util.printInfo(1, interact.data.get("user"),  "唇型数据生成失败")
                wsa_server.get_instance().add_cmd(content)
                util.printInfo(1, interact.data.get("user"),  "数字人接口发送音频数据成功")

            #面板播放
            config_util.load_config()
            if config_util.config["interact"]["playSound"]:
                  self.sound_query.put((file_url, audio_length, interact))
            else:
                if wsa_server.get_web_instance().is_connected(interact.data.get('user')):
                    wsa_server.get_web_instance().add_cmd({"panelMsg": "", 'Username' : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Normal.jpg'})
            
        except Exception as e:
            print(e)

    def play_end(self, interact):
        self.speaking = False
        global can_auto_play
        global auto_play_lock
        with auto_play_lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            if interact.interleaver != 'auto_play': #交互后暂停自动播报30秒
                self.timer = threading.Timer(30, self.set_auto_play)
                self.timer.start()
            else:
                can_auto_play = True

    #恢复自动播报(如果有)   
    def set_auto_play(self):
        global auto_play_lock
        global can_auto_play
        with auto_play_lock:
            can_auto_play = True
            self.timer = None

    #启动核心服务
    def start(self):
        if cfg.ltp_mode == "cemotion":
            from cemotion import Cemotion
            self.cemotion = Cemotion()
        MyThread(target=self.__send_mood).start()
        MyThread(target=self.__play_sound).start()

    #停止核心服务
    def stop(self):
        self.__running = False
        self.speaking = False
        self.sp.close()
        wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
        content = {'Topic': 'human', 'Data': {'Key': 'log', 'Value': ""}}
        wsa_server.get_instance().add_cmd(content)

    def __record_response(self, text, username, uid):
        """
        记录AI的回复内容
        :param text: 回复文本
        :param username: 用户名
        :param uid: 用户ID
        :return: content_id
        """
        self.write_to_file("./logs", "answer_result.txt", text)
        return content_db.new_instance().add_content('fay', 'speak', text, username, uid)

    def __send_panel_message(self, text, username, uid, content_id=None, type=None):
        """
        发送消息到Web面板
        :param text: 消息文本
        :param username: 用户名
        :param uid: 用户ID
        :param content_id: 内容ID
        :param type: 消息类型
        """
        if not wsa_server.get_web_instance().is_connected(username):
            return
            
        # 发送基本消息
        wsa_server.get_web_instance().add_cmd({
            "panelMsg": text,
            "Username": username
        })
        
        # 如果有content_id，发送回复消息
        if content_id is not None:
            wsa_server.get_web_instance().add_cmd({
                "panelReply": {
                    "type": "fay",
                    "content": text,
                    "username": username,
                    "uid": uid,
                    "id": content_id,
                    "is_adopted": type == 'qa'
                },
                "Username": username
            })

    def __send_digital_human_message(self, text, username):
        """
        发送消息到数字人（语音应该在say方法驱动数字人输出）
        :param text: 消息文本
        :param username: 用户名
        """
        if wsa_server.get_instance().is_connected(username):
            content = {
                'Topic': 'human',
                'Data': {
                    'Key': 'text',
                    'Value': text
                },
                'Username': username
            }
            wsa_server.get_instance().add_cmd(content)

    def __process_text_output(self, text, username, uid):
        """
        处理文本输出到各个终端
        :param text: 主要回复文本
        :param textlist: 额外回复列表
        :param username: 用户名
        :param uid: 用户ID
        :param type: 消息类型
        """
        if text:
            text = text.strip()
            
        # 记录主回复
        content_id = self.__record_response(text, username, uid)
        
        # 发送主回复到面板和数字人
        # self.__send_panel_message(text, username, uid, content_id, type)
        self.__send_digital_human_message(text, username)
        
        # 打印日志
        util.printInfo(1, username, '({}) {}'.format(self.__get_mood_voice(), text))

import importlib
fay_booter = importlib.import_module('fay_booter')

#作用是处理交互逻辑，文字输入，语音、文字及情绪的发送、播放及展示输出
import math
import os
import time
import socket
import wave
import pygame
import requests
from pydub import AudioSegment
from queue import Queue

# 适应模型使用
import numpy as np
import fay_booter
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
from llm import nlp_rasa
from llm import nlp_gpt
from llm import nlp_lingju
from llm import nlp_xingchen
from llm import nlp_ollama_api
from llm import nlp_coze
from llm.agent import fay_agent
from llm import nlp_qingliu
from llm import nlp_return
from llm import nlp_gpt_stream
from core import stream_manager

from core import member_db
import threading
import functools

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
    
modules = {
    "nlp_gpt": nlp_gpt,
    "nlp_rasa": nlp_rasa,
    "nlp_lingju": nlp_lingju,
    "nlp_xingchen": nlp_xingchen,
    "nlp_ollama_api": nlp_ollama_api,
    "nlp_coze": nlp_coze,
    "nlp_agent": fay_agent,
    "nlp_qingliu": nlp_qingliu,
    "nlp_return": nlp_return,
    "nlp_gpt_stream": nlp_gpt_stream

}

#大语言模型回复
def handle_chat_message(msg, username='User', observation='', cache=None):
    text = ''
    textlist = []
    try:
        util.printInfo(1, username, '自然语言处理...')
        tm = time.time()
        cfg.load_config()
        module_name = "nlp_" + cfg.key_chat_module
        selected_module = modules.get(module_name)
        if selected_module is None:
            raise RuntimeError('请选择正确的nlp模型')   
        if cfg.key_chat_module == 'rasa':
            textlist = selected_module.question(msg)
            text = textlist[0]['text'] 
        elif cfg.key_chat_module == 'gpt_stream' and cache is not None:
            uid = member_db.new_instance().find_user(username)
            text = selected_module.question(msg, uid, observation, cache)  
        else:
            uid = member_db.new_instance().find_user(username)
            text = selected_module.question(msg, uid, observation)  
        util.printInfo(1, username, '自然语言处理完成. 耗时: {} ms'.format(math.floor((time.time() - tm) * 1000)))
        if text == '哎呀，你这么说我也不懂，详细点呗' or text == '':
            util.printInfo(1, username, '[!] 自然语言无语了！')
            text = '哎呀，你这么说我也不懂，详细点呗'  
    except BaseException as e:
        print(e)
        util.printInfo(1, username, '自然语言处理错误！')
        text = '哎呀，你这么说我也不懂，详细点呗'   

    return text,textlist

#可以使用自动播放的标记    
can_auto_play = True
auto_play_lock = threading.Lock()

class FeiFei:
    def __init__(self):
        self.lock = threading.Lock()
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
                if index == 1: #语音文字交互
                    #记录用户问题,方便obs等调用
                    self.write_to_file("./logs", "asr_result.txt",  interact.data["msg"])

                    #同步用户问题到数字人
                    if wsa_server.get_instance().is_connected(interact.data.get("user")): 
                        content = {'Topic': 'Unreal', 'Data': {'Key': 'question', 'Value': interact.data["msg"]}, 'Username' : interact.data.get("user")}
                        wsa_server.get_instance().add_cmd(content)

                    #记录用户
                    username = interact.data.get("user", "User")
                    if member_db.new_instance().is_username_exist(username)  == "notexists":
                        member_db.new_instance().add_user(username)
                    uid = member_db.new_instance().find_user(username)

                    #记录用户问题
                    content_id = content_db.new_instance().add_content('member','speak',interact.data["msg"], username, uid)
                    if wsa_server.get_web_instance().is_connected(username):
                        wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"member","content":interact.data["msg"], "username":username, "uid":uid, "id":content_id}, "Username" : username})
                    
                    #确定是否命中q&a
                    answer, type = self.__get_answer(interact.interleaver, interact.data["msg"])
                    
                    #大语言模型回复    
                    text = ''
                    textlist = []
                    if answer is None:
                        if wsa_server.get_web_instance().is_connected(username):
                            wsa_server.get_web_instance().add_cmd({"panelMsg": "思考中...", "Username" : username, 'robot': f'http://{cfg.fay_url}:5000/robot/Thinking.jpg'})
                        if wsa_server.get_instance().is_connected(username):
                            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': "思考中..."}, 'Username' : username, 'robot': f'http://{cfg.fay_url}:5000/robot/Thinking.jpg'}
                            wsa_server.get_instance().add_cmd(content)
                        text,textlist = handle_chat_message(interact.data["msg"], username, interact.data.get("observation", ""))

                    else: 
                        text = answer
                           
                    #记录回复    
                    self.write_to_file("./logs", "answer_result.txt", text)
                    content_id = content_db.new_instance().add_content('fay','speak',text, username, uid)

                    #文字输出：面板、聊天窗、log、数字人
                    if wsa_server.get_web_instance().is_connected(username):
                        wsa_server.get_web_instance().add_cmd({"panelMsg": text, "Username" : username, 'robot': f'http://{cfg.fay_url}:5000/robot/Speaking.jpg'})
                        if type == 'qa':
                            wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"fay","content":text, "username":username, "uid":uid, "id":content_id, "is_adopted":True}, "Username" : username})
                        else:
                            wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"fay","content":text, "username":username, "uid":uid, "id":content_id, "is_adopted":False}, "Username" : username})
                    if len(textlist) > 1:
                        i = 1
                        while i < len(textlist):
                            content_db.new_instance().add_content('fay','speak',textlist[i]['text'], username, uid)
                            if wsa_server.get_web_instance().is_connected(username):
                                wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"fay","content":textlist[i]['text'], "username":username, "uid":uid}, "Username" : username, 'robot': f'http://{cfg.fay_url}:5000/robot/Speaking.jpg'})
                            i+= 1                                
                    util.printInfo(1, interact.data.get('user'), '({}) {}'.format(self.__get_mood_voice(), text))                            
                    if wsa_server.get_instance().is_connected(username):
                        content = {'Topic': 'Unreal', 'Data': {'Key': 'text', 'Value': text}, 'Username' : username, 'robot': f'http://{cfg.fay_url}:5000/robot/Speaking.jpg'}
                        wsa_server.get_instance().add_cmd(content)
                
                    #声音输出
                    MyThread(target=self.say, args=[interact, text]).start()
                    
                    return text      
                
                elif (index == 2):#透传模式，用于适配自动播放控制及agent的通知工具
                    #记录用户
                    username = interact.data.get("user", "User")
                    if member_db.new_instance().is_username_exist(username)  == "notexists":
                        member_db.new_instance().add_user(username)
                    uid = member_db.new_instance().find_user(username)

                    if interact.data.get("text"):
                        #记录回复
                        text = interact.data.get("text")
                        self.write_to_file("./logs", "answer_result.txt", text)
                        content_db.new_instance().add_content('fay','speak', text, username, uid)

                        #文字输出：面板、聊天窗、log、数字人
                        if wsa_server.get_web_instance().is_connected(username):
                            wsa_server.get_web_instance().add_cmd({"panelMsg": text, "Username" : username, 'robot': f'http://{cfg.fay_url}:5000/robot/Speaking.jpg'})
                            wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"fay","content":text, "username":username, "uid":uid}, "Username" : username})  
                        util.printInfo(1, interact.data.get('user'), '({}) {}'.format(self.__get_mood_voice(), text))                            
                        if wsa_server.get_instance().is_connected(username):
                            content = {'Topic': 'Unreal', 'Data': {'Key': 'text', 'Value': text}, 'Username' : username, 'robot': f'http://{cfg.fay_url}:5000/robot/Speaking.jpg'}
                            wsa_server.get_instance().add_cmd(content)
                    
                    #声音输出
                    if cfg.key_chat_module != 'gpt_stream':
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
        return self.__process_interact(interact)

    # 发送情绪
    def __send_mood(self):
         while self.__running:
            time.sleep(3)
            if wsa_server.get_instance().is_connected("User"):
                if  self.old_mood != self.mood:
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'mood', 'Value': self.mood}}
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
    def say(self, interact, text):
        try:
            result = None
            audio_url = interact.data.get('audio')#透传的音频
            if audio_url is not None:
                file_name = 'sample-' + str(int(time.time() * 1000)) + '.wav'
                result = self.download_wav(audio_url, './samples/', file_name)
            elif config_util.config["interact"]["playSound"] or wsa_server.get_instance().is_connected(interact.data.get("user")) or self.__is_send_remote_device_audio(interact):#tts
                util.printInfo(1,  interact.data.get('user'), '合成音频...')
                tm = time.time()
                result = self.sp.to_sample(text.replace("*", ""), self.__get_mood_voice())
                util.printInfo(1,  interact.data.get('user'), '合成音频完成. 耗时: {} ms 文件:{}'.format(math.floor((time.time() - tm) * 1000), result))

            if result is not None:            
                MyThread(target=self.__process_output_audio, args=[result, interact, text]).start()
                return result
            else:
                if wsa_server.get_web_instance().is_connected(interact.data.get('user')):
                    wsa_server.get_web_instance().add_cmd({"panelMsg": "", 'Username' : interact.data.get('user'), 'robot': f'http://{cfg.fay_url}:5000/robot/Normal.jpg'})
                if wsa_server.get_instance().is_connected(interact.data.get("user")):
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ''}, 'Username' : interact.data.get('user'), 'robot': f'http://{cfg.fay_url}:5000/robot/Normal.jpg'}
                    wsa_server.get_instance().add_cmd(content)               
                
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
        
        pygame.mixer.init()  # 初始化pygame.mixer，只需要在此处初始化一次
        
        while self.__running:
            time.sleep(0.1)
            if not self.sound_query.empty():  # 如果队列不为空则播放音频
                file_url, audio_length, interact = self.sound_query.get()
                util.printInfo(1, interact.data.get('user'), '播放音频...')
                
                pygame.mixer.music.load(file_url)
                pygame.mixer.music.play()

                # 播放过程中计时，直到音频播放完毕
                length = 0
                while length < audio_length:
                    length += 0.01
                    time.sleep(0.01)
                
                util.printInfo(1, interact.data.get('user'), '结束播放！')
                
                # 播放完毕后通知
                if wsa_server.get_web_instance().is_connected(interact.data.get("user")):
                    wsa_server.get_web_instance().add_cmd({"panelMsg": "", 'Username': interact.data.get('user')})
    
    #推送远程音频
    def __send_remote_device_audio(self, file_url, interact):
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
                audio = AudioSegment.from_wav(file_url)
                audio_length = len(audio) / 1000.0  # 时长以秒为单位
            except Exception as e:
                audio_length = 3

            #自动播放关闭
            global auto_play_lock
            global can_auto_play
            with auto_play_lock:
                if self.timer is not None:
                    self.timer.cancel()
                    self.timer = None
                can_auto_play = False

            self.speaking = True
            #推送远程音频
            MyThread(target=self.__send_remote_device_audio, args=[file_url, interact]).start()       

            #发送音频给数字人接口
            if wsa_server.get_instance().is_connected(interact.data.get("user")):
                content = {'Topic': 'Unreal', 'Data': {'Key': 'audio', 'Value': os.path.abspath(file_url), 'HttpValue': f'http://{cfg.fay_url}:5000/audio/' + os.path.basename(file_url),  'Text': text, 'Time': audio_length, 'Type': interact.interleaver}, 'Username' : interact.data.get('user')}
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
            
            #播放完成通知
            threading.Timer(audio_length, self.send_play_end_msg, [interact]).start()

            #面板播放
            config_util.load_config()
            if config_util.config["interact"]["playSound"]:
                  self.sound_query.put((file_url, audio_length, interact))
            
        except Exception as e:
            print(e)

    def send_play_end_msg(self, interact):
        if wsa_server.get_web_instance().is_connected(interact.data.get('user')):
            wsa_server.get_web_instance().add_cmd({"panelMsg": "", 'Username' : interact.data.get('user'), 'robot': f'http://{cfg.fay_url}:5000/robot/Normal.jpg'})
        if wsa_server.get_instance().is_connected(interact.data.get("user")):
            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}, 'Username' : interact.data.get('user'), 'robot': f'http://{cfg.fay_url}:5000/robot/Normal.jpg'}
            wsa_server.get_instance().add_cmd(content)
        if config_util.config["interact"]["playSound"]:
            util.printInfo(1, interact.data.get('user'), '结束播放！')
        
        self.speaking = False
        global can_auto_play
        global auto_play_lock
        with auto_play_lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            if interact.interleaver != 'auto_play': #交互后暂停自动播放30秒
                self.timer = threading.Timer(30, self.set_auto_play)
                self.timer.start()
            else:
                can_auto_play = True

    #恢复自动播放(如果有)   
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
        content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
        wsa_server.get_instance().add_cmd(content)

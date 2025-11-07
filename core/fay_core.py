# -*- coding: utf-8 -*-
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
import uuid

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

        self.timer = None
        self.sound_query = Queue()
        self.think_mode_users = {}  # 使用字典存储每个用户的think模式状态
        self.think_time_users = {} #使用字典存储每个用户的think开始时间
        self.user_conv_map = {} #存储用户对话id及句子流序号
    
    def __remove_emojis(self, text):
        """
        改进的表情包过滤，避免误删除正常Unicode字符
        """
        # 更精确的emoji范围，避免误删除正常字符
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # 表情符号 (Emoticons)
            "\U0001F300-\U0001F5FF"  # 杂项符号和象形文字 (Miscellaneous Symbols and Pictographs)
            "\U0001F680-\U0001F6FF"  # 交通和地图符号 (Transport and Map Symbols)
            "\U0001F1E0-\U0001F1FF"  # 区域指示符号 (Regional Indicator Symbols)
            "\U0001F900-\U0001F9FF"  # 补充符号和象形文字 (Supplemental Symbols and Pictographs)
            "\U0001FA70-\U0001FAFF"  # 扩展A符号和象形文字 (Symbols and Pictographs Extended-A)
            "\U00002600-\U000026FF"  # 杂项符号 (Miscellaneous Symbols)
            "\U00002700-\U000027BF"  # 装饰符号 (Dingbats)
            "\U0000FE00-\U0000FE0F"  # 变体选择器 (Variation Selectors)
            "\U0001F000-\U0001F02F"  # 麻将牌 (Mahjong Tiles)
            "\U0001F0A0-\U0001F0FF"  # 扑克牌 (Playing Cards)
            "]+",
            flags=re.UNICODE,
        )

        # 保护常用的中文标点符号和特殊字符
        protected_chars = ["。", "，", "！", "？", "：", "；", "、", """, """, "'", "'", "（", "）", "【", "】", "《", "》"]

        # 先保存保护字符的位置
        protected_positions = {}
        for i, char in enumerate(text):
            if char in protected_chars:
                protected_positions[i] = char

        # 执行emoji过滤
        filtered_text = emoji_pattern.sub('', text)

        # 如果过滤后文本长度变化太大，可能误删了正常字符，返回原文本
        if len(filtered_text) < len(text) * 0.5:  # 如果删除了超过50%的内容
            return text

        return filtered_text

    def __process_stream_output(self, text, username, session_type="type2_stream", is_qa=False):
        """
        按流式方式分割和发送 type=2 的文本
        使用安全的流式文本处理器和状态管理器
        """
        if not text or text.strip() == "":
            return

        # 使用安全的流式文本处理器
        from utils.stream_text_processor import get_processor
        from utils.stream_state_manager import get_state_manager

        processor = get_processor()
        state_manager = get_state_manager()

        # 处理流式文本，is_qa=False表示普通模式
        success = processor.process_stream_text(text, username, is_qa=is_qa, session_type=session_type)

        if success:
            # 普通模式结束会话
            state_manager.end_session(username, conversation_id=stream_manager.new_instance().get_conversation_id(username))
        else:
            util.log(1, f"type=2流式处理失败，文本长度: {len(text)}")
            # 失败时也要确保结束会话
            state_manager.force_reset_user_state(username)

    #语音消息处理检查是否命中q&a
    def __get_answer(self, interleaver, text):
        answer = None
        # 全局问答
        answer, type = qa_service.QAService().question('qa',text)
        if answer is not None:
            return answer, type
        else:
            return None, None
        
       
    #消息处理
    def __process_interact(self, interact: Interact):
        if self.__running:
            try:
                index = interact.interact_type
                username = interact.data.get("user", "User")
                uid = member_db.new_instance().find_user(username)
                
                if index == 1: #语音、文字交互
                    
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
                        # 使用流式分割处理Q&A答案
                        self.__process_stream_output(text, username, session_type="qa", is_qa=True)
                           

                    return text      
                
                elif (index == 2):#透传模式：有音频则仅播音频；仅文本则流式+TTS
                    audio_url = interact.data.get("audio")
                    text = interact.data.get("text")

                    # 1) 存在音频：忽略文本，仅播放音频
                    if audio_url and str(audio_url).strip():
                        try:
                            audio_interact = Interact(
                                "stream", 1,
                                {"user": username, "msg": "", "isfirst": True, "isend": True, "audio": audio_url}
                            )
                            self.say(audio_interact, "")
                        except Exception:
                            pass
                        return 'success'

                    # 2) 只有文本：执行流式切分并TTS
                    if text and str(text).strip():
                        # 进行流式处理（用于TTS，流式处理中会记录到数据库）
                        self.__process_stream_output(text, username, f"type2_{interact.interleaver}", is_qa=False)
                        
                        # 不再需要额外记录，因为流式处理已经记录了
                        # self.__process_text_output(text, username, uid)
                        
                        return 'success'

                    # 没有有效内容
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

    #触发交互
    def on_interact(self, interact: Interact):
        #创建用户
        username = interact.data.get("user", "User")
        if member_db.new_instance().is_username_exist(username)  == "notexists":
            member_db.new_instance().add_user(username)
        try:
            from utils.stream_state_manager import get_state_manager
            import uuid
            if get_state_manager().is_session_active(username):
                stream_manager.new_instance().clear_Stream_with_audio(username)
            conv_id = "conv_" + str(uuid.uuid4())
            stream_manager.new_instance().set_current_conversation(username, conv_id)
            # 将当前会话ID附加到交互数据
            interact.data["conversation_id"] = conv_id
            # 允许新的生成
            stream_manager.new_instance().set_stop_generation(username, stop=False)
        except Exception:
            util.log(3, "开启新会话失败")

        if interact.interact_type == 1:
            MyThread(target=self.__process_interact, args=[interact]).start()
        else:
            return self.__process_interact(interact)

    #获取不同情绪声音
    def __get_mood_voice(self):
        voice = tts_voice.get_voice_of(config_util.config["attribute"]["voice"])
        if voice is None:
            voice = EnumVoice.XIAO_XIAO
        styleList = voice.value["styleList"]
        sayType = styleList["calm"]
        return sayType

    # 合成声音
    def say(self, interact, text, type = ""):
        try:
            uid = member_db.new_instance().find_user(interact.data.get("user"))
            is_end = interact.data.get("isend", False)
            is_first = interact.data.get("isfirst", False)
            username = interact.data.get("user", "User")
            
            # 提前进行会话有效性与中断检查，避免产生多余面板/数字人输出
            try:
                user_for_stop = interact.data.get("user", "User")
                conv_id_for_stop = interact.data.get("conversation_id")
                if not is_end and stream_manager.new_instance().should_stop_generation(user_for_stop, conversation_id=conv_id_for_stop):
                    return None
            except Exception:
                pass
            
            #无效流式文本提前结束
            if not is_first and not is_end and (text is None or text.strip() == ""):
                return None
                
            # 流式文本拼接存库
            content_id = 0
            if is_first == True:
                # reset any leftover think-mode at the start of a new reply
                try:
                    if uid is not None:
                        self.think_mode_users[uid] = False
                        if uid in self.think_time_users:
                            del self.think_time_users[uid]
                except Exception:
                    pass
                conv = interact.data.get("conversation_id") or ("conv_" + str(uuid.uuid4()))
                conv_no = 0
                # 创建第一条数据库记录，获得content_id
                if text and text.strip():
                    content_id = content_db.new_instance().add_content('fay', 'speak', text, username, uid)
                else:
                    content_id = content_db.new_instance().add_content('fay', 'speak', '', username, uid)
                
                # 保存content_id到会话映射中
                self.user_conv_map[username] = {
                    "conversation_id": conv, 
                    "conversation_msg_no": conv_no,
                    "content_id": content_id  # 新增：保存content_id
                }
            else:
                self.user_conv_map[username]["conversation_msg_no"] += 1
                # 获取之前保存的content_id
                content_id = self.user_conv_map.get(username, {}).get("content_id", 0)
                
                # 如果有新内容，更新数据库
                if content_id > 0 and text and text.strip():
                    # 获取当前已有内容
                    existing_content = content_db.new_instance().get_content_by_id(content_id)
                    if existing_content:
                        # 累积内容
                        accumulated_text = existing_content[3] + text
                        content_db.new_instance().update_content(content_id, accumulated_text)

            
            # 推送给前端和数字人
            try:
                user_for_stop = interact.data.get("user", "User")
                conv_id_for_stop = interact.data.get("conversation_id")
                if is_end or not stream_manager.new_instance().should_stop_generation(user_for_stop, conversation_id=conv_id_for_stop):
                    self.__process_text_output(text, interact.data.get('user'), uid, content_id, type, is_first, is_end)
            except Exception:
                self.__process_text_output(text, interact.data.get('user'), uid, content_id, type, is_first, is_end)
            
            # 处理think标签
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
                self.think_mode_users[uid] = True
                self.think_time_users[uid] = time.time()
   
            #”思考中“的输出
            if self.think_mode_users.get(uid, False):
                try:
                    user_for_stop = interact.data.get("user", "User")
                    conv_id_for_stop = interact.data.get("conversation_id")
                    should_block = stream_manager.new_instance().should_stop_generation(user_for_stop, conversation_id=conv_id_for_stop)
                except Exception:
                    should_block = False
                if not should_block:
                    if wsa_server.get_web_instance().is_connected(interact.data.get('user')):
                        wsa_server.get_web_instance().add_cmd({"panelMsg": "思考中...", "Username" : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Thinking.jpg'})
                    if wsa_server.get_instance().is_connected(interact.data.get("user")):
                        content = {'Topic': 'human', 'Data': {'Key': 'log', 'Value': "思考中..."}, 'Username' : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Thinking.jpg'}
                        wsa_server.get_instance().add_cmd(content)

            #”请稍等“的输出
            if self.think_mode_users.get(uid, False) == True and time.time() - self.think_time_users[uid] >= 5:
                self.think_time_users[uid] = time.time()
                text = "请稍等..."
            elif self.think_mode_users.get(uid, False) == True and "</think>" not in text:
                return None
            
            result = None
            audio_url = interact.data.get('audio', None)#透传的音频
            if audio_url is not None:#透传音频下载
                file_name = 'sample-' + str(int(time.time() * 1000)) + audio_url[-4:]
                result = self.download_wav(audio_url, './samples/', file_name)
            elif config_util.config["interact"]["playSound"] or wsa_server.get_instance().get_client_output(interact.data.get("user")) or self.__is_send_remote_device_audio(interact):#tts
                if text != None and text.replace("*", "").strip() != "":
                    # 检查是否需要停止TTS处理（按会话）
                    if stream_manager.new_instance().should_stop_generation(
                        interact.data.get("user", "User"),
                        conversation_id=interact.data.get("conversation_id")
                    ):
                        util.printInfo(1, interact.data.get('user'), 'TTS处理被打断，跳过音频合成')
                        return None
                        
                    # 先过滤表情符号，然后再合成语音
                    filtered_text = self.__remove_emojis(text.replace("*", ""))
                    if filtered_text is not None and filtered_text.strip() != "":
                        util.printInfo(1,  interact.data.get('user'), '合成音频...')
                        tm = time.time()
                        result = self.sp.to_sample(filtered_text, self.__get_mood_voice())
                        # 合成完成后再次检查会话是否仍有效，避免继续输出旧会话结果
                        try:
                            user_for_stop = interact.data.get("user", "User")
                            conv_id_for_stop = interact.data.get("conversation_id")
                            if stream_manager.new_instance().should_stop_generation(user_for_stop, conversation_id=conv_id_for_stop):
                                return None
                        except Exception:
                            pass
                        util.printInfo(1,  interact.data.get("user"), "合成音频完成. 耗时: {} ms 文件:{}".format(math.floor((time.time() - tm) * 1000), result))
            else:
                if is_end and wsa_server.get_web_instance().is_connected(interact.data.get('user')):
                    wsa_server.get_web_instance().add_cmd({"panelMsg": "", 'Username' : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Normal.jpg'})

            if result is not None or is_first or is_end:
                if is_end:#TODO 临时方案：如果结束标记，则延迟1秒处理,免得is end比前面的音频tts要快
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

                is_first = interact.data.get('isfirst') is True
                is_end = interact.data.get('isend') is True



                if file_url is not None:
                    util.printInfo(1, interact.data.get('user'), '播放音频...')

                    if is_first:
                        self.speaking = True
                    elif not is_end:
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
                        try:
                            user_for_stop = interact.data.get("user", "User")
                            conv_id_for_stop = interact.data.get("conversation_id")
                            if stream_manager.new_instance().should_stop_generation(user_for_stop, conversation_id=conv_id_for_stop):
                                try:
                                    pygame.mixer.music.stop()
                                except Exception:
                                    pass
                                break
                        except Exception:
                            pass
                        length += 0.01
                        time.sleep(0.01)

                if is_end:
                    self.play_end(interact)

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
            # 会话有效性与中断检查（最早返回，避免向面板/数字人发送任何旧会话输出）
            try:
                user_for_stop = interact.data.get("user", "User")
                conv_id_for_stop = interact.data.get("conversation_id")
                if stream_manager.new_instance().should_stop_generation(user_for_stop, conversation_id=conv_id_for_stop):
                    return
            except Exception:
                pass
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
            if file_url is not None and wsa_server.get_instance().get_client_output(interact.data.get("user")):
                content = {'Topic': 'human', 'Data': {'Key': 'audio', 'Value': os.path.abspath(file_url), 'HttpValue': f'{cfg.fay_url}/audio/' + os.path.basename(file_url),  'Text': text, 'Time': audio_length, 'Type': interact.interleaver, 'IsFirst': 1 if interact.data.get("isfirst", False) else 0,  'IsEnd': 1 if interact.data.get("isend", False) else 0, 'CONV_ID' : self.user_conv_map[interact.data.get("user", "User")]["conversation_id"], 'CONV_MSG_NO' : self.user_conv_map[interact.data.get("user", "User")]["conversation_msg_no"]  }, 'Username' : interact.data.get('user'), 'robot': f'{cfg.fay_url}/robot/Speaking.jpg'}
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
                # 检查是否需要停止音频播放（按会话）
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
            
        # gui日志区消息
        wsa_server.get_web_instance().add_cmd({
            "panelMsg": text,
            "Username": username
        })
        
        # 聊天窗消息
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

    def __send_digital_human_message(self, text, username, is_first=False, is_end=False):
        """
        发送消息到数字人（语音应该在say方法驱动数字人输出）
        :param text: 消息文本
        :param username: 用户名
        :param is_first: 是否是第一段文本
        :param is_end: 是否是最后一段文本
        """
        full_text = self.__remove_emojis(text.replace("*", ""))
        if wsa_server.get_instance().is_connected(username):
            content = {
                'Topic': 'human',
                'Data': {
                    'Key': 'text',
                    'Value': full_text,
                    'IsFirst': 1 if is_first else 0,
                    'IsEnd': 1 if is_end else 0
                },
                'Username': username
            }
            wsa_server.get_instance().add_cmd(content)

    def __process_text_output(self, text, username, uid, content_id, type, is_first=False, is_end=False):
        """
        完整文本输出到各个终端
        :param text: 主要回复文本
        :param textlist: 额外回复列表
        :param username: 用户名
        :param uid: 用户ID
        :param type: 消息类型
        :param is_first: 是否是第一段文本
        :param is_end: 是否是最后一段文本
        """
        if text:
            text = text.strip()
            
        # 记录主回复
        # content_id = self.__record_response(text, username, uid)
        
        # 发送主回复到面板和数字人
        self.__send_panel_message(text, username, uid, content_id, type)
        self.__send_digital_human_message(text, username, is_first, is_end)
        
        # 打印日志
        util.printInfo(1, username, '({}) {}'.format("llm", text))

import importlib
fay_booter = importlib.import_module('fay_booter')


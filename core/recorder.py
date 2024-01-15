import audioop
import math
import time
import threading
from abc import abstractmethod

from ai_module.ali_nls import ALiNls
from ai_module.funasr import FunASR
from core import wsa_server
from scheduler.thread_manager import MyThread
from utils import util
from utils import config_util as cfg
import numpy as np
# 启动时间 (秒)
_ATTACK = 0.2

# 释放时间 (秒)
_RELEASE = 0.75


class Recorder:

    def __init__(self, fay):
        self.__fay = fay

        

        self.__running = True
        self.__processing = False
        self.__history_level = []
        self.__history_data = []
        self.__dynamic_threshold = 0.5 # 声音识别的音量阈值

        self.__MAX_LEVEL = 25000
        self.__MAX_BLOCK = 100
        
        #Edit by xszyou in 20230516:增加本地asr
        self.ASRMode = cfg.ASR_mode
        self.__aLiNls = self.asrclient()
        self.is_awake = False
        self.wakeup_matched = False
        if cfg.config['source']['wake_word_enabled']:
            self.timer = threading.Timer(60, self.reset_wakeup_status)  # 60秒后执行reset_wakeup_status方法


    def asrclient(self):
        if self.ASRMode == "ali":
            asrcli = ALiNls()
        elif self.ASRMode == "funasr":
            asrcli = FunASR()
        return asrcli

    

    def __get_history_average(self, number):
        total = 0
        num = 0
        for i in range(len(self.__history_level) - 1, -1, -1):
            level = self.__history_level[i]
            total += level
            num += 1
            if num >= number:
                break
        return total / num

    def __get_history_percentage(self, number):
        return (self.__get_history_average(number) / self.__MAX_LEVEL) * 1.05 + 0.02

    def __print_level(self, level):
        text = ""
        per = level / self.__MAX_LEVEL
        if per > 1:
            per = 1
        bs = int(per * self.__MAX_BLOCK)
        for i in range(bs):
            text += "#"
        for i in range(self.__MAX_BLOCK - bs):
            text += "-"
        print(text + " [" + str(int(per * 100)) + "%]")

    def reset_wakeup_status(self):
        self.wakeup_matched = False        

    def __waitingResult(self, iat: asrclient):
        if self.__fay.playing:
            return
        self.processing = True
        t = time.time()
        tm = time.time()
        # 等待结果返回
        while not iat.done and time.time() - t < 1:
            time.sleep(0.01)
        text = iat.finalResults
        util.log(1, "语音处理完成！ 耗时: {} ms".format(math.floor((time.time() - tm) * 1000)))
        if len(text) > 0:
            if cfg.config['source']['wake_word_enabled']:

                if cfg.config['source']['wake_word_type'] == 'common':

                    if not self.wakeup_matched:
                        #唤醒词判断
                        wake_word =  cfg.config['source']['wake_word']
                        wake_word_list = wake_word.split(',')
                        wake_up = False
                        for word in wake_word_list:
                            if word in text:
                                    wake_up = True
                        if wake_up:
                            self.wakeup_matched = True  # 唤醒成功
                            util.log(1, "唤醒成功！")
                            self.on_speaking('唤醒')
                            self.processing = False
                            self.timer.cancel()  # 取消之前的计时器任务
                        else:
                            util.log(1, "[!] 待唤醒！")
                            wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                
  
                    else:
                        self.on_speaking(text)
                        self.processing = False
                        self.timer.cancel()  # 取消之前的计时器任务
                        self.timer = threading.Timer(60, self.reset_wakeup_status)  # 重设计时器为60秒
                        self.timer.start()
                elif  cfg.config['source']['wake_word_type'] == 'front':
                    wake_word =  cfg.config['source']['wake_word']
                    wake_word_list = wake_word.split(',')
                    wake_up = False
                    for word in wake_word_list:
                        if text.startswith(word):
                            wake_up = True
                            break
                    if wake_up:
                        util.log(1, "唤醒成功！")
                        self.on_speaking(text)
                        self.processing = False
                    else:
                        util.log(1, "[!] 待唤醒！")
                        wsa_server.get_web_instance().add_cmd({"panelMsg": ""})


            else:
                  self.on_speaking(text)
                  self.processing = False
        else:
            if self.wakeup_matched:
                self.wakeup_matched = False
            util.log(1, "[!] 语音未检测到内容！")
            self.processing = False
            self.dynamic_threshold = self.__get_history_percentage(30)
            wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
            if not cfg.config["interact"]["playSound"]: # 非展板播放
                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                wsa_server.get_instance().add_cmd(content)

    def __record(self):   
        try:
            stream = self.get_stream() #把get stream的方式封装出来方便实现麦克风录制及网络流等不同的流录制子类
        except Exception as e:
                print(e)
                util.log(1, "请检查设备是否有误，再重新启动!")
                return
        isSpeaking = False
        last_mute_time = time.time()
        last_speaking_time = time.time()
        data = None
        while self.__running:
            try:
                data = stream.read(1024, exception_on_overflow=False)
            except Exception as e:
                data = None
                print(e)
                util.log(1, "请检查设备是否有误，再重新启动!")
                return
            if not data:
                continue
            

            if  cfg.config['source']['record']['enabled'] and not self.is_remote():
                if len(cfg.config['source']['record'])<3:
                    channels = 1
                else:
                    channels = int(cfg.config['source']['record']['channels'])
                #只获取第一声道
                data = np.frombuffer(data, dtype=np.int16)
                data = np.reshape(data, (-1, channels))  # reshaping the array to split the channels
                mono = data[:, 0]  # taking the first channel
                data = mono.tobytes()  


            level = audioop.rms(data, 2)
            if len(self.__history_data) >= 5:
                self.__history_data.pop(0)
            if len(self.__history_level) >= 500:
                self.__history_level.pop(0)
            self.__history_data.append(data)
            self.__history_level.append(level)

            percentage = level / self.__MAX_LEVEL
            history_percentage = self.__get_history_percentage(30)

            if history_percentage > self.__dynamic_threshold:
                self.__dynamic_threshold += (history_percentage - self.__dynamic_threshold) * 0.0025
            elif history_percentage < self.__dynamic_threshold:
                self.__dynamic_threshold += (history_percentage - self.__dynamic_threshold) * 1

            soon = False
            if percentage > self.__dynamic_threshold and not self.__fay.speaking:
                last_speaking_time = time.time()
                if not self.__processing and not isSpeaking and time.time() - last_mute_time > _ATTACK:
                    soon = True  #
                    isSpeaking = True  #用户正在说话
                    util.log(3, "聆听中...")
                    self.__aLiNls = self.asrclient()
                    try:
                        self.__aLiNls.start()
                    except Exception as e:
                        print(e)
                    for buf in self.__history_data:
                        self.__aLiNls.send(buf)
            else:
                last_mute_time = time.time()
                if isSpeaking:
                    if time.time() - last_speaking_time > _RELEASE:
                        isSpeaking = False
                        self.__aLiNls.end()
                        util.log(1, "语音处理中...")
                        self.__fay.last_quest_time = time.time()
                        self.__waitingResult(self.__aLiNls)
            if not soon and isSpeaking:
                self.__aLiNls.send(data)
     

    def set_processing(self, processing):
        self.__processing = processing

    def start(self):
        MyThread(target=self.__record).start()

    def stop(self):
        self.__running = False
        self.__aLiNls.end()

    @abstractmethod
    def on_speaking(self, text):
        pass

    #TODO Edit by xszyou on 20230113:把流的获取方式封装出来方便实现麦克风录制及网络流等不同的流录制子类
    @abstractmethod
    def get_stream(self):
        pass

    @abstractmethod
    def is_remote(self):
        pass

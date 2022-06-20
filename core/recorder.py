import audioop
import math
import time
from abc import abstractmethod

import pyaudio

from ai_module.ali_nls import ALiNls
from core import wsa_server
from scheduler.thread_manager import MyThread
from utils import util

# 启动时间 (秒)
_ATTACK = 0.2

# 释放时间 (秒)
_RELEASE = 0.75


class Recorder:

    def __init__(self, device, fay):
        self.__device = device
        self.__fay = fay

        self.__RATE = 16000
        self.__FORMAT = pyaudio.paInt16
        self.__CHANNELS = 1

        self.__running = True
        self.__processing = False
        self.__history_level = []
        self.__history_data = []
        self.__dynamic_threshold = 0.5

        self.__MAX_LEVEL = 25000
        self.__MAX_BLOCK = 100

        self.__aLiNls = ALiNls()

    def __findInternalRecordingDevice(self, p):
        for i in range(p.get_device_count()):
            devInfo = p.get_device_info_by_index(i)
            if devInfo['name'].find(self.__device) >= 0 and devInfo['hostApi'] == 0:
                return i
        util.log(1, '[!] 无法找到内录设备!')
        return -1

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

    def __waitingResult(self, iat: ALiNls):
        self.processing = True
        t = time.time()
        tm = time.time()
        # 等待结果返回
        while not iat.done and time.time() - t < 1:
            time.sleep(0.01)
        text = iat.finalResults
        util.log(1, "语音处理完成！ 耗时: {} ms".format(math.floor((time.time() - tm) * 1000)))
        if len(text) > 0:
            self.on_speaking(text)
            self.processing = False
        else:
            util.log(1, "[!] 语音未检测到内容！")
            self.processing = False
            self.dynamic_threshold = self.__get_history_percentage(30)
            wsa_server.get_web_instance().add_cmd({"panelMsg": ""})

    def __record(self):
        p = pyaudio.PyAudio()
        device_id = self.__findInternalRecordingDevice(p)
        if device_id < 0:
            return
        stream = p.open(input_device_index=device_id, rate=self.__RATE, format=self.__FORMAT, channels=self.__CHANNELS, input=True)

        isSpeaking = False
        last_mute_time = time.time()
        last_speaking_time = time.time()
        while self.__running:
            data = stream.read(1024)
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
                    soon = True
                    isSpeaking = True
                    util.log(3, "聆听中...")
                    self.__aLiNls = ALiNls()
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

        stream.stop_stream()
        stream.close()
        p.terminate()

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

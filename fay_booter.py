import time
from io import BytesIO
import socket
import pyaudio
import numpy as np
import scipy.io.wavfile as wav
import wave

from core.interact import Interact
from core.recorder import Recorder
from core.fay_core import FeiFei
from core.viewer import Viewer
from scheduler.thread_manager import MyThread
from utils import util, config_util, stream_util, ngrok_util
from core.wsa_server import MyServer




feiFei: FeiFei = None
viewerListener: Viewer = None
recorderListener: Recorder = None

__running = True


class ViewerListener(Viewer):

    def __init__(self, url):
        super().__init__(url)

    def on_interact(self, interact: Interact, event_time):
        type_names = {
            1: '发言',
            2: '进入',
            3: '送礼',
            4: '关注'
        }
        util.printInfo(1, type_names[interact.interact_type], '{}: {}'.format(interact.data["user"], interact.data["msg"]), event_time)
        if interact.interact_type == 1:
            feiFei.last_quest_time = time.time()
        thr = MyThread(target=feiFei.on_interact, args=[interact])
        thr.start()
        thr.join()

    def on_change_state(self, is_live_started):
        feiFei.set_sleep(not is_live_started)
        pass

#录制麦克风音频输入并传给aliyun
class RecorderListener(Recorder):

    def __init__(self, device, fei):
        self.__device = device
        self.__RATE = 16000
        self.__FORMAT = pyaudio.paInt16
        self.__CHANNELS = 1

        super().__init__(fei)

    def on_speaking(self, text):
        if len(text) > 1:
            interact = Interact("mic", 1, {'user': '', 'msg': text})
            util.printInfo(3, "语音", '{}'.format(interact.data["msg"]), time.time())
            feiFei.on_interact(interact)
            time.sleep(2)

    def get_stream(self):
        self.paudio = pyaudio.PyAudio()
        device_id = self.__findInternalRecordingDevice(self.paudio)
        if device_id < 0:
            return
        self.stream = self.paudio.open(input_device_index=device_id, rate=self.__RATE, format=self.__FORMAT, channels=self.__CHANNELS, input=True)
        return self.stream

    def __findInternalRecordingDevice(self, p):
        for i in range(p.get_device_count()):
            devInfo = p.get_device_info_by_index(i)
            if devInfo['name'].find(self.__device) >= 0 and devInfo['hostApi'] == 0:
                return i
        util.log(1, '[!] 无法找到内录设备!')
        return -1
    
    def stop(self):
        super().stop()
        self.stream.stop_stream()
        self.stream.close()
        self.paudio.terminate()


#TODO Edit by xszyou on 20230113:录制远程设备音频输入并传给aliyun
class DeviceInputListener(Recorder):
    def __init__(self, fei):
        super().__init__(fei)
        self.__running = True
        self.ngrok = None
        self.streamCache = None
        self.thread = MyThread(target=self.run)
        self.thread.start()  #启动远程音频输入设备监听线程

    def run(self):
        #启动ngork
        self.streamCache = stream_util.StreamCache(1024*1024*20)
        if config_util.key_ngrok_cc_id and config_util.key_ngrok_cc_id is not None and config_util.key_ngrok_cc_id.strip() != "":
            MyThread(target=self.start_ngrok, args=[config_util.key_ngrok_cc_id]).start()
        addr = None
        while self.__running:
            try:
                
                data = b""
                while feiFei.deviceConnect:
                    data = feiFei.deviceConnect.recv(1024)
                    self.streamCache.write(data)
                    time.sleep(0.005)
                self.streamCache.clear()
         
            except Exception as err:
                pass
            time.sleep(1)

    def on_speaking(self, text):
        if len(text) > 1:
            interact = Interact("mic", 1, {'user': '', 'msg': text})
            util.printInfo(3, "语音", '{}'.format(interact.data["msg"]), time.time())
            feiFei.on_interact(interact)
            time.sleep(2)

    #recorder会等待stream不为空才开始录音
    def get_stream(self):
        while self.streamCache is None:
            time.sleep(1)
            pass
        return self.streamCache

    def stop(self):
        super().stop()
        self.__running = False
        if config_util.key_ngrok_cc_id and config_util.key_ngrok_cc_id is not None and config_util.key_ngrok_cc_id.strip() != "":
            self.ngrok.stop()

    def start_ngrok(self, clientId):
        self.ngrok = ngrok_util.NgrokCilent(clientId)
        self.ngrok.start()
        



def console_listener():
    type_names = {
        1: '发言',
        2: '进入',
        3: '送礼',
        4: '关注'
    }
    while __running:
        text = input()
        args = text.split(' ')

        if len(args) == 0 or len(args[0]) == 0:
            continue

        if args[0] == 'help':
            util.log(1, 'in <msg> \t通过控制台交互')
            util.log(1, 'restart \t重启服务')
            util.log(1, 'stop \t\t关闭服务')

        elif args[0] == 'stop':
            stop()
            break

        elif args[0] == 'restart':
            stop()
            time.sleep(0.1)
            start()

        elif args[0] == 'in':
            if len(args) == 1:
                util.log(1, '错误的参数！')
            msg = text[3:len(text)]
            i = 1
            try:
                i = int(msg)
            except:
                pass
            if i < 1:
                i = 1
            if i > 4:
                i = 4
            util.printInfo(1, type_names[i], '{}: {}'.format('控制台', msg))
            if i == 1:
                feiFei.last_quest_time = time.time()
            thr = MyThread(target=feiFei.on_interact, args=[("console", i, '', msg)])
            thr.start()
            thr.join()

        else:
            util.log(1, '未知命令！使用 \'help\' 获取帮助.')

#停止服务
def stop():
    global feiFei
    global viewerListener
    global recorderListener
    global __running
    global deviceInputListener

    util.log(1, '正在关闭服务...')
    __running = False
    if viewerListener is not None:
        util.log(1, '正在关闭直播服务...')
        viewerListener.stop()
    if recorderListener is not None:
        util.log(1, '正在关闭录音服务...')
        recorderListener.stop()
    if deviceInputListener is not None:
        util.log(1, '正在关闭远程音频输入输出服务...')
        deviceInputListener.stop()
    util.log(1, '正在关闭核心服务...')
    feiFei.stop()
    util.log(1, '服务已关闭！')


def start():
    # global ws_server
    global feiFei
    global viewerListener
    global recorderListener
    global __running
    global deviceInputListener

    util.log(1, '开启服务...')
    __running = True
    util.log(1, '读取配置...')
    config_util.load_config()


    

    util.log(1, '开启核心服务...')
    feiFei = FeiFei()
    feiFei.start()

    liveRoom = config_util.config['source']['liveRoom']
    record = config_util.config['source']['record']

    

    if liveRoom['enabled']:
        util.log(1, '开启直播服务...')
        viewerListener = ViewerListener(liveRoom['url'])  # 监听直播间
        viewerListener.start()

    if record['enabled']:
        util.log(1, '开启录音服务...')
        recorderListener = RecorderListener(record['device'], feiFei)  # 监听麦克风
        recorderListener.start()

    #TODO edit by xszyou on 20230113:通过此服务来连接k210、手机等音频输入设备
    util.log(1,'开启远程设备音频输入服务...')
    deviceInputListener = DeviceInputListener(feiFei)  # 设备音频输入输出麦克风
    deviceInputListener.start()

    util.log(1, '注册命令...')
    MyThread(target=console_listener).start()  # 监听控制台

    util.log(1, '完成!')
    util.log(1, '使用 \'help\' 获取帮助.')

    

# if __name__ == '__main__':
#     ws_server: MyServer = None
#     feiFei: FeiFei = None
#     viewerListener: Viewer = None
#     recorderListener: Recorder = None
#     start()
# config_util.save_config()

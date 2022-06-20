import time

from core.recorder import Recorder
from core.fay_core import FeiFei
from core.viewer import Viewer
from scheduler.thread_manager import MyThread
from utils import util, config_util

feiFei: FeiFei = None
viewerListener: Viewer = None
recorderListener: Recorder = None

__running = True


class ViewerListener(Viewer):

    def __init__(self, url):
        super().__init__(url)

    def on_interact(self, interact, event_time):
        type_names = {
            1: '发言',
            2: '进入',
            3: '送礼',
            4: '关注'
        }
        util.printInfo(1, type_names[interact[0]], '{}: {}'.format(interact[1], interact[2]), event_time)
        if interact[0] == 1:
            feiFei.last_quest_time = time.time()
        thr = MyThread(target=feiFei.on_interact, args=[interact])
        thr.start()
        thr.join()

    def on_change_state(self, is_live_started):
        feiFei.set_sleep(not is_live_started)
        pass


class RecorderListener(Recorder):

    def __init__(self, device, fei):
        super().__init__(device, fei)

    def on_speaking(self, text):
        interact = (1, '', text)
        util.printInfo(3, "语音", '{}'.format(interact[2]), time.time())
        feiFei.on_interact(interact)
        time.sleep(2)


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
            thr = MyThread(target=feiFei.on_interact, args=[(i, '', msg)])
            thr.start()
            thr.join()

        else:
            util.log(1, '未知命令！使用 \'help\' 获取帮助.')


def stop():
    global feiFei
    global viewerListener
    global recorderListener
    global __running

    util.log(1, '正在关闭服务...')
    __running = False
    # util.log('正在关闭通讯服务...')
    # wsa_server.get_instance().stop_server()
    if viewerListener is not None:
        util.log(1, '正在关闭直播服务...')
        viewerListener.stop()
    if recorderListener is not None:
        util.log(1, '正在关闭录音服务...')
        recorderListener.stop()
    util.log(1, '正在关闭核心服务...')
    feiFei.stop()
    util.log(1, '服务已关闭！')


def start():
    # global ws_server
    global feiFei
    global viewerListener
    global recorderListener
    global __running

    util.log(1, '开启服务...')
    __running = True
    util.log(1, '读取配置...')
    config_util.load_config()
    #
    # util.log('开启通讯服务...')
    # ws_server = MyServer()
    # ws_server.start_server()

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

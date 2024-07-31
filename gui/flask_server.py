import json
import time

import pyaudio
from flask import Flask, render_template, request
from flask_cors import CORS

import fay_booter

from core import tts_voice
from gevent import pywsgi
from scheduler.thread_manager import MyThread
from utils import config_util
from core import wsa_server
from core.interact import Interact
from core import fay_core
from utils import util

__app = Flask(__name__)
CORS(__app, supports_credentials=True)


def __get_template():
    return render_template('index.html')


def __get_device_list():
    audio = pyaudio.PyAudio()
    device_list = []
    for i in range(audio.get_device_count()):
        devInfo = audio.get_device_info_by_index(i)
        if devInfo['hostApi'] == 0:
            device_list.append(devInfo["name"])
    
    return list(set(device_list))


@__app.route('/api/submit', methods=['post'])
def api_submit():
    data = request.values.get('data')
    # print(data)
    config_data = json.loads(data)
    if(config_data['config']['source']['record']['enabled']):
        config_data['config']['source']['record']['channels'] = 0
        audio = pyaudio.PyAudio()
        for i in range(audio.get_device_count()):
            devInfo = audio.get_device_info_by_index(i)
            if devInfo['name'].find(config_data['config']['source']['record']['device']) >= 0 and devInfo['hostApi'] == 0:
                 config_data['config']['source']['record']['channels'] = devInfo['maxInputChannels']

    config_util.save_config(config_data['config'])


    return '{"result":"successful"}'


@__app.route('/api/get-data', methods=['post'])
def api_get_data():
    config_data = config_util.config
    if  wsa_server.new_instance().isConnect:
        config_data['interact']['playSound'] = False
    else:
        config_data['interact']['playSound'] = True
    config_util.save_config(config_data)
    voice_list = tts_voice.get_voice_list()
    send_voice_list = []
    if config_util.tts_module == 'ali':
        wsa_server.get_web_instance().add_cmd({
        "voiceList": [
            {"id": "abin", "name": "阿斌"},
            {"id": "zhixiaobai", "name": "知小白"},
            {"id": "zhixiaoxia", "name": "知小夏"},
            {"id": "zhixiaomei", "name": "知小妹"},
            {"id": "zhigui", "name": "知柜"},
            {"id": "zhishuo", "name": "知硕"},
            {"id": "aixia", "name": "艾夏"},
            {"id": "zhifeng_emo", "name": "知锋_多情感"},
            {"id": "zhibing_emo", "name": "知冰_多情感"},
            {"id": "zhimiao_emo", "name": "知妙_多情感"},
            {"id": "zhimi_emo", "name": "知米_多情感"},
            {"id": "zhiyan_emo", "name": "知燕_多情感"},
            {"id": "zhibei_emo", "name": "知贝_多情感"},
            {"id": "zhitian_emo", "name": "知甜_多情感"},
            {"id": "xiaoyun", "name": "小云"},
            {"id": "xiaogang", "name": "小刚"},
            {"id": "ruoxi", "name": "若兮"},
            {"id": "siqi", "name": "思琪"},
            {"id": "sijia", "name": "思佳"},
            {"id": "sicheng", "name": "思诚"},
            {"id": "aiqi", "name": "艾琪"},
            {"id": "aijia", "name": "艾佳"},
            {"id": "aicheng", "name": "艾诚"},
            {"id": "aida", "name": "艾达"},
            {"id": "ninger", "name": "宁儿"},
            {"id": "ruilin", "name": "瑞琳"},
            {"id": "siyue", "name": "思悦"},
            {"id": "aiya", "name": "艾雅"},
            {"id": "aimei", "name": "艾美"},
            {"id": "aiyu", "name": "艾雨"},
            {"id": "aiyue", "name": "艾悦"},
            {"id": "aijing", "name": "艾婧"},
            {"id": "xiaomei", "name": "小美"},
            {"id": "aina", "name": "艾娜"},
            {"id": "yina", "name": "伊娜"},
            {"id": "sijing", "name": "思婧"},
            {"id": "sitong", "name": "思彤"},
            {"id": "xiaobei", "name": "小北"},
            {"id": "aitong", "name": "艾彤"},
            {"id": "aiwei", "name": "艾薇"},
            {"id": "aibao", "name": "艾宝"},
            {"id": "shanshan", "name": "姗姗"},
            {"id": "chuangirl", "name": "小玥"},
            {"id": "lydia", "name": "Lydia"},
            {"id": "aishuo", "name": "艾硕"},
            {"id": "qingqing", "name": "青青"},
            {"id": "cuijie", "name": "翠姐"},
            {"id": "xiaoze", "name": "小泽"},
            {"id": "zhimao", "name": "知猫"},
            {"id": "zhiyuan", "name": "知媛"},
            {"id": "zhiya", "name": "知雅"},
            {"id": "zhiyue", "name": "知悦"},
            {"id": "zhida", "name": "知达"},
            {"id": "zhistella", "name": "知莎"},
            {"id": "kelly", "name": "Kelly"},
            {"id": "jiajia", "name": "佳佳"},
            {"id": "taozi", "name": "桃子"},
            {"id": "guijie", "name": "柜姐"},
            {"id": "stella", "name": "Stella"},
            {"id": "stanley", "name": "Stanley"},
            {"id": "kenny", "name": "Kenny"},
            {"id": "rosa", "name": "Rosa"},
            {"id": "mashu", "name": "马树"},
            {"id": "xiaoxian", "name": "小仙"},
            {"id": "yuer", "name": "悦儿"},
            {"id": "maoxiaomei", "name": "猫小美"},
            {"id": "aifei", "name": "艾飞"},
            {"id": "yaqun", "name": "亚群"},
            {"id": "qiaowei", "name": "巧薇"},
            {"id": "dahu", "name": "大虎"},
            {"id": "ailun", "name": "艾伦"},
            {"id": "jielidou", "name": "杰力豆"},
            {"id": "laotie", "name": "老铁"},
            {"id": "laomei", "name": "老妹"},
            {"id": "aikan", "name": "艾侃"}
        ]
    })
    elif config_util.tts_module == 'volcano':
        wsa_server.get_web_instance().add_cmd({
        "voiceList": [
            {"id": "BV001_streaming", "name": "通用女声"},
            {"id": "BV002_streaming", "name": "通用男声"},
            {"id": "zh_male_jingqiangkanye_moon_bigtts", "name": "京腔侃爷/Harmony"},
            {"id": "zh_female_shuangkuaisisi_moon_bigtts", "name": "爽快思思/Skye"},
            {"id": "zh_male_wennuanahu_moon_bigtts", "name": "温暖阿虎/Alvin"},
            {"id": "zh_female_wanwanxiaohe_moon_bigtts", "name": "湾湾小何"},
        ]
    }) 
    else:
        voice_list = tts_voice.get_voice_list()
        send_voice_list = []
        for voice in voice_list: 
            voice_data = voice.value 
            send_voice_list.append({"id": voice_data['name'], "name": voice_data['name']})
        wsa_server.get_web_instance().add_cmd({
            "voiceList": send_voice_list
        })
    wsa_server.get_web_instance().add_cmd({"deviceList": __get_device_list()})
    return json.dumps({'config': config_util.config})


@__app.route('/api/start-live', methods=['post'])
def api_start_live():
    # time.sleep(5)
    fay_booter.start()
    time.sleep(1)
    wsa_server.get_web_instance().add_cmd({"liveState": 1})
    return '{"result":"successful"}'


@__app.route('/api/stop-live', methods=['post'])
def api_stop_live():
    # time.sleep(1)
    fay_booter.stop()
    time.sleep(1)
    wsa_server.get_web_instance().add_cmd({"liveState": 0})
    return '{"result":"successful"}'

wx_msg_msg_id = ''
@__app.route('/api/get-wx-msg', methods=['post'])
def api_get_wx_msg():
    global wx_msg_msg_id
    if fay_booter.__running:
        data = request.json
        info = data['events'][0]
        if wx_msg_msg_id != info['msg_id']:
            wx_msg_msg_id = info['msg_id']
            if info['decoded_type'] == 'enter':
                #进入
                interact = Interact("live", 2, {"user": info['nickname'], "msg": "来了"})
            elif info['decoded_type'] == 'comment':
                #留言
                interact = Interact("live", 1, {"user": info['nickname'], "msg": info['content']})
                fay_core.new_instance().last_quest_time = time.time()
            elif info['decoded_type'] == 'gift':
                #礼物
                interact = Interact("live", 3, {"user": info['nickname'], "msg": "礼物", "gift": '礼物', "amount": info['gift_num'],})
            MyThread(target=fay_core.new_instance().on_interact, args=[interact]).start()
    else:
        util.log(1, "请先进行开启")    
    return '{"result":"successful"}' 


@__app.route('/', methods=['get'])
def home_get():
    return __get_template()


@__app.route('/', methods=['post'])
def home_post():
    return __get_template()

def run():
    server = pywsgi.WSGIServer(('0.0.0.0',5000), __app)
    server.serve_forever()

def start():
    MyThread(target=run).start()

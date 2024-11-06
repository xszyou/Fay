import importlib
import json
import time
import os
import pyaudio
import re
from flask import Flask, render_template, request, jsonify, Response, send_file
from flask_cors import CORS
import requests
import datetime

import fay_booter

from tts import tts_voice
from gevent import pywsgi
from scheduler.thread_manager import MyThread
from utils import config_util, util
from core import wsa_server
from core import fay_core
from core import content_db
from core.interact import Interact
from core import member_db
import fay_booter
from flask_httpauth import HTTPBasicAuth
from core import qa_service

__app = Flask(__name__)
auth = HTTPBasicAuth()
CORS(__app, supports_credentials=True)

def load_users():
    with open('verifier.json') as f:
        users = json.load(f)
    return users

users = load_users()

@auth.verify_password
def verify_password(username, password):
    if not users or config_util.start_mode == 'common':
        return True
    if username in users and users[username] == password:
        return username


def __get_template():
    return render_template('index.html')


def __get_device_list():
    if config_util.start_mode == 'common':
        audio = pyaudio.PyAudio()
        device_list = []
        for i in range(audio.get_device_count()):
            devInfo = audio.get_device_info_by_index(i)
            if devInfo['hostApi'] == 0:
                device_list.append(devInfo["name"])
        
        return list(set(device_list))
    else:
        return []


@__app.route('/api/submit', methods=['post'])
def api_submit():
    data = request.values.get('data')
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
    config_util.load_config()
    voice_list = tts_voice.get_voice_list()
    send_voice_list = []
    if config_util.tts_module == 'ali':
        voice_list = [
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
        send_voice_list = {"voiceList": voice_list}
        wsa_server.get_web_instance().add_cmd(send_voice_list)
    elif config_util.tts_module == 'volcano':
        voice_list = {
        "voiceList": [
            {"id": "BV001_streaming", "name": "通用女声"},
            {"id": "BV002_streaming", "name": "通用男声"},
            {"id": "zh_male_jingqiangkanye_moon_bigtts", "name": "京腔侃爷/Harmony"},
            {"id": "zh_female_shuangkuaisisi_moon_bigtts", "name": "爽快思思/Skye"},
            {"id": "zh_male_wennuanahu_moon_bigtts", "name": "温暖阿虎/Alvin"},
            {"id": "zh_female_wanwanxiaohe_moon_bigtts", "name": "湾湾小何"},
        ]
    }
        send_voice_list = {"voiceList": voice_list}
        wsa_server.get_web_instance().add_cmd(send_voice_list)
    else:
        voice_list = tts_voice.get_voice_list()
        send_voice_list = []
        for voice in voice_list: 
            voice_data = voice.value 
            send_voice_list.append({"id": voice_data['name'], "name": voice_data['name']})
        wsa_server.get_web_instance().add_cmd({
            "voiceList": send_voice_list
        })
        voice_list = send_voice_list
    wsa_server.get_web_instance().add_cmd({"deviceList": __get_device_list()})
    if fay_booter.is_running():
        wsa_server.get_web_instance().add_cmd({"liveState": 1})
    return json.dumps({'config': config_util.config, 'voice_list' : voice_list})


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

@__app.route('/api/send', methods=['post'])
def api_send():
    data = request.values.get('data')
    info = json.loads(data)
    interact = Interact("text", 1, {'user': info['username'], 'msg': info['msg']})
    util.printInfo(3, "文字发送按钮", '{}'.format(interact.data["msg"]), time.time())
    fay_booter.feiFei.on_interact(interact)
    return '{"result":"successful"}'

#获取指定用户的消息记录
@__app.route('/api/get-msg', methods=['post'])
def api_get_Msg():
    data = request.form.get('data')
    data = json.loads(data)
    uid = member_db.new_instance().find_user(data["username"])
    contentdb = content_db.new_instance()
    if uid == 0:
        return json.dumps({'list': []})
    else:
        list = contentdb.get_list('all','desc',1000, uid)
    relist = []
    i = len(list)-1
    while i >= 0:
        timetext = datetime.datetime.fromtimestamp(list[i][3]).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        relist.append(dict(type=list[i][0], way=list[i][1], content=list[i][2], createtime=list[i][3], timetext=timetext, username=list[i][5], id=list[i][6], is_adopted=list[i][7]))
        i -= 1
    if fay_booter.is_running():
        wsa_server.get_web_instance().add_cmd({"liveState": 1})
    return json.dumps({'list': relist})

@__app.route('/v1/chat/completions', methods=['post'])
@__app.route('/api/send/v1/chat/completions', methods=['post'])
def api_send_v1_chat_completions():
    data = request.json  
    last_content = ""
    if 'messages' in data and data['messages']:
        last_message = data['messages'][-1]  
        username = last_message.get('role', 'User')  
        if username == 'user':
            username = 'User'
        last_content = last_message.get('content', 'No content provided')  
    else:
        last_content = 'No messages found'
        username = 'User'

    model = data.get('model', 'fay')
    observation = data.get('observation', '')
    interact = Interact("text", 1, {'user': username, 'msg': last_content, 'observation': observation})
    util.printInfo(3, "文字沟通接口", '{}'.format(interact.data["msg"]), time.time())
    text = fay_booter.feiFei.on_interact(interact)

    if model == 'fay-streaming':
        return stream_response(text)
    else:
        return non_streaming_response(last_content, text)

@__app.route('/api/get-member-list', methods=['post'])
def api_get_Member_list():
    memberdb = member_db.new_instance()
    list = memberdb.get_all_users()
    return json.dumps({'list': list})


@__app.route('/api/get_run_status', methods=['post'])
def api_get_run_status():
    status = fay_booter.is_running()
    return json.dumps({'status': status})

@__app.route('/api/adopt_msg', methods=['POST'])
def adopt_msg():
    data = request.get_json()
    if not data:
        return jsonify({'status':'error', 'msg': '未提供数据'})

    id = data.get('id')

    if not id:
        return jsonify({'status':'error', 'msg': 'id不能为空'})

    info = content_db.new_instance().get_content_by_id(id)
    content = info[3]
    if info is not None:
        previous_info = content_db.new_instance().get_previous_user_message(id)
        previous_content = previous_info[3]
        result = content_db.new_instance().adopted_message(id)
        if result:
            qa_service.QAService().record_qapair(previous_content, content)
            return jsonify({'status': 'success', 'msg': '采纳成功'})
        else:
            return jsonify({'status':'error', 'msg': '采纳失败'})
    else:
        return jsonify({'status':'error', 'msg': '采纳失败'})

def stream_response(text):
    def generate():
        for chunk in text_chunks(text):
            message = {
                "id": "chatcmpl-8jqorq6Fw1Vi5XoH7pddGGpQeuPe0",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "fay-streaming",
                "choices": [
                    {
                        "delta": {
                            "content": chunk
                        },
                        "index": 0,
                        "finish_reason": None
                    }
                ]
            }
            yield f"data: {json.dumps(message)}\n\n"
            time.sleep(0.1)
        # 发送最终的结束信号
        yield 'data: [DONE]\n\n'
    
    return Response(generate(), mimetype='text/event-stream')

def non_streaming_response(last_content, text):
    return jsonify({
        "id": "chatcmpl-8jqorq6Fw1Vi5XoH7pddGGpQeuPe0",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "fay",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text
                },
                "logprobs": "",
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": len(last_content),
            "completion_tokens": len(text),
            "total_tokens": len(last_content) + len(text)
        },
        "system_fingerprint": "fp_04de91a479"
    })

def text_chunks(text, chunk_size=20):
    pattern = r'([^.!?;:，。！？]+[.!?;:，。！？]?)'
    chunks = re.findall(pattern, text)
    for chunk in chunks:
        yield chunk

@__app.route('/', methods=['get'])
@auth.login_required
def home_get():
    return __get_template()


@__app.route('/', methods=['post'])
@auth.login_required
def home_post():
    wsa_server.get_web_instance.add_cmd({"is_connect": wsa_server.get_instance().isConnect}) #TODO 不应放这里，同步数字人连接状态
    return __get_template()

@__app.route('/setting', methods=['get'])
def setting():
    return render_template('setting.html')



#输出的音频http
@__app.route('/audio/<filename>')
def serve_audio(filename):
    audio_file = os.path.join(os.getcwd(), "samples", filename)
    return send_file(audio_file)

#输出的表情git
@__app.route('/robot/<filename>')
def serve_gif(filename):
    gif_file = os.path.join(os.getcwd(), "gui", "robot", filename)
    return send_file(gif_file)

def run():
    server = pywsgi.WSGIServer(('0.0.0.0',5000), __app)
    server.serve_forever()

def start():
    MyThread(target=run).start()

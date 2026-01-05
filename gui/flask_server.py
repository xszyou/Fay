# -*- coding: utf-8 -*-
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
import pytz
import logging
import uuid

import fay_booter
from tts import tts_voice
from gevent import pywsgi
try:
    # Use gevent.sleep to avoid blocking the gevent loop; fallback to time.sleep if unavailable
    from gevent import sleep as gsleep
except Exception:
    from time import sleep as gsleep
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
from core import stream_manager

# 全局变量，用于跟踪当前的genagents服务器
genagents_server = None
genagents_thread = None
monitor_thread = None

__app = Flask(__name__)
# 禁用 Flask 默认日志
__app.logger.disabled = True
log = logging.getLogger('werkzeug')
log.disabled = True
# 禁用请求日志中间件
__app.config['PROPAGATE_EXCEPTIONS'] = True

auth = HTTPBasicAuth()
CORS(__app, supports_credentials=True)

def load_users():
    try:
        with open('verifier.json') as f:
            users = json.load(f)
        return users
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}

users = load_users()

@auth.verify_password
def verify_password(username, password):
    if not users or config_util.start_mode == 'common':
        return True
    if username in users and users[username] == password:
        return username


def __get_template():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Error rendering template: {e}", 500

def __get_device_list():
    try:
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
    except Exception as e:
        print(f"Error getting device list: {e}")
        return []

@__app.route('/api/submit', methods=['post'])
def api_submit():
    data = request.values.get('data')
    if not data:
        return jsonify({'result': 'error', 'message': '未提供数据'})
    try:
        config_data = json.loads(data)
        if 'config' not in config_data:
            return jsonify({'result': 'error', 'message': '数据中缺少config'})

        config_util.load_config()
        existing_config = config_util.config

        def merge_configs(existing, new):
            for key, value in new.items():
                if isinstance(value, dict) and key in existing:
                    if isinstance(existing[key], dict):
                        merge_configs(existing[key], value)
                    else:
                        existing[key] = value
                else:
                    existing[key] = value

        merge_configs(existing_config, config_data['config'])

        config_util.save_config(existing_config)
        config_util.load_config()

        return jsonify({'result': 'successful'})
    except json.JSONDecodeError:
        return jsonify({'result': 'error', 'message': '无效的JSON数据'})
    except Exception as e:
        return jsonify({'result': 'error', 'message': f'保存配置时出错: {e}'}), 500
    



@__app.route('/api/get-data', methods=['post'])
def api_get_data():
    # 获取配置和语音列表
    try:
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
            voice_list = [
                {"id": "BV001_streaming", "name": "通用女声"},
                {"id": "BV002_streaming", "name": "通用男声"},
                {"id": "zh_male_jingqiangkanye_moon_bigtts", "name": "京腔侃爷/Harmony"},
                {"id": "zh_female_shuangkuaisisi_moon_bigtts", "name": "爽快思思/Skye"},
                {"id": "zh_male_wennuanahu_moon_bigtts", "name": "温暖阿虎/Alvin"},
                {"id": "zh_female_wanwanxiaohe_moon_bigtts", "name": "湾湾小何"}
            ]
            send_voice_list = {"voiceList": voice_list}
            wsa_server.get_web_instance().add_cmd(send_voice_list)

        else:
            voice_list = tts_voice.get_voice_list()
            send_voice_list = []
            for voice in voice_list:
                voice_data = voice.value
                send_voice_list.append({"id": voice_data['name'], "name": voice_data['name']})
            wsa_server.get_web_instance().add_cmd({"voiceList": send_voice_list})
            voice_list = send_voice_list
        wsa_server.get_web_instance().add_cmd({"deviceList": __get_device_list()})
        if fay_booter.is_running():
            wsa_server.get_web_instance().add_cmd({"liveState": 1})
        return json.dumps({'config': config_util.config, 'voice_list': voice_list})
    except Exception as e:
        return jsonify({'result': 'error', 'message': f'获取数据时出错: {e}'}), 500

@__app.route('/api/start-live', methods=['post'])
def api_start_live():
    # 启动
    try:
        fay_booter.start()
        gsleep(1)
        wsa_server.get_web_instance().add_cmd({"liveState": 1})
        return '{"result":"successful"}'
    except Exception as e:
        return jsonify({'result': 'error', 'message': f'启动时出错: {e}'}), 500

@__app.route('/api/stop-live', methods=['post'])
def api_stop_live():
    # 停止
    try:
        fay_booter.stop()
        gsleep(1)
        wsa_server.get_web_instance().add_cmd({"liveState": 0})
        return '{"result":"successful"}'
    except Exception as e:
        return jsonify({'result': 'error', 'message': f'停止时出错: {e}'}), 500

@__app.route('/api/send', methods=['post'])
def api_send():
    # 接收前端发送的消息
    data = request.values.get('data')
    if not data:
        return jsonify({'result': 'error', 'message': '未提供数据'})
    try:
        info = json.loads(data)
        username = info.get('username')
        msg = info.get('msg')
        if not username or not msg:
            return jsonify({'result': 'error', 'message': '用户名和消息内容不能为空'})
        msg = msg.strip()
      
        interact = Interact("text", 1, {'user': username, 'msg': msg})
        util.printInfo(1, username, '[文字发送按钮]{}'.format(interact.data["msg"]), time.time())
        fay_booter.feiFei.on_interact(interact)
        return '{"result":"successful"}'
    except json.JSONDecodeError:
        return jsonify({'result': 'error', 'message': '无效的JSON数据'})
    except Exception as e:
        return jsonify({'result': 'error', 'message': f'发送消息时出错: {e}'}), 500

# 获取指定用户的消息记录（支持分页）
@__app.route('/api/get-msg', methods=['post'])
def api_get_Msg():
    try:
        data = request.form.get('data')
        if data is None:
            data = request.get_json()
        else:
            data = json.loads(data)
        uid = member_db.new_instance().find_user(data["username"])
        limit = data.get("limit", 30)  # 默认每页30条
        offset = data.get("offset", 0)  # 默认从0开始
        contentdb = content_db.new_instance()
        if uid == 0:
            return json.dumps({'list': [], 'total': 0, 'hasMore': False})
        else:
            # 获取总数用于判断是否还有更多
            total = contentdb.get_message_count(uid)
            list = contentdb.get_list('all', 'desc', limit, uid, offset)
        relist = []
        i = len(list) - 1
        while i >= 0:
            timezone = pytz.timezone('Asia/Shanghai')
            timetext = datetime.datetime.fromtimestamp(list[i][3], timezone).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            relist.append(dict(type=list[i][0], way=list[i][1], content=list[i][2], createtime=list[i][3], timetext=timetext, username=list[i][5], id=list[i][6], is_adopted=list[i][7]))
            i -= 1
        if fay_booter.is_running():
            wsa_server.get_web_instance().add_cmd({"liveState": 1})
        hasMore = (offset + len(list)) < total
        return json.dumps({'list': relist, 'total': total, 'hasMore': hasMore})
    except json.JSONDecodeError:
        return jsonify({'list': [], 'total': 0, 'hasMore': False, 'message': '无效的JSON数据'})
    except Exception as e:
        return jsonify({'list': [], 'total': 0, 'hasMore': False, 'message': f'获取消息时出错: {e}'}), 500

#文字沟通接口
@__app.route('/v1/chat/completions', methods=['post'])
@__app.route('/api/send/v1/chat/completions', methods=['post'])
def api_send_v1_chat_completions():
    # 处理聊天完成请求
    data = request.get_json()
    if not data:
        return jsonify({'error': '未提供数据'})
    try:
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
        # 检查请求中是否指定了流式传输
        stream_requested = data.get('stream', False)
        if stream_requested or model == 'fay-streaming':
            interact = Interact("text", 1, {'user': username, 'msg': last_content, 'observation': str(observation), 'stream':True})
            util.printInfo(1, username, '[文字沟通接口(流式)]{}'.format(interact.data["msg"]), time.time())
            fay_booter.feiFei.on_interact(interact)
            return gpt_stream_response(last_content, username)
        else:
            interact = Interact("text", 1, {'user': username, 'msg': last_content, 'observation': str(observation), 'stream':False})
            util.printInfo(1, username, '[文字沟通接口(非流式)]{}'.format(interact.data["msg"]), time.time())
            fay_booter.feiFei.on_interact(interact)
            return non_streaming_response(last_content, username)
    except Exception as e:
        return jsonify({'error': f'处理请求时出错: {e}'}), 500

@__app.route('/api/get-member-list', methods=['post'])
def api_get_Member_list():
    # 获取成员列表
    try:
        memberdb = member_db.new_instance()
        list = memberdb.get_all_users()
        return json.dumps({'list': list})
    except Exception as e:
        return jsonify({'list': [], 'message': f'获取成员列表时出错: {e}'}), 500

@__app.route('/api/add-user', methods=['POST'])
def api_add_user():
    """添加新用户"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({'success': False, 'message': '缺少用户名参数'}), 400

        username = data['username'].strip()

        if not username:
            return jsonify({'success': False, 'message': '用户名不能为空'}), 400

        if username == 'User':
            return jsonify({'success': False, 'message': '不能使用保留的用户名 "User"'}), 400

        # 检查用户是否已存在
        memberdb = member_db.new_instance()
        if memberdb.is_username_exist(username) != "notexists":
            return jsonify({'success': False, 'message': '该用户名已存在'}), 400

        # 添加用户
        result = memberdb.add_user(username)
        if result == "success":
            # 获取新用户的 uid
            uid = memberdb.find_user(username)
            return jsonify({
                'success': True,
                'message': f'用户 {username} 已添加',
                'uid': uid
            })
        else:
            return jsonify({'success': False, 'message': result}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': f'添加用户时出错: {e}'}), 500

@__app.route('/api/get-run-status', methods=['post'])
def api_get_run_status():
    # 获取运行状态
    try:
        status = fay_booter.is_running()
        return json.dumps({'status': status})
    except Exception as e:
        return jsonify({'status': False, 'message': f'获取运行状态时出错: {e}'}), 500

@__app.route('/api/delete-user', methods=['POST'])
def api_delete_user():
    """删除用户及其所有数据（聊天记录、记忆文件）"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({'success': False, 'message': '缺少用户名参数'}), 400

        username = data['username']

        # 不允许删除主人账户
        if username == 'User':
            return jsonify({'success': False, 'message': '无法删除主人账户'}), 400

        deleted_msgs = 0
        deleted_memory = False
        deleted_user = False

        # 1. 删除聊天记录（fay.db 中的 T_Msg 和 T_Adopted）
        try:
            deleted_msgs = content_db.new_instance().delete_messages_by_username(username)
        except Exception as e:
            print(f"删除聊天记录时出错: {e}")

        # 2. 删除用户记忆文件目录（如果启用了按用户隔离）
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            mem_base = os.path.join(base_dir, "memory")
            user_memory_dir = os.path.join(mem_base, str(username))

            if os.path.exists(user_memory_dir) and os.path.isdir(user_memory_dir):
                import shutil
                shutil.rmtree(user_memory_dir)
                deleted_memory = True
                print(f"已删除用户记忆目录: {user_memory_dir}")

            # 清除缓存的 agent 对象
            try:
                from llm import nlp_cognitive_stream
                if hasattr(nlp_cognitive_stream, 'agents') and username in nlp_cognitive_stream.agents:
                    del nlp_cognitive_stream.agents[username]
            except Exception:
                pass
        except Exception as e:
            print(f"删除记忆文件时出错: {e}")

        # 3. 从用户表删除用户
        try:
            member_db.new_instance().delete_user(username)
            deleted_user = True
        except Exception as e:
            print(f"删除用户记录时出错: {e}")

        return jsonify({
            'success': True,
            'message': f'用户 {username} 已删除',
            'details': {
                'deleted_messages': deleted_msgs,
                'deleted_memory': deleted_memory,
                'deleted_user': deleted_user
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'删除用户时出错: {e}'}), 500

@__app.route('/api/get-user-extra-info', methods=['POST'])
def api_get_user_extra_info():
    """获取用户补充信息"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({'success': False, 'message': '缺少用户名参数'}), 400

        username = data['username']
        extra_info = member_db.new_instance().get_extra_info(username)
        return jsonify({'success': True, 'extra_info': extra_info})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取补充信息时出错: {e}'}), 500

@__app.route('/api/update-user-extra-info', methods=['POST'])
def api_update_user_extra_info():
    """更新用户补充信息"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({'success': False, 'message': '缺少用户名参数'}), 400

        username = data['username']
        extra_info = data.get('extra_info', '')
        member_db.new_instance().update_extra_info(username, extra_info)
        return jsonify({'success': True, 'message': '补充信息已更新'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新补充信息时出错: {e}'}), 500

@__app.route('/api/get-user-portrait', methods=['POST'])
def api_get_user_portrait():
    """获取用户画像"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({'success': False, 'message': '缺少用户名参数'}), 400

        username = data['username']
        user_portrait = member_db.new_instance().get_user_portrait(username)
        return jsonify({'success': True, 'user_portrait': user_portrait})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取用户画像时出错: {e}'}), 500

@__app.route('/api/update-user-portrait', methods=['POST'])
def api_update_user_portrait():
    """更新用户画像"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({'success': False, 'message': '缺少用户名参数'}), 400

        username = data['username']
        user_portrait = data.get('user_portrait', '')
        member_db.new_instance().update_user_portrait(username, user_portrait)
        return jsonify({'success': True, 'message': '用户画像已更新'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新用户画像时出错: {e}'}), 500

@__app.route('/api/get-system-status', methods=['get'])
def api_get_system_status():
    # 获���系统各组件连接状态
    try:
        username = request.args.get('username')
        server_status = True
        
        # 数字人状态 (HumanServer 10002)
        # 检查指定用户是否连接了数字人端
        digital_human_status = False
        try:
            wsa_instance = wsa_server.get_instance()
            if wsa_instance and username:
                digital_human_status = wsa_instance.is_connected(username)
        except Exception:
            digital_human_status = False
        
        # 远程音频状态 (Socket 10001)
        # 检查指定用户是否连接了远程音频
        remote_audio_status = False
        try:
            if username and hasattr(fay_booter, 'DeviceInputListenerDict'):
                for listener in fay_booter.DeviceInputListenerDict.values():
                    if listener.username == username:
                        remote_audio_status = True
                        break
        except Exception:
            remote_audio_status = False
            
        return jsonify({
            'server': server_status,
            'digital_human': digital_human_status,
            'remote_audio': remote_audio_status
        })
    except Exception as e:
        return jsonify({'server': False, 'digital_human': False, 'remote_audio': False, 'error': str(e)}), 500

@__app.route('/api/get-audio-config', methods=['GET'])
def api_get_audio_config():
    """获取麦克风和扬声器的配置状态"""
    try:
        mic_enabled = config_util.config.get('source', {}).get('record', {}).get('enabled', False)
        speaker_enabled = config_util.config.get('interact', {}).get('playSound', False)

        return jsonify({
            'mic': mic_enabled,
            'speaker': speaker_enabled
        })
    except Exception as e:
        return jsonify({'mic': False, 'speaker': False, 'error': str(e)}), 500

@__app.route('/api/adopt-msg', methods=['POST'])
def adopt_msg():
    # 采纳消息
    data = request.get_json()
    if not data:
        return jsonify({'status':'error', 'msg': '未提供数据'})

    id = data.get('id')

    if not id:
        return jsonify({'status':'error', 'msg': 'id不能为空'})

    if  config_util.config["interact"]["QnA"] == "":
        return jsonify({'status':'error', 'msg': '请先设置Q&A文件'})

    try:
        info = content_db.new_instance().get_content_by_id(id)
        content = info[3] if info else ''
        if info is not None:
            # 过滤掉 think 标签及其内容
            content = re.sub(r'<think>[\s\S]*?</think>', '', content, flags=re.IGNORECASE).strip()
            previous_info = content_db.new_instance().get_previous_user_message(id)
            previous_content = previous_info[3] if previous_info else ''
            result = content_db.new_instance().adopted_message(id)
            if result:
                qa_service.QAService().record_qapair(previous_content, content)
                return jsonify({'status': 'success', 'msg': '采纳成功'})
            else:
                return jsonify({'status':'error', 'msg': '采纳失败'}), 500
        else:
            return jsonify({'status':'error', 'msg': '消息未找到'}), 404
    except Exception as e:
        return jsonify({'status':'error', 'msg': f'采纳消息时出错: {e}'}), 500

@__app.route('/api/unadopt-msg', methods=['POST'])
def unadopt_msg():
    # 取消采纳消息
    data = request.get_json()
    if not data:
        return jsonify({'status':'error', 'msg': '未提供数据'})

    id = data.get('id')

    if not id:
        return jsonify({'status':'error', 'msg': 'id不能为空'})

    try:
        info = content_db.new_instance().get_content_by_id(id)
        if info is None:
            return jsonify({'status':'error', 'msg': '消息未找到'}), 404

        content = info[3]
        # 过滤掉 think 标签及其内容，用于匹配 QA 文件中的答案
        clean_content = re.sub(r'<think>[\s\S]*?</think>', '', content, flags=re.IGNORECASE).strip()

        # 从数据库中删除采纳记录，并获取所有相同内容的消息ID
        success, same_content_ids = content_db.new_instance().unadopt_message(id, clean_content)

        if success:
            # 从 QA 文件中删除对应记录
            qa_service.QAService().remove_qapair(clean_content)
            return jsonify({
                'status': 'success',
                'msg': '取消采纳成功',
                'unadopted_ids': same_content_ids
            })
        else:
            return jsonify({'status':'error', 'msg': '取消采纳失败'}), 500
    except Exception as e:
        return jsonify({'status':'error', 'msg': f'取消采纳时出错: {e}'}), 500

def gpt_stream_response(last_content, username):
    sm = stream_manager.new_instance()
    _, nlp_Stream = sm.get_Stream(username)
    def generate():
        conversation_id = sm.get_conversation_id(username)
        while True:
            sentence = nlp_Stream.read()
            if sentence is None:
                gsleep(0.01)
                continue

            # 跳过非当前会话
            try:
                m = re.search(r"__<cid=([^>]+)>__", sentence)
                producer_cid = m.group(1)
                if producer_cid != conversation_id:
                    continue
                if m:
                    sentence = sentence.replace(m.group(0), "")
            except Exception as e:
                print(e)
            is_first = "_<isfirst>" in sentence
            is_end = "_<isend>" in sentence
            content = sentence.replace("_<isfirst>", "").replace("_<isend>", "").replace("_<isqa>", "")
            # 移除 prestart 标签及其内容，不返回给API调用方
            content = re.sub(r'<prestart>[\s\S]*?</prestart>', '', content, flags=re.IGNORECASE)
            if content or is_first or is_end:  # 只有当有实际内容时才发送
                message = {
                    "id": "faystreaming-" + str(uuid.uuid4()),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "fay-streaming",
                    "choices": [
                        {
                            "delta": {
                                "content": content
                            },
                            "index": 0,
                            "finish_reason": "stop" if is_end else None
                        }
                    ],
                    #TODO 这里的token计算方式需要优化
                    "usage": {
                        "prompt_tokens": len(last_content) if is_first else 0,
                        "completion_tokens": len(content),
                        "total_tokens": len(last_content) + len(content)
                    },
                    "system_fingerprint": ""
                }
                yield f"data: {json.dumps(message)}\n\n"
            if is_end:
                break
            gsleep(0.01)
        yield 'data: [DONE]\n\n'

    return Response(generate(), mimetype='text/event-stream')

# 处理非流式响应
def non_streaming_response(last_content, username):
    sm = stream_manager.new_instance()
    _, nlp_Stream = sm.get_Stream(username)
    text = ""
    conversation_id = sm.get_conversation_id(username)
    while True:
        sentence = nlp_Stream.read()
        if sentence is None:
            gsleep(0.01)
            continue

        # 跳过非当前会话
        try:
            m = re.search(r"__<cid=([^>]+)>__", sentence)
            producer_cid = m.group(1)
            if producer_cid != conversation_id:
                continue
            if m:
                sentence = sentence.replace(m.group(0), "")
        except Exception as e:
            print(e)
        is_first = "_<isfirst>" in sentence
        is_end = "_<isend>" in sentence
        text += sentence.replace("_<isfirst>", "").replace("_<isend>", "").replace("_<isqa>", "")
        if is_end:
            break
    # 移除 prestart 标签及其内容，不返回给API调用方
    text = re.sub(r'<prestart>[\s\S]*?</prestart>', '', text, flags=re.IGNORECASE)
    return jsonify({
        "id": "fay-" + str(uuid.uuid4()),
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
        #TODO 这里的token计算方式需要优化
        "usage": {
            "prompt_tokens": len(last_content),
            "completion_tokens": len(text),
            "total_tokens": len(last_content) + len(text)
        },
        "system_fingerprint": ""
    })

@__app.route('/', methods=['get'])
@auth.login_required
def home_get():
    try:
        return __get_template()
    except Exception as e:
        return f"Error loading home page: {e}", 500

@__app.route('/', methods=['post'])
@auth.login_required
def home_post():
    try:
        return __get_template()
    except Exception as e:
        return f"Error processing request: {e}", 500

@__app.route('/setting', methods=['get'])
def setting():
    try:
        return render_template('setting.html')
    except Exception as e:
        return f"Error loading settings page: {e}", 500

@__app.route('/Page3', methods=['get'])
def Page3():
    try:
        return render_template('Page3.html')
    except Exception as e:
        return f"Error loading settings page: {e}", 500


# 输出的音频http
@__app.route('/audio/<filename>')
def serve_audio(filename):
    audio_file = os.path.join(os.getcwd(), "samples", filename)
    if os.path.exists(audio_file):
        return send_file(audio_file)
    else:
        return jsonify({'error': '文件未找到'}), 404

# 输出的表情gif
@__app.route('/robot/<filename>')
def serve_gif(filename):
    gif_file = os.path.join(os.getcwd(), "gui", "robot", filename)
    if os.path.exists(gif_file):
        return send_file(gif_file)
    else:
        return jsonify({'error': '文件未找到'}), 404

#打招呼
@__app.route('/to-greet', methods=['POST'])
def to_greet():
    data = request.get_json()
    username = data.get('username', 'User')
    observation = data.get('observation', '')
    interact = Interact("hello", 1, {'user': username, 'msg': '按观测要求打个招呼', 'observation': str(observation)})
    text = fay_booter.feiFei.on_interact(interact)
    return jsonify({'status': 'success', 'data': text, 'msg': '已进行打招呼'}), 200 

#唤醒:在普通唤醒模式，进行大屏交互才有意义
@__app.route('/to-wake', methods=['POST'])
def to_wake():
    data = request.get_json()
    username = data.get('username', 'User')
    observation = data.get('observation', '')
    fay_booter.recorderListener.wakeup_matched = True
    return jsonify({'status': 'success', 'msg': '已唤醒'}), 200 

#打断
@__app.route('/to-stop-talking', methods=['POST'])
def to_stop_talking():
    try:
        data = request.get_json()
        username = data.get('username', 'User')
        stream_manager.new_instance().clear_Stream_with_audio(username)

        result = "interrupted"  # 简单的结果标识
        return jsonify({
            'status': 'success',
            'data': str(result) if result is not None else '',
            'msg': f'已停止用户 {username} 的说话'
        }), 200
    except Exception as e:
        username_str = username if 'username' in locals() else 'Unknown'
        util.printInfo(1, username_str, f"打断操作失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'msg': str(e)
        }), 500

#麦克风开关
@__app.route('/api/toggle-microphone', methods=['POST'])
def api_toggle_microphone():
    try:
        data = request.get_json()
        if data and 'enabled' in data:
            enabled = data['enabled']
        else:
            # 如果未提供enabled参数，则切换当前状态
            config_util.load_config()
            enabled = not config_util.config.get('source', {}).get('record', {}).get('enabled', True)

        # 加载并更新配置
        config_util.load_config()
        if 'source' not in config_util.config:
            config_util.config['source'] = {}
        if 'record' not in config_util.config['source']:
            config_util.config['source']['record'] = {}

        config_util.config['source']['record']['enabled'] = enabled
        config_util.save_config(config_util.config)
        config_util.load_config()

        return jsonify({
            'status': 'success',
            'enabled': enabled,
            'msg': f'麦克风已{"开启" if enabled else "关闭"}'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'msg': f'麦克风开关操作失败: {str(e)}'
        }), 500


#消息透传接口
@__app.route('/transparent-pass', methods=['post'])
def transparent_pass():
    try:
        data = request.form.get('data')
        if data is None:
            data = request.get_json()
        else:
            data = json.loads(data)
        username = data.get('user', 'User')
        response_text = data.get('text', None)
        audio_url = data.get('audio', None)
        if response_text or audio_url:
            # 新消息到达，立即中断该用户之前的所有处理（文本流+音频队列）
            util.printInfo(1, username, f'[API中断] 新消息到达，完整中断用户 {username} 之前的所有处理')
            util.printInfo(1, username, f'[API中断] 用户 {username} 的文本流和音频队列已清空，准备处理新消息')
            interact = Interact('transparent_pass', 2, {'user': username, 'text': response_text, 'audio': audio_url, 'isend':True, 'isfirst':True})
            util.printInfo(1, username, '透传播放：{}，{}'.format(response_text, audio_url), time.time())
            success = fay_booter.feiFei.on_interact(interact)
            if (success == 'success'):
                return jsonify({'code': 200, 'message' : '成功'})
        return jsonify({'code': 500, 'message' : '未知原因出错'})
    except Exception as e:
        return jsonify({'code': 500, 'message': f'出错: {e}'}), 500

# 清除记忆API
@__app.route('/api/clear-memory', methods=['POST'])
def api_clear_memory():
    try:
        config_util.load_config()
        success_messages = []
        error_messages = []

        # 1. 清除仿生记忆
        try:
            from llm.nlp_bionicmemory_stream import clear_agent_memory as clear_bionic
            if clear_bionic():
                success_messages.append("仿生记忆")
                util.log(1, "仿生记忆已清除")
            else:
                error_messages.append("清除仿生记忆失败")
        except Exception as e:
            error_messages.append(f"清除仿生记忆时出错: {str(e)}")
            util.log(1, f"清除仿生记忆时出错: {str(e)}")

        # 2. 清除认知记忆（文件系统）
        try:
            memory_dir = os.path.join(os.getcwd(), "memory")

            if os.path.exists(memory_dir):
                # 清空memory目录下的所有文件
                for root, dirs, files in os.walk(memory_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                util.log(1, f"已删除文件: {file_path}")
                        except Exception as e:
                            util.log(1, f"删除文件时出错: {file_path}, 错误: {str(e)}")

                # 创建标记文件，延迟到启动时删除chroma_db（避免文件锁定问题）
                with open(os.path.join(memory_dir, ".memory_cleared"), "w") as f:
                    f.write("Memory has been cleared. Do not save on exit.")

                # 清除内存中的认知记忆
                try:
                    from llm.nlp_cognitive_stream import set_memory_cleared_flag, clear_agent_memory as clear_cognitive
                    set_memory_cleared_flag(True)
                    clear_cognitive()
                    util.log(1, "已同时清除文件存储和内存中的认知记忆")
                except Exception as e:
                    util.log(1, f"清除内存中认知记忆时出错: {str(e)}")

                success_messages.append("认知记忆")
                util.log(1, "认知记忆已清除，ChromaDB数据库将在下次启动时清除")
            else:
                error_messages.append("记忆目录不存在")

        except Exception as e:
            error_messages.append(f"清除认知记忆时出错: {str(e)}")
            util.log(1, f"清除认知记忆时出错: {str(e)}")

        # 返回结果
        if success_messages:
            message = "已清除：" + "、".join(success_messages)
            if error_messages:
                message += "；部分失败：" + "、".join(error_messages)
            message += "，请重启应用使更改生效"
            return jsonify({'success': True, 'message': message}), 200
        else:
            message = "清除失败：" + "、".join(error_messages)
            return jsonify({'success': False, 'message': message}), 500

    except Exception as e:
        util.log(1, f"清除记忆时出错: {str(e)}")
        return jsonify({'success': False, 'message': f'清除记忆时出错: {str(e)}'}), 500

# 启动genagents_flask.py的API
@__app.route('/api/start-genagents', methods=['POST'])
def api_start_genagents():
    try:
        # 检查是否启用了仿生记忆
        config_util.load_config()
        if config_util.config["memory"].get("use_bionic_memory", False):
            return jsonify({
                'success': False,
                'message': '仿生记忆模式下不支持人格克隆功能，请在设置中关闭仿生记忆后重试'
            }), 400

        # 只有在数字人启动后才能克隆人格
        if not fay_booter.is_running():
            return jsonify({'success': False, 'message': 'Fay未启动，无法启动决策分析'}), 400
        
        # 获取克隆要求
        data = request.get_json()
        if not data or 'instruction' not in data:
            return jsonify({'success': False, 'message': '缺少克隆要求参数'}), 400
        
        instruction = data['instruction']
        
        # 保存指令到临时文件，供genagents_flask.py读取
        instruction_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'genagents', 'instruction.json')
        with open(instruction_file, 'w', encoding='utf-8') as f:
            json.dump({'instruction': instruction}, f, ensure_ascii=False)
        
        # 导入genagents_flask模块
        import sys
        sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        from genagents.genagents_flask import start_genagents_server, is_shutdown_requested
        from werkzeug.serving import make_server
        
        # 关闭之前的genagents服务器（如果存在）
        global genagents_server, genagents_thread, monitor_thread
        if genagents_server is not None:
            try:
                # 主动关闭之前的服务器
                util.log(1, "关闭之前的决策分析服务...")
                genagents_server.shutdown()
                # 等待线程结束
                if genagents_thread and genagents_thread.is_alive():
                    genagents_thread.join(timeout=2)
                if monitor_thread and monitor_thread.is_alive():
                    monitor_thread.join(timeout=2)
            except Exception as e:
                util.log(1, f"关闭之前的决策分析服务时出错: {str(e)}")
        
        # 清除之前的记忆，确保只保留最新的决策分析
        try:
            from llm.nlp_cognitive_stream import clear_agent_memory
            util.log(1, "已清除之前的决策分析记忆")
        except Exception as e:
            util.log(1, f"清除之前的决策分析记忆时出错: {str(e)}")
        
        # 启动决策分析服务（不启动单独进程，而是返回Flask应用实例）
        genagents_app = start_genagents_server(instruction_text=instruction)
        
        # 创建服务器
        genagents_server = make_server('0.0.0.0', 5001, genagents_app)
        
        # 在后台线程中启动Flask服务
        import threading
        def run_genagents_app():
            try:
                # 使用serve_forever而不是app.run
                genagents_server.serve_forever()
            except Exception as e:
                util.log(1, f"决策分析服务运行出错: {str(e)}")
            finally:
                util.log(1, f"决策分析服务已关闭")
        
        # 启动监控线程，检查是否需要关闭服务器
        def monitor_shutdown():
            try:
                while not is_shutdown_requested():
                    gsleep(1)
                util.log(1, f"检测到关闭请求，正在关闭决策分析服务...")
                genagents_server.shutdown()
            except Exception as e:
                util.log(1, f"监控决策分析服务时出错: {str(e)}")
        
        # 启动服务器线程
        genagents_thread = threading.Thread(target=run_genagents_app)
        genagents_thread.daemon = True
        genagents_thread.start()
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor_shutdown)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        util.log(1, f"已启动决策分析页面，指令: {instruction}")
        
        # 返回决策分析页面的URL
        return jsonify({
            'success': True, 
            'message': '已启动决策分析页面',
            'url': 'http://127.0.0.1:5001/'
        }), 200
    except Exception as e:
        util.log(1, f"启动决策分析页面时出错: {str(e)}")
        return jsonify({'success': False, 'message': f'启动决策分析页面时出错: {str(e)}'}), 500

# 获取本地图片（用于在网页中显示本地图片）
@__app.route('/api/local-image')
def api_local_image():
    try:
        file_path = request.args.get('path', '')
        if not file_path:
            return jsonify({'error': '缺少文件路径参数'}), 400

        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'error': f'文件不存在: {file_path}'}), 404

        # 检查是否为图片文件
        valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
        if not file_path.lower().endswith(valid_extensions):
            return jsonify({'error': '不是有效的图片文件'}), 400

        # 返回图片文件
        return send_file(file_path)
    except Exception as e:
        return jsonify({'error': f'获取图片时出错: {str(e)}'}), 500

# 打开图片文件（使用系统默认程序）
@__app.route('/api/open-image', methods=['POST'])
def api_open_image():
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'success': False, 'message': '缺少文件路径参数'}), 400

        file_path = data['path']

        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': f'文件不存在: {file_path}'}), 404

        # 检查是否为图片文件
        valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
        if not file_path.lower().endswith(valid_extensions):
            return jsonify({'success': False, 'message': '不是有效的图片文件'}), 400

        # 使用系统默认程序打开图片
        import subprocess
        import platform

        system = platform.system()
        if system == 'Windows':
            os.startfile(file_path)
        elif system == 'Darwin':  # macOS
            subprocess.run(['open', file_path])
        else:  # Linux
            subprocess.run(['xdg-open', file_path])

        return jsonify({'success': True, 'message': '已打开图片'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'打开图片时出错: {str(e)}'}), 500

def run():
    class NullLogHandler:
        def write(self, *args, **kwargs):
            pass
    server = pywsgi.WSGIServer(
        ('0.0.0.0', 5000), 
        __app,
        log=NullLogHandler()  
    )
    server.serve_forever()

def start():
    MyThread(target=run).start()

import gzip
import re
from abc import abstractmethod
import json
import random
import time
from urllib.parse import unquote_plus

import requests
import websocket
import ssl

from douyin import douyin_pb2 as dy

from core.interact import Interact
from scheduler.thread_manager import MyThread
from utils import config_util, util

USER_URL = 'https://www.douyin.com/user/'

interact_datas = []
import json
import time
import ssl
import websocket


running = False
class WS_Client:
    def __init__(self, host, ttwid):
        self.__ws = None
        self.__host = host
        self.__connect(host, ttwid)
        self.__ttwid = ttwid

    def on_message(self, ws, message):
        global interact_datas
        try:
            wss_response = dy.WssResponse()
            wss_response.ParseFromString(message)

            # gzip解压
            origin_bytes = gzip.decompress(wss_response.payload)

            # Response
            response = dy.Response()
            response.ParseFromString(origin_bytes)

            # Ack
            if response.needAck:
                s = dy.WssResponse()
                s.payloadType = "ack"
                s.payload = response.internalExt.encode('utf-8')
                s.logid = wss_response.logid

                ws.send(s.SerializeToString())

            # 获取数据内容 根据不同Method进行解析
            # TODO 丢掉msgId重复的数据
            for item in response.messages:
                # 忘记Python的switch怎么写 先用if
                if item.method == "WebcastChatMessage":
                    chatMessage = dy.ChatMessage()
                    chatMessage.ParseFromString(item.payload)
                    if len(interact_datas) >= 5:
                        interact_datas.pop()
                    interact = Interact("live", 1, {"user": chatMessage.user.nickname,
                                                    "msg": chatMessage.content})
                    interact_datas.append(interact)
                if item.method == "WebcastMemberMessage":
                    memberMessage = dy.MemberMessage()
                    memberMessage.ParseFromString(item.payload)
                    if len(interact_datas) >= 5:
                        interact_datas.pop()
                    interact_datas.append(
                        Interact("live", 2, {"user": memberMessage.user.nickname, "msg": "来了"}))
        except Exception as e:
            pass

    def on_close(self, ws, code, msg):
        pass

    def on_error(self, ws, error):
        util.log(1, f"弹幕监听WebSocket error. Reconnecting...{error}")
        time.sleep(5)
        self.__connect(self.__host, self.__ttwid)

    def on_open(self, ws):
        pass

    def __connect(self, host, ttwid):
        global running
        while running:
            try:
                self.__ws = websocket.WebSocketApp(host,
                                                   header={
                                                       'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
                                                   },
                                                   cookie=f"ttwid={ttwid}",
                                                   on_message=self.on_message,
                                                   on_error=self.on_error,
                                                   on_close=self.on_close)
                self.__ws.on_open = self.on_open
                # self.__ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
                self.__ws.run_forever()
                util.log(1, "弹幕监听WebSocket success.")
                break
            except Exception as e:
                break

    def close(self):
        self.__ws.close()


class Viewer:

    def __init__(self):
        global running
        running = True
        self.live_started = False
        self.dy_msg_ws = None
        self.url = ""

    def __start(self):
        MyThread(target=self.__run_dy_msg_ws).start() #获取抖音监听内容
        self.live_started = True
        MyThread(target=self.__get_package_listen_interact_runnable).start()

    def __run_dy_msg_ws(self):
        room_id, room_title, room_user_count, wss_url, ttwid = self.__fetch_live_room_info()

        self.dy_msg_ws = WS_Client(wss_url, ttwid)

    def __fetch_live_room_info(self):
        res = requests.get(
            url = self.url,
            headers = {
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
            },
            cookies = {
                '__ac_nonce': '0644b01a000d245c5a9c'
            }
        )
        data_string = re.findall(r'<script id="RENDER_DATA" type="application/json">(.*?)</script>', res.text)[0]
        data_dict = json.loads(unquote_plus(data_string))
        room_id = data_dict['app']['initialState']['roomStore']['roomInfo']['roomId']
        room_title = data_dict['app']['initialState']['roomStore']['roomInfo']['room']['title']
        room_user_count = data_dict['app']['initialState']['roomStore']['roomInfo']['room']['user_count_str']
        util.log(1, room_id + room_title + room_user_count)
        wss_url = f"wss://webcast3-ws-web-hl.douyin.com/webcast/im/push/v2/?app_name=douyin_web&version_code=180800&webcast_sdk_version=1.3.0&update_version_code=1.3.0&compress=gzip&internal_ext=internal_src:dim|wss_push_room_id:7225737346073774903|wss_push_did:7199486991779792444|dim_log_id:20230428114337FD4558A3BE4089824C54|fetch_time:1682653417808|seq:1|wss_info:0-1682653417808-0-0|wrds_kvs:WebcastRoomStatsMessage-1682653414545125398_InputPanelComponentSyncData-1682652587177966081_WebcastRoomRankMessage-1682653312579024233&cursor=d-1_u-1_h-1_t-1682653417808_r-1&host=https://live.douyin.com&aid=6383&live_id=1&did_rule=3&debug=false&maxCacheMessageNumber=20&endpoint=live_pc&support_wrds=1&im_path=/webcast/im/fetch/&user_unique_id=7199486991779792444&device_platform=web&cookie_enabled=true&screen_width=1920&screen_height=1200&browser_language=zh-CN&browser_platform=MacIntel&browser_name=Mozilla&browser_version=5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2010_15_7)%20AppleWebKit/537.36%20(KHTML,%20like%20Gecko)%20Chrome/112.0.0.0%20Safari/537.36&browser_online=true&tz_name=Asia/Shanghai&identity=audience&room_id={room_id}&heartbeatDuration=0&signature=WM5ae8YShx2AojG0"
        util.log(1, wss_url)
        ttwid = res.cookies.get_dict()['ttwid']
        return room_id, room_title, room_user_count, wss_url, ttwid


    def start(self,url):
        self.url = url
        MyThread(target=self.__start).start()

    def is_live_started(self):
        return self.live_started

    
    #Add by xszyou on 20230412.通过抓包监测互动数据
    def __get_package_listen_interact_runnable(self):
        global interact_datas
        global running
        while running:
            if not self.live_started:
                continue
            
            for interact in interact_datas:
                MyThread(target=self.on_interact, args=[interact, time.time()]).start()
            interact_datas.clear()

    def stop(self):
        global running
        running = False
        if self.dy_msg_ws:
            self.dy_msg_ws.close()
            self.dy_msg_ws = None
            
    
    @abstractmethod
    def on_interact(self, interact, event_time):
        pass

    @abstractmethod
    def on_change_state(self, is_live_started):
        pass

import json
import time

from ws4py.client.threadedclient import WebSocketClient
import base64
import hashlib
import uuid
from utils import config_util as cfg

base_url = "ws://wsapi.xfyun.cn/v1/aiui"

end_tag = "--end--"


# qa 通讯类
class __WSClient(WebSocketClient):
    q_msg = ''
    a_msg = ''

    def opened(self):
        pass

    def closed(self, code, reason=None):
        # if code == 1000:
        #     print("qa close")
        # else:
        #     print("连接异常关闭，code：" + str(code) + " ，reason：" + str(reason))
        return

    def received_message(self, m):

        s = json.loads(str(m))

        if s['action'] == "started":

            # 输入内容并发送
            str_content = self.q_msg
            self.send(bytes(str_content.encode('utf-8')))
            time.sleep(0.04)

            # 数据发送结束之后发送结束标识
            self.send(bytes(end_tag.encode("utf-8")))

        elif s['action'] == "result":
            data = s['data']
            # with open('qa/out.txt', 'w') as file:
            #     file.write(str(data))
            if data['sub'] == "iat":
                print("user: ", data["text"])
            elif data['sub'] == "nlp":
                intent = data['intent']
                if intent['rc'] == 0:
                    self.a_msg = intent['answer']['text']
                else:
                    self.a_msg = "我没有理解你说的话啊"
            elif data['sub'] == "tts":
                # TODO 播报pcm音频
                print('tts')
                pass
        elif s['action'] == "error":
            print('[NLP错误] ' + s['desc'])
        else:
            print(s)


def __get_auth_id():
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return hashlib.md5(":".join([mac[e:e + 2] for e in range(0, 11, 2)]).encode("utf-8")).hexdigest()


def question(text):
    ws = None
    try:
        # 构造握手参数
        curTime = int(time.time())

        auth_id = __get_auth_id()

        param = """{{
            "auth_id": "{0}",
            "data_type": "text",
            "scene": "main_box",
            "ver_type": "monitor",
            "close_delay": "200",
            "ent":"xtts",
            "vcn":"x_xiaoyan",
            "speed":"50",
            "interact_mode":"continuous",
            "context": "{{\\\"sdk_support\\\":[\\\"iat\\\",\\\"nlp\\\",\\\"tts\\\"]}}"
        }}"""

        param = param.format(auth_id).encode(encoding="utf-8")
        paramBase64 = base64.b64encode(param).decode()
        checkSumPre = cfg.key_xf_aiui_api_key + str(curTime) + paramBase64
        checksum = hashlib.md5(checkSumPre.encode("utf-8")).hexdigest()
        connParam = "?appid=" + cfg.key_xf_aiui_app_id + "&checksum=" + checksum + "&param=" + paramBase64 + "&curtime=" + str(curTime) + "&signtype=md5"

        ws = __WSClient(base_url + connParam, protocols=['chat'], headers=[("Origin", "https://wsapi.xfyun.cn")])
        ws.q_msg = text
        ws.connect()
        ws.run_forever()

    except KeyboardInterrupt:
        if ws is not None:
            ws.close()

    return ws.a_msg

import json
import requests
from utils import util
from core.authorize_tb import Authorize_Tb
import os

def question(cont, uid=0, observation=""):
    bigmodel = BigModel()
    answer = bigmodel.question(cont, uid)
    return answer

class BigModel:

    def __init__(self):

        #服务地址：https://open.bigmodel.cn/
        self.api_key = ""#填写对应的api_key
        self.app_id = ""#写对应的智能体id

        self.authorize_tb = Authorize_Tb()
        self.conversation_file = "cache_data/bigmodel_conversation_data.json"

    def question(self, cont, uid):
        self.userid = uid
        conversation_id = self.__get_conversation_id()
        if not conversation_id:
            conversation_id = self.__create_conversation()
            if conversation_id:
                self.__store_conversation_id(conversation_id)
            else:
                return "网络异常，开了个小差，请稍后再问。"

        request_id = self.__send_message(conversation_id, cont)
        if not request_id:
            return "网络异常，开了个小差，请稍后再问。"

        answer = self.__get_response(request_id)
        return answer

    def __get_conversation_id(self):
        if os.path.exists(self.conversation_file):
            with open(self.conversation_file, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}
                return data.get(str(self.userid))
        return None

    def __store_conversation_id(self, conversation_id):
        data = {}
        # 如果文件存在，读取内容
        if os.path.exists(self.conversation_file):
            with open(self.conversation_file, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}
        # 如果文件不存在，data则为{}

        # 更新/新增当前userid的conversation_id
        data[str(self.userid)] = conversation_id

        # 写回文件
        with open(self.conversation_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def __create_conversation(self):
        url = f"https://open.bigmodel.cn/api/llm-application/open/v2/application/{self.app_id}/conversation"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(url, headers=headers)
            if response.status_code != 200:
                util.log(1, f"创建会话失败: {response.text}")
                return None
            data = response.json()
            if data['code'] != 200:
                util.log(1, f"创建会话失败: {data['message']}")
                return None
            return data['data']['conversation_id']
        except Exception as e:
            util.log(1, f"创建会话异常: {str(e)}")
            return None

    def __send_message(self, conversation_id, message):
        url = "https://open.bigmodel.cn/api/llm-application/open/v2/application/generate_request_id"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            "app_id": self.app_id,
            "conversation_id": conversation_id,
            "key_value_pairs": [
                {
                    "id": "user",
                    "type": "input",
                    "name": "用户提问",
                    "value": message
                }
            ]
        }
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            if response.status_code != 200:
                util.log(1, f"发送消息失败: {response.text}")
                return None
            data = response.json()
            if data['code'] != 200:
                util.log(1, f"发送消息失败: {data['message']}")
                return None
            return data['data']['id']
        except Exception as e:
            util.log(1, f"发送消息异常: {str(e)}")
            return None

    def __get_response(self, request_id):
        url = f"https://open.bigmodel.cn/api/llm-application/open/v2/model-api/{request_id}/sse-invoke"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'text/event-stream'
        }
        try:
            with requests.post(url, headers=headers, stream=True, timeout=60) as response:
                if response.status_code != 200:
                    util.log(1, f"获取响应失败: {response.text}")
                    return "网络异常，开了个小差，请稍后再问。"
                answer = []
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data:"):
                            data_str = decoded_line.replace("data:", "").strip()
                            if data_str:
                                try:
                                    data_json = json.loads(data_str)
                                    if 'usage' in data_json:
                                        break
                                    if 'msg' in data_json:
                                        msg = data_json['msg'].replace('#', '').replace('*', '')
                                        answer.append(msg)
                                       
                                except json.JSONDecodeError as je:
                                    util.log(1, f"JSON解析错误: {str(je)}")

                return ''.join(answer) if answer else "网络异常，开了个小差，请稍后再问。"
        except requests.exceptions.Timeout:
            util.log(1, "获取响应超时。")
            return "网络异常，开了个小差，请稍后再问。"
        except Exception as e:
            util.log(1, f"获取响应异常: {str(e)}")
            return "网络异常，开了个小差，请稍后再问。"

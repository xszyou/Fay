import requests
import json
from utils import util
from utils import config_util as cfg

def question(cont, communication_history=[], username="user"):
    if username == "":
        username = "user"
    message = []
    if len(communication_history) > 1:
        for info in communication_history[:-1]:
            answer_info = dict()
            if info['role'] == "user":
                answer_info["role"] = "user"
                answer_info["type"] = "query"
                answer_info["content"] = info['content']
                answer_info["content_type"] = "text"
            elif info['role'] == "bot":
                answer_info["role"] = "assistant"
                answer_info["type"] = "answer"
                answer_info["content"] = info['content']
                answer_info["content_type"] = "text"
            message.append(answer_info)
    api_url = 'https://api.coze.cn/open_api/v2/chat'
    headers = {
        'Authorization': "Bearer "+cfg.coze_api_key,
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'Host': 'api.coze.cn',
        'Connection': 'keep-alive'
    }
    data = {
        "bot_id": cfg.coze_bot_id,
        "user": username,
        "query": cont,
        "stream": False,
        "chat_history": message
    }
    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(data))
        
        if response.status_code == 200:
            response_json = response.json()
            if response_json.get('code', 0) == 0:
                for message in response_json.get('messages', []):
                    if message.get('type') == 'answer':
                        return message.get('content')
            else:
                util.log(1, f"调用失败，请检查配置错误 {response_json.get('msg', '')}")
                response_text = "抱歉，我现在太忙了，休息一会，请稍后再试。"
                return response_text
        else:
            util.log(1, f"调用失败，请检查配置")
            response_text = "抱歉，我现在太忙了，休息一会，请稍后再试。"
            return response_text
    except Exception as e:
        util.log(1, f"调用失败，请检查配置（错误：{e}）")
        response_text = "抱歉，我现在太忙了，休息一会，请稍后再试。"
        return response_text
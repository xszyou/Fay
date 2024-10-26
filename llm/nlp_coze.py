
import requests
import json
from utils import util
from utils import config_util as cfg
from core import content_db

def question(cont, uid=0):
    contentdb = content_db.new_instance()
    if uid == 0:
        communication_history = contentdb.get_list('all','desc', 11)
    else:
        communication_history = contentdb.get_list('all','desc', 11, uid)
    message = []
    i = len(communication_history) - 1

    if len(communication_history)>1:
        while i >= 0:
            answer_info = dict()
            if communication_history[i][0] == "member":
                answer_info["role"] = "user"
                answer_info["type"] = "query"
                answer_info["content"] = communication_history[i][2]
                answer_info["content_type"] = "text"
            elif communication_history[i][0] == "fay":
                answer_info["role"] = "assistant"
                answer_info["type"] = "answer"
                answer_info["content"] = communication_history[i][2]
                answer_info["content_type"] = "text"
            message.append(answer_info)
            i -= 1

    message.append({
                "role": "user",
                "content": cont,
                "content_type": "text"
            })
    url = "https://api.coze.cn/v3/chat"
    payload = json.dumps({
        "bot_id": cfg.coze_bot_id,
        "user_id": f"{uid}",
        "stream": True,
        "auto_save_history": True,
        "additional_messages": message
    })
    headers = {
        'Authorization': f"Bearer {cfg.coze_api_key}",
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, data=payload, stream=True)

    if response.status_code == 200:
        response_text = ""
        start = False
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')  
                if line == "event:conversation.message.completed":
                    start = True
                if line == "event:done":
                    return response_text 
                if start and line.startswith('data:'):
                    json_str = line[5:]  
                    try:
                        event_data = json.loads(json_str)
                        if event_data.get('type') == 'answer':
                            response_text = event_data.get('content', '')
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e}")
                        continue
    else:
        print(f"调用失败，状态码：{response.status_code}")
        return "抱歉，我现在太忙了，休息一会，请稍后再试。"


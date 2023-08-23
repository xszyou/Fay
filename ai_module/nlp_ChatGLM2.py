import json
import requests
from core.content_db import Content_Db
content_db = Content_Db()
list = content_db.get_list('all','desc',10)
answer_info = dict()
chat_list = []
for val in list:
    answer_info = dict()
    if val[0] == "member":
        answer_info["role"] = "user"
        answer_info["content"] = val[2]
    elif val[0] == "fay":
        answer_info["role"] = "bot"
        answer_info["content"] = val[2]
    chat_list.append(answer_info)

def question(cont):
    print(chat_list)
    content = {
        "prompt":"请简单回复我。" +  cont,
        "history":chat_list}
    url = "http://192.168.1.23:8000"
    req = json.dumps(content)
    headers = {'content-type': 'application/json'}
    r = requests.post(url, headers=headers, data=req)
    res = json.loads(r.text).get('response')
    return res


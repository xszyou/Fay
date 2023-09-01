import json
import requests
from core.content_db import Content_Db


def question(cont):
    content_db = Content_Db()
    list = content_db.get_list('all','desc',11)
    answer_info = dict()
    chat_list = []
    i = len(list)-1
    while i >= 0:
        answer_info = dict()
        if list[i][0] == "member":
            answer_info["role"] = "user"
            answer_info["content"] = list[i][2]
        elif list[i][0] == "fay":
            answer_info["role"] = "bot"
            answer_info["content"] = list[i][2]
        chat_list.append(answer_info)
        i -= 1
    content = {
        "prompt":"请简单回复我。" +  cont,
        "history":chat_list}
    url = "http://127.0.0.1:8000"
    req = json.dumps(content)
    headers = {'content-type': 'application/json'}
    r = requests.post(url, headers=headers, data=req)
    res = json.loads(r.text).get('response')
    return res


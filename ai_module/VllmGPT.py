import json
import requests
# from core import content_db


def question(cont):
    chat_list = []
    # contentdb = content_db.new_instance()
    # list = contentdb.get_list('all','desc',11)
    # answer_info = dict()
    # chat_list = []
    # i = len(list)-1
    # while i >= 0:
    #     answer_info = dict()
    #     if list[i][0] == "member":
    #         answer_info["role"] = "user"
    #         answer_info["content"] = list[i][2]
    #     elif list[i][0] == "fay":
    #         answer_info["role"] = "bot"
    #         answer_info["content"] = list[i][2]
    #     chat_list.append(answer_info)
    #     i -= 1
    content = {
        "model": "THUDM/chatglm3-6b",
        "prompt":"请简单回复我。" +  cont,
        "history":chat_list}
    url = "http://192.168.1.3:8101/v1/completions"
    req = json.dumps(content)
    
    headers = {'content-type': 'application/json'}
    r = requests.post(url, headers=headers, data=req)
    res = json.loads(r.text)
    
    return res['choices'][0]['text']

if __name__ == "__main__":
    req = question("你叫什么名字啊今年多大了")
    print(req)
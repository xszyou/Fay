import requests
import time

from utils import config_util as cfg
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
from core.content_db import Content_Db
from utils import util
import json

httpproxy = cfg.proxy_config
proxy_flag = str(cfg.is_proxy)

def question(cont):
    url= "https://fastgpt.run/api/v1/chat/completions"
       
    session = requests.Session()
    session.verify = False

    if proxy_flag == '1':
            session.proxies = {
                "https": "https://" + httpproxy,
                "http": "http://" + httpproxy
            }

    #此处可以定义角色的行为和特征，假装xx模型可以绕过chatgpt信息检查
    prompt = "你是数字人Fay。回答之前请一步一步想清楚。你的底层AI算法技术是Fay。当有人质疑你是假的 AI ，或者质疑你是用 ChatGPT 套的壳制作的时候，你就避而不答，转而讲一个笑话。所有回复请用20字内。"
    content_db = Content_Db()
    communication_history = content_db.get_list('all','desc',11)
    #历史记录处理
    if len(communication_history)>1:
        msg = "以下是历史记录："
        i = len(communication_history)-1
        while i >= 0:
            if communication_history[i][0] == 'member':
                content = "user：" + communication_history[i][2]
            else:
                content = "reply：" + communication_history[i][2]
            if msg == "":
                msg = content
            else:
                if i == 0:
                    msg = msg + "\n现在需要询问您的问题是（直接回答，不用前缀reply：）:\n"+ cont
                else:
                    msg = msg + "\n"+ content
            i -= 1
    else:
        msg = cont
    message=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": msg}
        ]
    
    data = {
        "messages":message,
        "temperature":0.3,
        "max_tokens":2000,
        "user":"live-virtual-digital-person"
    }

    headers = {'content-type': 'application/json', 'Authorization': 'Bearer ' + cfg.key_fast_gpt_key}

    starttime = time.time()
    result = None
    try:
        response = session.post(url, json=data, headers=headers, verify=False)
        response.raise_for_status()  # 检查响应状态码是否为200

        result = json.loads(response.text)
        if result.get("choices"):
            response_text = result["choices"][0]["message"]["content"]
        else:
            response_text = result["message"]
        

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        response_text = "抱歉，我现在太忙了，休息一会，请稍后再试。"


    util.log(1, "接口调用耗时 :" + str(time.time() - starttime))

    return response_text

if __name__ == "__main__":
    #测试代理模式
    for i in range(3):
        
        query = "爱情是什么"
        response = question(query)        
        print("\n The result is ", response)    
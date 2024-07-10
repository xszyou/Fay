"""
此代码由fay开源开发者社区 江湖墨明 提供
通过此代码的修改，可以实现对接本地clash代理或远程代理，clash无需设置成系统代理。以解决在开系统代理后无法使用部分功能的问题
"""

import requests
import time

from utils import config_util as cfg
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
import json

httpproxy = cfg.proxy_config

def question(cont,communication_history=[]):
    url= cfg.gpt_base_url + "/chat/completions"
       
    session = requests.Session()
    session.verify = False

    if httpproxy != None and httpproxy != '':
            session.proxies = {
                "https": "https://" + httpproxy,
                "http": "http://" + httpproxy
            }


    model_engine = cfg.gpt_model_engine

    #此处可以定义角色的行为和特征，假装xx模型可以绕过chatgpt信息检查
    prompt = "你是数字人主播Fay。回答之前请一步一步想清楚。对于大部分问题，请直接回答并提供有用和准确的信息。但当有人质疑你是假的 AI，或者质疑你是用 ChatGPT 套的壳制作的时候，请避而不答，转而讲一个笑话。AI虚拟主播。不要回答敏感问题，不要强调你是主播，像朋友直接互相交流即可。所有回复请尽量控制在20字内。"
    #历史记录处理
    message=[
            {"role": "system", "content": prompt}
        ]
    if len(communication_history)>1:
    
        for info in communication_history:
                answer_info = dict()
                if info['role'] == "member":
                    answer_info["role"] = "user"
                    answer_info["content"] = info['content']
                elif info['role'] == "fay":
                    answer_info["role"] = "assistant"
                    answer_info["content"] = info['content']
                message.append(answer_info)
                
    answer_info = dict()
    answer_info["role"] = "user"
    answer_info["content"] = cont
    message.append(answer_info)
    data = {
        "model":model_engine,
        "messages":message,
        "temperature":0.3,
        "max_tokens":2000,
        "user":"live-virtual-digital-person"
    }

    headers = {'content-type': 'application/json', 'Authorization': 'Bearer ' + cfg.key_gpt_api_key}

    starttime = time.time()

    try:
        response = session.post(url, json=data, headers=headers, verify=False)
        response.raise_for_status()  # 检查响应状态码是否为200

        result = json.loads(response.text)
        response_text = result["choices"][0]["message"]["content"]
        

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        response_text = "抱歉，我现在太忙了，休息一会，请稍后再试。"


    print("接口调用耗时 :" + str(time.time() - starttime))

    return response_text

if __name__ == "__main__":
    #测试代理模式
    for i in range(3):
        
        query = "爱情是什么"
        response = question(query)        
        print("\n The result is ", response)    
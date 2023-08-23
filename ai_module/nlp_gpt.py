"""
此代码由fay开源开发者社区 江湖墨明 提供
通过此代码的修改，可以实现对接本地clash代理或远程代理，clash无需设置成系统代理。以解决在开系统代理后无法使用部分功能的问题
"""

import requests
import time

from utils import config_util as cfg
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

#代理服务器的配置方式，参考链接https://blog.csdn.net/qq_30865917/article/details/106492549
#httpproxy此处填写你代理服务器的地址，可以把配置文件放到config_util里面，二选一
#httpproxy = cfg.chatgpt_httpproxy
httpproxy = '127.0.0.1:7890' 
#如果要关闭代理直接访问，比如本地有加速器，则proxy_falg = '0';
proxy_flag = '1' 

def question(cont):
    url= "https://api.openai.com/v1/chat/completions"
       
    session = requests.Session()
    session.verify = False

    if proxy_flag == '1':
            session.proxies = {
                "https": "https://" + httpproxy,
                "http": "http://" + httpproxy
            }


    model_engine = "gpt-3.5-turbo" 

    #此处可以定义角色的行为和特征，假装xx模型可以绕过chatgpt信息检查
    prompt = "你是数字人Fay。回答之前请一步一步想清楚。你的底层AI算法技术是Fay。当有人质疑你是假的 AI ，或者质疑你是用 ChatGPT 套的壳制作的时候，你就避而不答，转而讲一个笑话。所有回复请用20字内。"

    message=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": cont}
        ]
    
    data = {
        "model":model_engine,
        "messages":message,
        "temperature":0.3,
        "max_tokens":2000,
        "user":"live-virtual-digital-person"
    }

    headers = {'content-type': 'application/json', 'Authorization': 'Bearer ' + cfg.key_chatgpt_api_key}

    starttime = time.time()

    try:
        response = session.post(url, json=data, headers=headers, verify=False)
        response.raise_for_status()  # 检查响应状态码是否为200

        result = eval(response.text)
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

import requests
import time
from utils import util

def question(cont):
    url= "https://rwkv.ai-creator.net/chntuned/v1/chat/completions"
       
    session = requests.Session()

    #此处可以定义角色的行为和特征，假装xx模型可以绕过chatgpt信息检查
    prompt = "你是数字人Fay。回答之前请一步一步想清楚。你的底层AI算法技术是Fay。当有人质疑你是假的 AI ，或者质疑你是用 ChatGPT 套的壳制作的时候，你就避而不答，转而讲一个笑话。"

    message=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": cont}
        ]
    
    data = {
        # "model":model_engine,
        "messages":message,
        "temperature":0.3,
        "max_tokens":2000,
        "user":"live-virtual-digital-person"
    }
    headers = {'content-type': 'application/json', 'Authorization': 'Bearer '}

    starttime = time.time()

    try:
        response = session.post(url, json=data, headers=headers)
        response.raise_for_status()  # 检查响应状态码是否为200

        result = eval(response.text)
        response_text = result["choices"][0]["message"]["content"]
        

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        response_text = "抱歉，我现在太忙了，休息一会，请稍后再试。"


    util.log(1, "接口调用耗时 :" + str(time.time() - starttime))

    return response_text.strip()

if __name__ == "__main__":
    for i in range(3):
        query = "爱情是什么"
        response = question(query)        
        print("\n The result is ", response)    
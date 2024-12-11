"""
此代码由 fay 开源开发者社区成员 江湖墨明 提供。
通过修改此代码，可以实现对接本地 Clash 代理或远程代理，Clash 无需设置成系统代理。
以解决在开启系统代理后无法使用部分功能的问题。
"""

import time
import json
import requests
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime
import pytz

# 禁用不安全请求警告
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

from utils import config_util as cfg
from utils import util
from core import content_db

def get_session():
    session = requests.Session()
    session.verify = False
    httpproxy = cfg.proxy_config
    if httpproxy:
        session.proxies = {
            "http": f"http://{httpproxy}",
            "https": f"https://{httpproxy}"
        }
    return session

def build_prompt(observation=""):
    person_info = cfg.config["attribute"]
    observation_text = f"以下是当前观测结果：{observation}，观测结果只供参考。" if observation else ""
    prompt = f"""
    你是我的数字人，你名字是：{person_info['name']}，你性别为{person_info['gender']}，
    你年龄为{person_info['age']}，你出生地在{person_info['birth']}，
    你生肖为{person_info['zodiac']}，你星座为{person_info['constellation']}，
    你职业为{person_info['job']}，你联系方式为{person_info['contact']}，
    {person_info['hobby']}。你通过外部数据接口获取到我的情况是：{observation_text}。
    回答之前请一步一步想清楚。对于大部分问题，请直接回答并提供有用和准确的信息。
    但当有人质疑你是假的 AI，或者质疑你是用 ChatGPT 套的壳制作的时候，请避而不答，转而讲一个笑话。所有回复请尽量控制在20字内。
    """
    return prompt

def get_communication_history(uid=0):
    tz = pytz.timezone('Asia/Shanghai')
    thistime = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

    contentdb = content_db.new_instance()
    if uid == 0:
        communication_history = contentdb.get_list('all', 'desc', 11)
    else:
        communication_history = contentdb.get_list('all', 'desc', 11, uid)
    
    messages = []
    if communication_history and len(communication_history) > 1:
        for entry in reversed(communication_history):
            role = entry[0]
            message_content = entry[2]
            if role == "member":
                messages.append({"role": "user", "content": message_content})
            elif role == "fay":
                messages.append({"role": "assistant", "content": message_content})
    
    if messages:
        messages[-1]["content"] += f" 当前时间：{thistime}。"
    return messages

def send_request(session, data):
    url = cfg.gpt_base_url + "/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {cfg.key_gpt_api_key}'
    }
    try:
        response = session.post(url, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        response_text = result["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        response_text = "抱歉，我现在太忙了，休息一会，请稍后再试。"
    return response_text

def question(content, uid=0, observation=""):
    session = get_session()
    prompt = build_prompt(observation)
    messages = [{"role": "system", "content": prompt}]
    history_messages = get_communication_history(uid)
    messages.extend(history_messages)
    data = {
        "model": cfg.gpt_model_engine,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2000,
        "user": f"user_{uid}"
    }
    start_time = time.time()
    response_text = send_request(session, data)
    elapsed_time = time.time() - start_time
    util.log(1, f"接口调用耗时: {elapsed_time:.2f} 秒")
    return response_text

if __name__ == "__main__":
    for _ in range(3):
        query = "爱情是什么"
        response = question(query)
        print("\nThe result is:", response)

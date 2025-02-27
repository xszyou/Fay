import time
import json
import requests
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime
import pytz
from core import stream_manager

# 禁用不安全请求警告
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

from utils import config_util as cfg
from utils import util
from core import content_db

def get_session():
    """
    获取 HTTP 会话，并设置代理（如果有的话）。
    """
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
    """
    构建对话场景里的 system 提示信息。
    """
    person_info = cfg.config["attribute"]
    observation_text = (
        f"以下是当前观测结果：{observation}，观测结果只供参考。"
        if observation else ""
    )
    prompt = f"""你是我的数字人，你名字是：{person_info['name']}，你性别为{person_info['gender']}，
    你年龄为{person_info['age']}，你出生地在{person_info['birth']}，
    你生肖为{person_info['zodiac']}，你星座为{person_info['constellation']}，
    你职业为{person_info['job']}，你联系方式为{person_info['contact']}，
    {person_info['additional']}。你通过外部数据接口获取到我的情况是：{observation_text}。
    回答之前请一步一步想清楚。对于大部分问题，请直接回答并提供有用和准确的信息。
    但当有人质疑你是假的 AI，或者质疑你是用 ChatGPT 套的壳制作的时候，请避而不答，转而讲一个笑话。所有回复请尽量控制在20字内。
    """
    return prompt

def get_communication_history(uid=0):
    """
    从数据库中获取最近的对话历史，以便在对话时带入上下文。
    """
    tz = pytz.timezone('Asia/Shanghai')
    _ = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

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

    return messages

def send_request_stream(session, data, uid, cache):
    url = cfg.gpt_base_url + "/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {cfg.key_gpt_api_key}'
    }

    # 开启流式传输
    data["stream"] = True
    
    try:
        response = session.post(url, json=data, headers=headers, stream=True)
        response.raise_for_status()

        full_response_text = ""
        accumulated_text = ""
        punctuation_marks = ["。", "！", "？", ".", "!", "?", "\n"]  
        for raw_line in response.iter_lines(decode_unicode=False):
            line = raw_line.decode('utf-8', errors='ignore')
            if not line or line.strip() == "":
                continue

            if line.startswith("data: "):
                chunk = line[len("data: "):].strip()
                try:
                    json_data = json.loads(chunk)
                    finish_reason = json_data["choices"][0].get("finish_reason")
                    if finish_reason is not None:
                        if finish_reason == "stop":
                            if accumulated_text:
                                stream_manager.new_instance().write_sentence(uid, accumulated_text)
                            break
                    
                    flush_text = json_data["choices"][0]["delta"].get("content", "")
                    accumulated_text += flush_text
                    
                    for mark in punctuation_marks:
                        if mark in accumulated_text:
                            last_punct_pos = max(accumulated_text.rfind(p) for p in punctuation_marks if p in accumulated_text)
                            if last_punct_pos != -1:
                                to_write = accumulated_text[:last_punct_pos + 1]
                                accumulated_text = accumulated_text[last_punct_pos + 1:]
                                stream_manager.new_instance().write_sentence(uid, to_write)
                            break

                    full_response_text += flush_text
                except json.JSONDecodeError:
                    continue

        return full_response_text

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        stream_manager.new_instance().write_sentence(uid, "抱歉，我现在太忙了，休息一会，请稍后再试。")
        return "抱歉，我现在太忙了，休息一会，请稍后再试。"

def question(content, uid=0, observation="", cache=None):
    session = get_session()
    prompt = build_prompt(observation)
    
    messages = [{"role": "system", "content": prompt}]
    history_messages = get_communication_history(uid)
    messages.extend(history_messages)

    messages.append({"role": "user", "content": content})

    data = {
        "model": cfg.gpt_model_engine,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2000,
        "user": f"user_{uid}"
    }
    
    start_time = time.time()
    response_text = send_request_stream(session, data, uid, cache)
    elapsed_time = time.time() - start_time

    util.log(1, f"接口调用耗时: {elapsed_time:.2f} 秒")

    return response_text

if __name__ == "__main__":
    # 测试示例
    for _ in range(3):
        query = "爱情是什么"
        resp = question(query)
        print("\nThe streaming result is:", resp)

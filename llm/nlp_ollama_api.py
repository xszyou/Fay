import json
import requests
import time 
from utils import config_util as cfg
from utils import util
from core import content_db
def question(cont, uid=0, observation=""):

    contentdb = content_db.new_instance()
    if uid == 0:
        communication_history = contentdb.get_list('all','desc', 11)
    else:
        communication_history = contentdb.get_list('all','desc', 11, uid)

    person_info = cfg.config["attribute"]
    observation_text = ""
    if observation != "":
        observation_text = f"以下是当前观测结果：{observation}，观测结果只供参考。"
    #此处可以定义角色的行为和特征，假装xx模型可以绕过chatgpt信息检查
    prompt = f"""
    你是数字人：{person_info['name']}，你性别为{person_info['gender']}，
    你年龄为{person_info['age']}，你出生地在{person_info['birth']}，
    你生肖为{person_info['zodiac']}，你星座为{person_info['constellation']}，
    你职业为{person_info['job']}，你联系方式为{person_info['contact']}，
    你喜好为{person_info['hobby']}。{observation_text}
    回答之前请一步一步想清楚。对于大部分问题，请直接回答并提供有用和准确的信息。
    请尽量以可阅读的方式回复，所有回复请尽量控制在20字内。
    """    
    #历史记录处理
    message=[
            {"role": "system", "content": prompt}
        ]
    i = len(communication_history) - 1
    
    if len(communication_history)>1:
        while i >= 0:
            answer_info = dict()
            if communication_history[i][0] == "member":
                answer_info["role"] = "user"
                answer_info["content"] = communication_history[i][2]
            elif communication_history[i][0] == "fay":
                answer_info["role"] = "assistant"
                answer_info["content"] = communication_history[i][2]
            message.append(answer_info)
            i -= 1
    else:
         answer_info = dict()
         answer_info["role"] = "user"
         answer_info["content"] = cont
         message.append(answer_info)
    url=f"http://{cfg.ollama_ip}:11434/api/chat"
    req = json.dumps({
        "model": cfg.ollama_model,
        "messages": message, 
        "stream": False
        })
    headers = {'content-type': 'application/json'}
    session = requests.Session()    
    starttime = time.time()
     
    try:
        response = session.post(url, data=req, headers=headers)
        response.raise_for_status()  # 检查响应状态码是否为200

        result = json.loads(response.text)
        response_text = result["message"]["content"]
        
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
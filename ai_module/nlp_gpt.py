from revChatGPT.V3 import Chatbot
from utils import config_util as cfg
import time 

count = 0
def question(cont):
    global count
    try:
        chatbot = Chatbot(model = "gpt-3.5", proxy = cfg.proxy_config, api_key = cfg.key_chatgpt_api_key)
        response = chatbot.ask(cont)
        count = 0
        return response
    except Exception as e:
        count += 1
        if count < 3:
            time.sleep(15)
            return question(cont)
        return 'gpt当前繁忙，请稍后重试' + e

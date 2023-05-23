from revChatGPT.V1 import Chatbot
from core.content_db import Content_Db
from utils import config_util as cfg

def question(cont):
    try:
        chatbot = Chatbot(config={
            "access_token": cfg.key_gpt_access_token,
            "paid": False,
            "collect_analytics": True,
            "conversation_id":cfg.key_gpt_conversation_id
            },conversation_id=cfg.key_gpt_conversation_id,
            parent_id=None)

        prompt = cont
        response = ""
        for data in chatbot.ask(prompt):
            response = data["message"]
        return response
    except:
        return 'gpt当前繁忙，请稍后重试'

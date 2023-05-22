from revChatGPT.V1 import Chatbot
from core.content_db import Content_Db
from utils import config_util as cfg

def question(cont):
    contentdb = Content_Db()
    list = contentdb.get_list('all','desc',5)
    text = ''
    if len(list) > 0:
        relist = []
        i = len(list)-1
        text = '以下是我和机器人的历史对话：'
        while i >= 0:
            if list[i][0] == 'fay':
                text =  text + ' 机器人：' + list[i][2]
            else:
                text =  text + ' 我：' + list[i][2]
            i -= 1

    try:
        chatbot = Chatbot(config={
        "access_token": cfg.key_gpt_access_token,
        "paid": False,
        "collect_analytics": True,
        "conversation_id":cfg.key_gpt_conversation_id
        },conversation_id=cfg.key_gpt_conversation_id,
        parent_id=None)

        prompt = text + ' 现在想咨询的问题是：'+cont
        response = ""
        for data in chatbot.ask(
        prompt
        ):
            response = data["message"]
        return response
    except:
        return 'gpt当前繁忙，请稍后重试'

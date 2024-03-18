from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
import os
from utils import config_util as cfg

def question(cont):
    os.environ['OPENAI_API_KEY'] = cfg.key_chatgpt_api_key
    llm = ChatOpenAI(model="gpt-4-0125-preview", openai_api_base=cfg.gpt_base_url)
    conversation = ConversationChain(
        llm=llm, 
        verbose=True, 
        memory=ConversationBufferMemory()
    )
    result = conversation.predict(input=cont)
    return result

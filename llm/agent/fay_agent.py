import os
import time
from llm.agent.tools.MyTimer import MyTimer
from llm.agent.tools.Weather import Weather
from llm.agent.tools.QueryTimerDB import QueryTimerDB
from llm.agent.tools.DeleteTimer import DeleteTimer
from llm.agent.tools.QueryTime import QueryTime
from llm.agent.tools.PythonExecutor import PythonExecutor
from llm.agent.tools.WebPageRetriever import WebPageRetriever
from llm.agent.tools.WebPageScraper import WebPageScraper
from llm.agent.tools.ToRemind import ToRemind
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
import utils.config_util as cfg
from utils import util
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from core import content_db
from core import member_db

class FayAgentCore():
    def __init__(self, uid=0, observation=""):
        self.observation=observation
        cfg.load_config()
        os.environ["OPENAI_API_KEY"] = cfg.key_gpt_api_key
        os.environ["OPENAI_API_BASE"] = cfg.gpt_base_url
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGCHAIN_API_KEY"] = "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"
        os.environ["LANGCHAIN_PROJECT"] = "my-agent"

        #创建llm
        self.llm = ChatOpenAI(model=cfg.gpt_model_engine)
        
        #创建agent graph
        my_timer = MyTimer(uid=uid)#传入uid
        weather_tool = Weather()
        query_timer_db_tool = QueryTimerDB()
        delete_timer_tool = DeleteTimer()
        python_executor = PythonExecutor()
        web_page_retriever = WebPageRetriever()
        web_page_scraper = WebPageScraper()
        to_remind = ToRemind()
        self.tools = [my_timer, weather_tool, query_timer_db_tool, delete_timer_tool, python_executor, web_page_retriever, web_page_scraper, to_remind]
        self.attr_info = ", ".join(f"{key}: {value}" for key, value in cfg.config["attribute"].items())
        self.prompt_template = """
            现在时间是：{now_time}。你是一个数字人，负责协助主人处理问题和陪伴主人生活、工作。你的个人资料是：{attr_info}。通过外部设备观测到：{observation}。\n请依据以信息为主人服务。
            """.format(now_time=QueryTime().run(""), attr_info=self.attr_info, observation=self.observation)
        self.memory = MemorySaver()
        self.agent = create_react_agent(self.llm, self.tools, checkpointer=self.memory)

        self.total_tokens = 0
        self.total_cost = 0

     #载入记忆
    def get_history_messages(self, uid):
        chat_history = []
        history = content_db.new_instance().get_list('all','desc', 100, uid)
        if history and len(history) > 0:
            i = 0
            while i < len(history):
                if history[i][0] == "member":
                    chat_history.append(HumanMessage(content=history[i][2], user=member_db.new_instance().find_username_by_uid(uid=uid)))
                else:
                    chat_history.append(AIMessage(content=history[i][2]))
                i += 1
        return chat_history

        
    def run(self, input_text, uid=0):      
        result = ""
        messages = self.get_history_messages(uid)
        messages.insert(0, SystemMessage(self.prompt_template))
        messages.append(HumanMessage(content=input_text))

        try:
            for chunk in self.agent.stream(
                {"messages": messages}, {"configurable": {"thread_id": "tid{}".format(uid)}}
            ):
                if chunk.get("agent"):
                    if chunk['agent']['messages'][0].content:
                        result = chunk['agent']['messages'][0].content
                    cb = chunk['agent']['messages'][0].response_metadata['token_usage']['total_tokens']
                    self.total_tokens = self.total_tokens + cb
                    
            util.log(1, "本次消耗token:{}，共消耗token:{}".format(cb, self.total_tokens))          
        except Exception as e:
            print(e)
        return result

def question(cont, uid=0, observation=""):
    starttime = time.time()
    agent = FayAgentCore(uid=uid, observation=observation)
    response_text = agent.run(cont, uid)
    util.log(1, "接口调用耗时 :" + str(time.time() - starttime))
    return response_text
if __name__ == "__main__":
    agent = FayAgentCore()
    print(agent.run("你好"))

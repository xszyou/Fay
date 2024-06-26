import os
import math

from agent.tools.MyTimer import MyTimer
from agent.tools.Weather import Weather
from agent.tools.QueryTimerDB import QueryTimerDB
from agent.tools.DeleteTimer import DeleteTimer
from agent.tools.QueryTime import QueryTime
from agent.tools.PythonExecutor import PythonExecutor
from agent.tools.WebPageRetriever import WebPageRetriever
from agent.tools.WebPageScraper import WebPageScraper
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent, Tool
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import ChatOpenAI

from langchain_community.callbacks import get_openai_callback

import utils.config_util as utils
from utils import util


class FayAgentCore():
    def __init__(self):
        utils.load_config()
        if str(utils.tavily_api_key) != '':
            os.environ["TAVILY_API_KEY"] = utils.tavily_api_key
        os.environ["OPENAI_API_KEY"] = utils.key_gpt_api_key
        os.environ["OPENAI_API_BASE"] = utils.gpt_base_url
        #创建llm
        self.llm = ChatOpenAI(model=utils.gpt_model_engine)
        # 保存基本信息到记忆
        utils.load_config()
        #内存保存聊天历史
        self.chat_history = []

        #创建agent chain
        my_timer = MyTimer()
        weather_tool = Weather()
        query_timer_db_tool = QueryTimerDB()
        delete_timer_tool = DeleteTimer()
        python_executor = PythonExecutor()
        web_page_retriever = WebPageRetriever()
        web_page_scraper = WebPageScraper()

        
        self.tools = [
            Tool(
                name=python_executor.name,
                func=python_executor.run,
                description=python_executor.description
            ),
            Tool(
                name=my_timer.name,
                func=my_timer.run,
                description=my_timer.description
            ),
            Tool(
                name=weather_tool.name,
                func=weather_tool.run,
                description=weather_tool.description
            ),
            Tool(
                name=query_timer_db_tool.name,
                func=query_timer_db_tool.run,
                description=query_timer_db_tool.description
            ),
            Tool(
                name=delete_timer_tool.name,
                func=delete_timer_tool.run,
                description=delete_timer_tool.description
            ),
            Tool(
                name=web_page_retriever.name,
                func=web_page_retriever.run,
                description=web_page_retriever.description
            ),
            Tool(
                name=web_page_scraper.name,
                func=web_page_scraper.run,
                description=web_page_scraper.description
            )
        ]
        if str(utils.tavily_api_key) != '':
            self.tools.append(TavilySearchResults(max_results=1))
        prompt = hub.pull("hwchase17/react")
        #agent用于执行任务
        agent = create_react_agent(self.llm, self.tools, prompt)

        # 通过传入agent和tools来创建一个agent executor
        self.agent = AgentExecutor(agent=agent,tools=self.tools, verbose=True, handle_parsing_errors=True)
        self.total_tokens = 0
        self.total_cost = 0


     #记忆prompt
    def format_history_str(self, history_list):
        attr_info = ", ".join(f"{key}: {value}" for key, value in utils.config["attribute"].items())
        result = """
        Human: 现在时间是：{now_time}。你是一个智慧农业系统中的AI，负责协助主人打理农作物和陪伴主人生活、工作。请依据以下信息为主人服务。
        """.format( now_time=QueryTime().run(""))
        result += "Human: 我的基本信息是?\nAI: {attr_info}\n".format(attr_info=attr_info)
        for history in history_list:
            result += "Human: {input}\nAI: {output}\n".format(input=history['input'], output=history['output'])
        return result

    
    def run(self, input_text):      
        result = ""
        history = ""
        history = self.format_history_str(self.chat_history)
        try:
            input_text = input_text.replace('主人语音说了：', '').replace('主人文字说了：', '')
           
            with get_openai_callback() as cb:
                # result = self.agent.run(agent_prompt)
                result = self.agent.invoke({"input": input_text,"chat_history": history})
                re = result['output']
                self.total_tokens = self.total_tokens + cb.total_tokens
                self.total_cost = self.total_cost + cb.total_cost
                util.log(1, "本次消耗token:{}， Cost (USD):{}，共消耗token:{}， Cost (USD):{}".format(cb.total_tokens, cb.total_cost, self.total_tokens, self.total_cost))
                    
        except Exception as e:
            print(e)
        
        re = "执行完毕" if re is None or re == "N/A" else re
        chat_text = re

        #保存到记忆流和聊天对话
        self.chat_history.append(result)
        if len(self.chat_history) > 5:
            self.chat_history.pop(0)

        return False, chat_text

if __name__ == "__main__":
    agent = FayAgentCore()
    print(agent.run("你好"))

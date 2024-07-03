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

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage

from core import content_db

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
        if int(utils.max_history_num) >0:
            old_history = content_db.new_instance().get_list('all','desc', int(utils.max_history_num))
            i = len(old_history) - 1
            if len(old_history)>1:
                while i >= 0:
                    if old_history[i][0] == "member":
                        self.chat_history.append(HumanMessage(content=old_history[i][2]))
                    else:
                        self.chat_history.append(AIMessage(content=old_history[i][2]))
                    i -= 1
            else:
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

        attr_info = ", ".join(f"{key}: {value}" for key, value in utils.config["attribute"].items())

        prompt_template = """
        现在时间是：{now_time}。你是一个数字人Fay,负责协助主人处理问题和陪伴主人生活、工作。你的基本信息是：{attr_info}\n请依据以下信息为主人服务。
        """.format( now_time=QueryTime().run(""), attr_info=attr_info)
        prompt_template += """
       回复请尽量使用中文,除非主人特别要求。数字人Fay在能够协助处理广泛的任务，从回答简单问题到提供深入的解释和讨论各种主题。作为语言模型，能够根据接收到的输入生成类似人类的文本，使其能够进行自然对话并提供连贯且与所讨论主题相关的响应。\n\n
并且不断学习和改进，其能力也在不断发展。它能够处理和理解大量文本，并利用这些知识对广泛的问题提供准确和信息丰富的响应。此外，还能根据接收到的输入生成自己的文本，从而参与讨论并提供关于各种主题的解释和描述。\n\n
总体而言，数字人Fay是一个强大的工具，可以帮助处理各种任务，并在广泛的主题上提供有价值的见解和信息。无论您需要帮助特定问题还是只想就某一特定主题进行对话，都在这里提供帮助。\n\n
       TOOLS:\n
       ------\n\n
       Assistant has access to the following tools:
       \n\n{tools}\n\n
       To use a tool, please use the following format, you MUST use the format strictly, ensuring no fields are omitted:
       \n\n```\n
       Thought: Do I need to use a tool? Yes\n
       Action: the action to take, should be one of [{tool_names}]\n
       Action Input: the input to the action\n
       Observation: the result of the action\n
       ```\n\n
       When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format strictly, ensuring no fields are omitted:\n\n
       ```\n
       Thought: Do I need to use a tool? No\n
       Final Answer: [your response here]\n```\n\n
       Begin!Let's think step by step. Take a deep breath.\n\n
       Previous conversation history:\n
       {chat_history}\n\n
       New input: {input}\n
       {agent_scratchpad}
            """
        prompt = ChatPromptTemplate.from_template(prompt_template)
        #agent用于执行任务
        agent = create_react_agent(self.llm, self.tools, prompt)

        # 通过传入agent和tools来创建一个agent executor
        self.agent = AgentExecutor(agent=agent,tools=self.tools, verbose=True, handle_parsing_errors=True)
        self.total_tokens = 0
        self.total_cost = 0


     #记忆
    def set_history(self, result):
            if(len(self.chat_history)>= int(utils.max_history_num)):
                del self.chat_history[0]
                del self.chat_history[0]
            if result:
                if isinstance(result, dict):
                    self.chat_history.append(HumanMessage(content=result['input']))
                    self.chat_history.append(AIMessage(content=result['output']))

        

    
    def run(self, input_text):      
        result = ""
        re = ""
        try:
            input_text = input_text.replace('主人语音说了：', '').replace('主人文字说了：', '')
           
            with get_openai_callback() as cb:
                # result = self.agent.run(agent_prompt)
                result = self.agent.invoke({"input": input_text, "chat_history": self.chat_history})
                re = "执行完毕" if re is None or re == "N/A" else result['output']
                self.total_tokens = self.total_tokens + cb.total_tokens
                self.total_cost = self.total_cost + cb.total_cost
                util.log(1, "本次消耗token:{}， Cost (USD):{}，共消耗token:{}， Cost (USD):{}".format(cb.total_tokens, cb.total_cost, self.total_tokens, self.total_cost))
                    
        except Exception as e:
            print(e)
        
        chat_text = re

        #保存聊天对话
        if int(utils.max_history_num) >0:
            self.set_history(result)
        

        return False, chat_text

if __name__ == "__main__":
    agent = FayAgentCore()
    print(agent.run("你好"))

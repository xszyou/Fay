from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.memory import VectorStoreRetrieverMemory
import faiss
from langchain.docstore import InMemoryDocstore
from langchain.vectorstores import FAISS
from langchain.agents import AgentExecutor, Tool, ZeroShotAgent, initialize_agent
from langchain.chains import LLMChain

from agent.tools.MyTimer import MyTimer
from agent.tools.QueryTime import QueryTime
from agent.tools.Weather import Weather
from agent.tools.Calculator import Calculator
from agent.tools.CheckSensor import CheckSensor
from agent.tools.Switch import Switch
from agent.tools.Knowledge import Knowledge
from agent.tools.Say import Say
from agent.tools.QueryTimerDB import QueryTimerDB


class FayAgentCore():
    def __init__(self):

        #使用open ai embedding
        embedding_size = 1536  # OpenAIEmbeddings 的维度
        index = faiss.IndexFlatL2(embedding_size)
        embedding_fn = OpenAIEmbeddings()

        #创建llm
        llm = ChatOpenAI(model="gpt-4-1106-preview")

        #创建向量数据库
        vectorstore = FAISS(embedding_fn, index, InMemoryDocstore({}), {})

        # 创建记忆
        retriever = vectorstore.as_retriever(search_kwargs=dict(k=2))
        memory = VectorStoreRetrieverMemory(memory_key="chat_history", retriever=retriever)

        # 保存对话内容到记忆
        memory.save_context({"Human": "你知道我在那里吗?"}, {"ai": "广州市"})

        #创建agent chain
        my_timer = MyTimer()
        query_time_tool = QueryTime()
        weather_tool = Weather()
        calculator_tool = Calculator()
        check_sensor_tool = CheckSensor()
        switch_tool = Switch()
        knowledge_tool = Knowledge()
        say_tool = Say()
        query_timer_db_tool = QueryTimerDB()
        tools = [
            Tool(
                name=my_timer.name,
                func=my_timer.run,
                description=my_timer.description
            ),
            Tool(
                name=query_time_tool.name,
                func=query_time_tool.run,
                description=query_time_tool.description
            ),
            Tool(
                name=weather_tool.name,
                func=weather_tool.run,
                description=weather_tool.description
            ),
            Tool(
                name=calculator_tool.name,
                func=calculator_tool.run,
                description=calculator_tool.description
            ),
            Tool(
                name=check_sensor_tool.name,
                func=check_sensor_tool.run,
                description=check_sensor_tool.description
            ),
            Tool(
                name=switch_tool.name,
                func=switch_tool.run,
                description=switch_tool.description
            ),
            Tool(
                name=knowledge_tool.name,
                func=knowledge_tool.run,
                description=knowledge_tool.description
            ),
            Tool(
                name=say_tool.name,
                func=say_tool.run,
                description=say_tool.description
            ),
            Tool(
                name=query_timer_db_tool.name,
                func=query_timer_db_tool.run,
                description=query_timer_db_tool.description
            ),
            
        ]
        prefix = """你是运行在一个智慧农业实验箱的ai数字人，你叫Fay,你的主要作用是，陪伴主人生活、工作，以及协助主人打理好农业种植箱里的农作物. 农业箱内设备会通过一套不成熟的iotm系统自动管理。你可以调用以下工具来完成工作，若缺少必要的工具也请告诉我。所有回复请使用中文，遇到需要提醒的问题也告诉我。若你感觉是我在和你交流请语音回复我。若你需要计算一个新的时间请先获取当前时间。"""
        suffix = """Begin!"

        {chat_history}
        Question: {input}
        {agent_scratchpad}"""

        prompt = ZeroShotAgent.create_prompt(
            tools,
            prefix=prefix,
            suffix=suffix,
            input_variables=["input", "chat_history", "agent_scratchpad"],
        )
        llm_chain = LLMChain(llm=llm, prompt=prompt,  verbose=True)
        agent = ZeroShotAgent(llm_chain=llm_chain, tools=tools, verbose=True)
        # agent = initialize_agent(agent="chat-conversational-react-description",
        #                          tools=tools, llm=llm, verbose=True, 
        #                          max_iterations=3, early_stopping_method="generate", memory=memory, handle_parsing_errors=True)
        self.agent_chain = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=tools, verbose=True, memory=memory, handle_parsing_errors=True
        )

    def run(self, input_text):
        return self.agent_chain.run(input_text)

if __name__ == "__main__":
    agent = FayAgentCore()
    print(agent.run("你好"))

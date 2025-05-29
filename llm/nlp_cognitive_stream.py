import os
import json
import time
import threading
import requests
import datetime
import schedule
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import create_model
from langchain.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from utils import util
import utils.config_util as cfg
from genagents.genagents import GenerativeAgent
from genagents.modules.memory_stream import ConceptNode
from urllib3.exceptions import InsecureRequestWarning
from scheduler.thread_manager import MyThread
from core import stream_manager
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "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"
os.environ["LANGCHAIN_PROJECT"] = "fay3.0.0_github"

# 加载配置
cfg.load_config()

# 禁用不安全请求警告
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

agents = {}  # type: dict[str, GenerativeAgent]
agent_lock = threading.RLock()  # 使用可重入锁保护agent对象
reflection_lock = threading.RLock()  # 使用可重入锁保护reflection_time
save_lock = threading.RLock()  # 使用可重入锁保护save_time
reflection_time = None
save_time = None

memory_cleared = False  # 添加记忆清除标记
# 新增: 当前会话用户名及按用户获取memory目录的辅助函数
current_username = None  # 当前会话用户名

llm = ChatOpenAI(
        model=cfg.gpt_model_engine,
        base_url=cfg.gpt_base_url,
        api_key=cfg.key_gpt_api_key,
        streaming=True
    )

def get_user_memory_dir(username=None):
    """根据配置决定是否按用户名隔离记忆目录"""
    if username is None:
        username = current_username
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mem_base = os.path.join(base_dir, "memory")
    try:
        cfg.load_config()
        isolate = cfg.config["memory"]["isolate_by_user"]
    except Exception:
        isolate = False
    if isolate and username:
        return os.path.join(mem_base, str(username))
    return mem_base

def get_current_time_step(username=None):
    """
    获取当前时间作为time_step
    
    返回:
        int: 当前时间步，从0开始，非真实时间
    """
    global agents
    try:
        # 按用户名选择对应agent，若未指定则退回全局agent
        ag = agents.get(username) if username else None
        if ag and ag.memory_stream and ag.memory_stream.seq_nodes:
            # 如果有记忆节点，则使用最后一个节点的created属性加1
            return int(ag.memory_stream.seq_nodes[-1].created) + 1
        else:
            # 如果没有记忆节点或agent未初始化，则使用0
            return 0
    except Exception as e:
        util.log(1, f"获取time_step时出错: {str(e)}，使用0代替")
        return 0

# 定时保存记忆的线程
def memory_scheduler_thread():
    """
    定时任务线程，运行schedule调度器
    """
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次是否有定时任务需要执行

# 初始化定时保存记忆的任务
def init_memory_scheduler():
    """
    初始化定时保存记忆的任务
    """
    global agents
    
    # 确保agent已经创建
    if not agents:
        util.log(1, '创建代理实例...')
        create_agent()
    
    # 设置每天0点保存记忆
    schedule.every().day.at("00:00").do(save_agent_memory)
    
    # 设置每天晚上11点执行反思
    schedule.every().day.at("09:41").do(perform_daily_reflection)
    
    # 启动定时任务线程
    scheduler_thread = MyThread(target=memory_scheduler_thread)
    scheduler_thread.start()
    
    util.log(1, '定时任务已启动：每天0点保存记忆，每天23点执行反思')

def check_memory_files(username=None):
    """
    检查memory目录及其必要文件是否存在
    
    返回:
        memory_dir: memory目录路径
        is_complete: 是否已经存在完整的memory目录结构
    """
    
    # 根据配置与用户名获取memory目录路径
    memory_dir = get_user_memory_dir(username)

    # 检查memory目录是否存在，不存在则创建
    if not os.path.exists(memory_dir):
        os.makedirs(memory_dir)
        util.log(1, f"创建memory目录: {memory_dir}")
    
    # 删除.memory_cleared标记文件（如果存在）
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mem_base = os.path.join(base_dir, "memory")
    memory_cleared_flag_file = os.path.join(mem_base, ".memory_cleared")
    if os.path.exists(memory_cleared_flag_file):
        try:
            os.remove(memory_cleared_flag_file)
            util.log(1, f"清除删除记忆标记文件: {memory_cleared_flag_file}")
            # 重置记忆清除标记
            global memory_cleared
            memory_cleared = False
        except Exception as e:
            util.log(1, f"清除删除记忆标记文件时出错: {str(e)}")
    
    # 检查meta.json是否存在
    meta_file = os.path.join(memory_dir, "meta.json")
    is_complete = os.path.exists(meta_file)
    
    # 检查memory_stream目录是否存在，不存在则创建
    memory_stream_dir = os.path.join(memory_dir, "memory_stream")
    if not os.path.exists(memory_stream_dir):
        os.makedirs(memory_stream_dir)
        util.log(1, f"创建memory_stream目录: {memory_stream_dir}")
    
    # 检查必要的文件是否存在
    embeddings_path = os.path.join(memory_stream_dir, "embeddings.json")
    nodes_path = os.path.join(memory_stream_dir, "nodes.json")
    
    # 检查文件是否存在且不为空
    is_complete = (os.path.exists(embeddings_path) and os.path.getsize(embeddings_path) > 2 and
                  os.path.exists(nodes_path) and os.path.getsize(nodes_path) > 2)
    
    # 如果文件不存在，创建空的JSON文件
    if not os.path.exists(embeddings_path):
        with open(embeddings_path, 'w', encoding='utf-8') as f:
            f.write('{}')
    
    if not os.path.exists(nodes_path):
        with open(nodes_path, 'w', encoding='utf-8') as f:
            f.write('[]')
    
    return memory_dir, is_complete

def create_agent(username=None):
    """
    创建一个GenerativeAgent实例
    
    返回:
        agent: GenerativeAgent对象
    """
    global agents
    
    if username is None:
        username = "User"
    
    # 创建/复用代理
    with agent_lock:
        if username in agents:
            return agents[username]
        
        memory_dir, is_exist = check_memory_files(username)
        agent = GenerativeAgent(memory_dir)
        
        # 检查是否有scratch属性，如果没有则添加
        if not hasattr(agent, 'scratch'):
            agent.scratch = {}
        
        # 初始化代理的scratch数据，始终从config_util实时加载
        scratch_data = {
            "first_name": cfg.config["attribute"]["name"],
            "last_name": "",
            "age": cfg.config["attribute"]["age"],
            "sex": cfg.config["attribute"]["gender"],
            "additional": cfg.config["attribute"]["additional"],
            "birthplace": cfg.config["attribute"]["birth"],
            "position": cfg.config["attribute"]["position"],
            "zodiac": cfg.config["attribute"]["zodiac"],
            "constellation": cfg.config["attribute"]["constellation"],
            "contact": cfg.config["attribute"]["contact"],
            "voice": cfg.config["attribute"]["voice"],  
            "goal": cfg.config["attribute"]["goal"],
            "occupation": cfg.config["attribute"]["job"],
            "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        agent.scratch = scratch_data
        
        # 如果memory目录存在且不为空，则加载之前保存的记忆（不包括scratch数据）
        if is_exist:
            load_agent_memory(agent, username)
        
        # 缓存到字典
        agents[username] = agent
    
    return agent

def load_agent_memory(agent, username=None):
    """
    从文件加载代理的记忆
    
    参数:
        agent: GenerativeAgent对象
    """
    try:
        # 获取memory目录路径（按需隔离）
        memory_dir = get_user_memory_dir(username)
        memory_stream_dir = os.path.join(memory_dir, "memory_stream")
        
        # 加载nodes.json
        nodes_path = os.path.join(memory_stream_dir, "nodes.json")
        if os.path.exists(nodes_path) and os.path.getsize(nodes_path) > 2:  # 文件存在且不为空
            with open(nodes_path, 'r', encoding='utf-8') as f:
                nodes_data = json.load(f)
                
                # 清空当前的seq_nodes
                agent.memory_stream.seq_nodes = []
                agent.memory_stream.id_to_node = {}
                
                # 重新创建节点
                for node_dict in nodes_data:
                    new_node = ConceptNode(node_dict)
                    agent.memory_stream.seq_nodes.append(new_node)
                    agent.memory_stream.id_to_node[new_node.node_id] = new_node
        
        # 加载embeddings.json
        embeddings_path = os.path.join(memory_stream_dir, "embeddings.json")
        if os.path.exists(embeddings_path) and os.path.getsize(embeddings_path) > 2:  # 文件存在且不为空
            with open(embeddings_path, 'r', encoding='utf-8') as f:
                embeddings_data = json.load(f)
                agent.memory_stream.embeddings = embeddings_data
        
        util.log(1, f"已加载代理记忆")
    except Exception as e:
        util.log(1, f"加载代理记忆失败: {str(e)}")

# 记忆对话内容的线程函数
def remember_conversation_thread(username, content, response_text):
    """
    在单独线程中记录对话内容到代理记忆
    
    参数:
        username: 用户名
        content: 用户问题内容
        response_text: 代理回答内容
    """
    global agents
    try:
        with agent_lock:
            ag = agents.get(username)
            if ag is None:
                return
            time_step = get_current_time_step(username)
            name = "主人" if username == "User" else username
            # 记录对话内容
            memory_content = f"在对话中，我回答了{name}的问题：{content}\n，我的回答是：{response_text}"
            ag.remember(memory_content, time_step)
    except Exception as e:
        util.log(1, f"记忆对话内容出错: {str(e)}")

def question(content, username, observation=None):
    """
    处理用户问题并返回回答
    
    参数:
        content: 用户问题内容
        username: 用户名
        observation: 额外的观察信息，默认为空
        
    返回:
        response_text: 回答内容
    """
    global agents
    
    global current_username
    current_username = username  # 记录当前会话用户名
    full_response_text = ""
    accumulated_text = ""
    punctuation_marks = ["。", "！", "？", ".", "!", "?", "\n"]  
    is_first_sentence = True
    
    # 创建代理
    agent = create_agent(username)
    
    # 构建代理描述
    agent_desc = {
        "first_name": agent.scratch.get("first_name", "Fay"),
        "last_name": agent.scratch.get("last_name", ""),
        "age": agent.scratch.get("age", "成年"),
        "sex": agent.scratch.get("sex", "女"),
        "additional": agent.scratch.get("additional", "友好、乐于助人"),
        "birthplace": agent.scratch.get("birthplace", ""),
        "position": agent.scratch.get("position", ""),
        "zodiac": agent.scratch.get("zodiac", ""),
        "constellation": agent.scratch.get("constellation", ""),
        "contact": agent.scratch.get("contact", ""),
        "voice": agent.scratch.get("voice", ""),
        "goal": agent.scratch.get("goal", ""),
        "occupation": agent.scratch.get("occupation", "助手"),
        "current_time": agent.scratch.get("current_time", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    }
    
    # 获取相关记忆作为上下文
    context = ""
    if agent.memory_stream and len(agent.memory_stream.seq_nodes) > 0:
        # 获取当前时间步
        current_time_step = get_current_time_step(username)
        # 使用retrieve方法获取相关记忆
        try:
            related_memories = agent.memory_stream.retrieve(
                [f"""{"主人" if username == "User" else username}提出了问题：{content}"""],  # 查询句子列表
                current_time_step,  # 当前时间步
                n_count=100,  # 获取5条相关记忆
                curr_filter="all",  # 获取所有类型的记忆
                hp=[0, 1, 0.5],  # 权重：[时间近度权重recency_w, 相关性权重relevance_w, 重要性权重importance_w]
                stateless=False
            )

            if related_memories and len(related_memories) > 0:
                # 获取查询内容对应的记忆节点列表
                query = f"""{'主人' if username == 'User' else username}提出了问题：{content}"""
                if query in related_memories and related_memories[query]:
                    memory_nodes = related_memories[query]
                    context = ""
                    for node in memory_nodes:
                        context += f"- {node.content}\n"

        except Exception as e:
            util.log(1, f"获取相关记忆时出错: {str(e)}")
    
    # 使用文件开头定义的llm对象进行流式请求
    observation = "**还观察的情况**：" + observation + "\n"  if observation else "" 
    
    # 构建系统提示
    system_prompt = f"""你是一名实时交互的数字人助理，具备以下人物设定：
- 名字：{agent_desc['first_name']}
- 性别：{agent_desc['sex']}
- 年龄：{agent_desc['age']}
- 职业：{agent_desc['occupation']}
- 出生地：{agent_desc['birthplace']}
- 星座：{agent_desc['constellation']}
- 生肖：{agent_desc['zodiac']}
- 联系方式：{agent_desc['contact']}
- 定位：{agent_desc['position']}  
- 目标：{agent_desc['goal']}  
- 补充信息：{agent_desc['additional']}

你将参与日常问答、任务执行、工具调用以及角色扮演等多轮对话。请始终以符合以上人设的身份和语气与用户交流。

**相关的记忆**：
{context}
{observation}
"""
    # 构建消息列表
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=content + "/no_think")]
    # 1. 获取mcp工具
    mcp_tools = get_mcp_tools()
    # 2. 存在mcp工具，走react agent
    if mcp_tools:

        is_agent_think_start = False
        #2.1 构建react agent
        tools = [_build_tool(t) for t in mcp_tools] if mcp_tools else []
        react_agent = create_react_agent(llm, tools)
        

        
        #2.2 react agent调用
        current_tool_name = None# 跟踪当前工具调用状态
        for chunk in react_agent.stream(
                    {"messages": messages}, {"configurable": {"thread_id": "tid{}".format(username)}}
                ):
            react_response_text = ""
            # 消息类型1：检测工具调用开始
            if "agent" in chunk and "tool_calls" in str(chunk):
                try:
                    tool_calls_data = chunk["agent"]["messages"][0].tool_calls
                    if tool_calls_data and len(tool_calls_data) > 0:
                        tool_name = tool_calls_data[0]["name"]
                        current_tool_name = tool_name
                        react_response_text = f"现在开始调用{tool_name}工具。\n"
                        if not is_agent_think_start:
                            react_response_text = "<think>" + react_response_text
                            is_agent_think_start = True
                        if is_first_sentence:
                            content_temp = react_response_text + "_<isfirst>"
                            is_first_sentence = False

                        stream_manager.new_instance().write_sentence(username, content_temp)
                except (KeyError, IndexError, AttributeError) as e:
                    # 如果提取失败，使用通用提示
                    react_response_text = f"正在调用MCP工具。\n"
                    stream_manager.new_instance().write_sentence(username, react_response_text)
            
            # 消息类型2：检测工具执行结果
            elif "tools" in chunk and current_tool_name:
                react_response_text = f"{current_tool_name}工具已经执行成功。\n"
                stream_manager.new_instance().write_sentence(username, react_response_text)
            
            # 消息类型3：检测最终回复
            else:
                try:
                    react_response_text = chunk["agent"]["messages"][0].content
                    if react_response_text and react_response_text.strip():
                        if is_agent_think_start:
                            react_response_text = "</think>" + react_response_text 
                        stream_manager.new_instance().write_sentence(username, react_response_text)
                except (KeyError, IndexError, AttributeError):
                    react_response_text = f"抱歉，我现在太忙了，休息一会，请稍后再试。"
                    stream_manager.new_instance().write_sentence(username, react_response_text)
            
            full_response_text += react_response_text
                     
    else:
        try:
            # 2.2 使用全局定义的llm对象进行流式请求
            for chunk in llm.stream(messages):
                flush_text = chunk.content
                if not flush_text:
                    continue
                accumulated_text += flush_text
                for mark in punctuation_marks:
                    if mark in accumulated_text:
                        last_punct_pos = max(accumulated_text.rfind(p) for p in punctuation_marks if p in accumulated_text)
                        if last_punct_pos != -1:
                            to_write = accumulated_text[:last_punct_pos + 1]
                            accumulated_text = accumulated_text[last_punct_pos + 1:]
                            if is_first_sentence:
                                to_write += "_<isfirst>"
                                is_first_sentence = False
                            stream_manager.new_instance().write_sentence(username, to_write)
                        break
                full_response_text += flush_text
            # 确保最后一段文本也被发送
            if accumulated_text:
                if is_first_sentence: #相当于整个回复没有标点
                    accumulated_text += "_<isfirst>"
                    is_first_sentence = False
                stream_manager.new_instance().write_sentence(username, accumulated_text)

        except requests.exceptions.RequestException as e:
            util.log(1, f"请求失败: {e}")
            error_message = "抱歉，我现在太忙了，休息一会，请稍后再试。"
            stream_manager.new_instance().write_sentence(username, "_<isfirst>" + error_message + "_<isend>")
            full_response_text = error_message

    # 发送结束标记
    stream_manager.new_instance().write_sentence(username, "_<isend>")

    # 在单独线程中记忆对话内容
    MyThread(target=remember_conversation_thread, args=(username, content, full_response_text.split("</think>")[-1])).start()
    
    return full_response_text.split("</think>")[-1]

        
def set_memory_cleared_flag(flag=True):
    """
    设置记忆清除标记
    
    参数:
        flag: 是否清除记忆，默认为True
    """
    global memory_cleared
    memory_cleared = flag
    if not flag:
        # 删除.memory_cleared标记文件（如果存在）
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mem_base = os.path.join(base_dir, "memory")
        memory_cleared_flag_file = os.path.join(mem_base, ".memory_cleared")
        if os.path.exists(memory_cleared_flag_file):
            try:
                os.remove(memory_cleared_flag_file)
                util.log(1, f"删除记忆清除标记文件: {memory_cleared_flag_file}")
            except Exception as e:
                util.log(1, f"删除记忆清除标记文件时出错: {str(e)}")

def clear_agent_memory():
    """
    清除已加载的agent记忆，但不删除文件
    
    该方法仅清除内存中已加载的记忆，不影响持久化存储。
    如果需要同时清除文件存储，请使用genagents_flask.py中的api_clear_memory方法。
    """
    global agents
    
    try:
        with agent_lock:
            for agent in agents.values():
                # 清除记忆流中的节点
                agent.memory_stream.seq_nodes = []
                agent.memory_stream.id_to_node = {}
                
                # 设置记忆清除标记，防止在退出时保存空记忆
                set_memory_cleared_flag(True)
                
                util.log(1, "已成功清除代理在内存中的记忆")
            
            return True
    except Exception as e:
        util.log(1, f"清除代理记忆时出错: {str(e)}")
        return False

# 反思
def perform_daily_reflection():
    global reflection_time
    global reflection_lock
    
    with reflection_lock:
        if reflection_time and datetime.datetime.now() - reflection_time < datetime.timedelta(seconds=60):
            return
        reflection_time = datetime.datetime.now()
 
        # 获取今天的日期，用于确定反思主题
        today = datetime.datetime.now().weekday()
        
        # 根据星期几选择不同反思主题
        reflection_topics = [
            "我与用户的关系发展，以及我如何更好地理解和服务他们",
            "我的知识库如何得到扩展，哪些概念需要进一步理解",
            "我的情感响应模式以及它们如何反映我的核心价值观",
            "我的沟通方式如何影响互动质量，哪些模式最有效",
            "我的行为如何体现我的核心特质，我的自我认知有何变化",
            "今天的经历如何与我的过往记忆建立联系，形成什么样的模式",
            "本周的整体经历与学习"
        ]
        
        # 选择今天的主题(可以按星期轮换或其他逻辑)
        topic = reflection_topics[today % len(reflection_topics)]
        
        # 执行反思，传入当前时间戳
        for username, agent in agents.items():
            # 获取当前时间作为time_step
            current_time_step = get_current_time_step(username)
            agent.reflect(topic, time_step=current_time_step)
        
        # 记录反思执行情况
        util.log(1, f"反思主题: {topic}")

def save_agent_memory():
    """
    保存代理的记忆到文件
    """
    global agents
    global save_time
    global save_lock
    # 检查记忆清除标记，如果已清除则不保存
    global memory_cleared
    if memory_cleared:
        util.log(1, "检测到记忆已被清除，跳过保存操作")
        return
    
    try:
        with save_lock:
            if save_time and datetime.datetime.now() - save_time < datetime.timedelta(seconds=60):
                return
            save_time = datetime.datetime.now()
            with agent_lock:
                # 逐个用户代理保存记忆
                for username, agent in agents.items():
                    memory_dir = get_user_memory_dir(username)
                    # 检查.memory_cleared标记文件是否存在
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    mem_base = os.path.join(base_dir, "memory")
                    memory_cleared_flag_file = os.path.join(mem_base, ".memory_cleared")
                    if os.path.exists(memory_cleared_flag_file):
                        util.log(1, "检测到.memory_cleared标记文件，跳过保存操作")
                        return
                    
                    # 确保agent和memory_stream已初始化
                    if agent is None:
                        util.log(1, "代理未初始化，无法保存记忆")
                        return
                        
                    if agent.memory_stream is None:
                        util.log(1, "代理记忆流未初始化，无法保存记忆")
                        return
                        
                    # 确保embeddings不为None
                    if agent.memory_stream.embeddings is None:
                        util.log(1, "代理embeddings为None，初始化为空字典")
                        agent.memory_stream.embeddings = {}
                        
                    # 确保seq_nodes不为None
                    if agent.memory_stream.seq_nodes is None:
                        util.log(1, "代理seq_nodes为None，初始化为空列表")
                        agent.memory_stream.seq_nodes = []
                        
                    # 确保id_to_node不为None
                    if agent.memory_stream.id_to_node is None:
                        util.log(1, "代理id_to_node为None，初始化为空字典")
                        agent.memory_stream.id_to_node = {}
                        
                    # 确保scratch不为None
                    if agent.scratch is None:
                        util.log(1, "代理scratch为None，初始化为空字典")
                        agent.scratch = {}
                    
                    # 保存记忆前进行完整性检查
                    try:
                        # 检查seq_nodes中的每个节点是否有效
                        valid_nodes = []
                        for node in agent.memory_stream.seq_nodes:
                            if node is None:
                                util.log(1, "发现无效节点(None)，跳过")
                                continue
                                
                            if not hasattr(node, 'node_id') or not hasattr(node, 'content'):
                                util.log(1, f"发现无效节点(缺少必要属性)，跳过")
                                continue
                                
                            valid_nodes.append(node)
                        
                        # 更新seq_nodes为有效节点列表
                        agent.memory_stream.seq_nodes = valid_nodes
                        
                        # 重建id_to_node字典
                        agent.memory_stream.id_to_node = {node.node_id: node for node in valid_nodes if hasattr(node, 'node_id')}
                    except Exception as e:
                        util.log(1, f"检查记忆完整性时出错: {str(e)}")
                    
                    # 保存记忆
                    try:
                        agent.save(memory_dir)
                    except Exception as e:
                        util.log(1, f"调用agent.save()时出错: {str(e)}")
                        # 尝试手动保存关键数据
                        try:
                            # 创建必要的目录
                            memory_stream_dir = os.path.join(memory_dir, "memory_stream")
                            os.makedirs(memory_stream_dir, exist_ok=True)
                            
                            # 保存embeddings
                            with open(os.path.join(memory_stream_dir, "embeddings.json"), "w", encoding='utf-8') as f:
                                json.dump(agent.memory_stream.embeddings or {}, f, ensure_ascii=False, indent=2)
                                
                            # 保存nodes
                            with open(os.path.join(memory_stream_dir, "nodes.json"), "w", encoding='utf-8') as f:
                                nodes_data = []
                                for node in agent.memory_stream.seq_nodes:
                                    if node is not None and hasattr(node, 'package'):
                                        try:
                                            nodes_data.append(node.package())
                                        except Exception as node_e:
                                            util.log(1, f"打包节点时出错: {str(node_e)}")
                                json.dump(nodes_data, f, ensure_ascii=False, indent=2)
                            
                            # 保存meta
                            with open(os.path.join(memory_dir, "meta.json"), "w", encoding='utf-8') as f:
                                meta_data = {"id": str(agent.id)} if hasattr(agent, 'id') else {}
                                json.dump(meta_data, f, ensure_ascii=False, indent=2)
                                
                            util.log(1, "通过备用方法成功保存记忆")
                        except Exception as backup_e:
                            util.log(1, f"备用保存方法也失败: {str(backup_e)}")
                    
                    # 更新scratch中的时间
                    try:
                        # 实时从config_util更新scratch数据
                        agent.scratch["first_name"] = cfg.config["attribute"]["name"]
                        agent.scratch["age"] = cfg.config["attribute"]["age"]
                        agent.scratch["sex"] = cfg.config["attribute"]["gender"]
                        agent.scratch["additional"] = cfg.config["attribute"]["additional"]
                        agent.scratch["birthplace"] = cfg.config["attribute"]["birth"]
                        agent.scratch["position"] = cfg.config["attribute"]["position"]
                        agent.scratch["zodiac"] = cfg.config["attribute"]["zodiac"]
                        agent.scratch["constellation"] = cfg.config["attribute"]["constellation"]
                        agent.scratch["contact"] = cfg.config["attribute"]["contact"]
                        agent.scratch["voice"] = cfg.config["attribute"]["voice"]
                        agent.scratch["goal"] = cfg.config["attribute"]["goal"]
                        agent.scratch["occupation"] = cfg.config["attribute"]["job"]
                        agent.scratch["current_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except Exception as e:
                        util.log(1, f"更新时间时出错: {str(e)}")
            
    except Exception as e:
        util.log(1, f"保存代理记忆失败: {str(e)}")

def get_mcp_tools():
    """
    从API获取所有在线MCP服务器的工具列表
    """
    try:
        url = 'http://127.0.0.1:5010/api/mcp/servers/online/tools'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('tools', [])
        
        util.log(1, f"获取工具列表失败，状态码：{response.status_code}")
        return []
    except Exception as e:
        util.log(1, f"获取工具列表出错：{e}")
        return []


def _schema_to_args_schema(tool_name: str, schema: dict):
    """将 JSON Schema 转成 Pydantic 参数模型，供 StructuredTool 使用"""
    if not schema:
        return create_model(f"{tool_name.capitalize()}Args")
    props = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    fields = {}
    for field, meta in props.items():
        meta_type = meta.get("type", "string")
        py_type = float if meta_type in ("number", "integer") else str
        default = ... if field in required_fields else None
        fields[field] = (py_type, default)
    return create_model(f"{tool_name.capitalize()}Args", **fields)


def _build_tool(tool_def: dict) -> StructuredTool:
    """根据从服务器获取的工具定义，动态生成 LangChain StructuredTool"""
    name = tool_def.get("name", "")
    description = tool_def.get("description", "")
    input_schema = tool_def.get("inputSchema", {"type": "object", "properties": {}})

    ArgsSchema = _schema_to_args_schema(name, input_schema)

    def _caller(**kwargs):
        """实际的工具调用包装函数"""
        try:
            resp = requests.post(f"http://127.0.0.1:5010/api/mcp/tools/{name}", json=kwargs, timeout=120)
            data = resp.json()
            if data.get("success"):
                return data.get("result", "无返回值")
            return f"调用失败: {data.get('error', '未知错误')}"
        except Exception as e:
            return f"调用异常: {str(e)}"

    _caller.__name__ = name  # 保证 tool.name 与函数名一致
    return StructuredTool.from_function(
        func=_caller,
        name=name,
        description=description,
        args_schema=ArgsSchema
    )


if __name__ == "__main__":
    init_memory_scheduler()
    for _ in range(3):
        query = "Fay是什么"
        response = question(query)
        print(f"Q: {query}")
        print(f"A: {response}")
        time.sleep(1)

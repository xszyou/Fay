import os
import json
import time
import threading
import requests
from utils import util
import utils.config_util as cfg
from genagents.genagents import GenerativeAgent
from genagents.modules.memory_stream import ConceptNode
from core import member_db
from urllib3.exceptions import InsecureRequestWarning
import schedule
from scheduler.thread_manager import MyThread
import datetime
from core import stream_manager

# 加载配置
cfg.load_config()

# 禁用不安全请求警告
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

agent = None
memory_dir = None
memory_stream_dir = None
agent_lock = threading.RLock()  # 使用可重入锁保护agent对象
memory_cleared = False  # 添加记忆清除标记

def get_current_time_step():
    """
    获取当前时间作为time_step
    
    返回:
        int: 当前时间的时间戳（秒）
    """
    global agent
    try:
        if agent and agent.memory_stream and agent.memory_stream.seq_nodes:
            # 如果有记忆节点，则使用最后一个节点的created属性加1
            return int(agent.memory_stream.seq_nodes[-1].created) + 1
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
    global agent
    
    # 确保agent已经创建
    if agent is None:
        util.log(1, '创建代理实例...')
        agent = create_agent()
    
    # 设置每天0点保存记忆
    schedule.every().day.at("00:00").do(save_agent_memory)
    
    # 设置每天晚上11点执行反思
    schedule.every().day.at("23:30").do(perform_daily_reflection)
    
    # 启动定时任务线程
    scheduler_thread = MyThread(target=memory_scheduler_thread)
    scheduler_thread.start()
    
    util.log(1, '定时任务已启动：每天0点保存记忆，每天23点执行反思')

def check_memory_files():
    """
    检查memory目录及其必要文件是否存在
    
    返回:
        memory_dir: memory目录路径
        is_complete: 是否已经存在完整的memory目录结构
    """
    global memory_dir
    global memory_stream_dir
    
    # 获取memory目录路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    memory_dir = os.path.join(base_dir, "memory")
    
    # 检查memory目录是否存在，不存在则创建
    if not os.path.exists(memory_dir):
        os.makedirs(memory_dir)
        util.log(1, f"创建memory目录: {memory_dir}")
    
    # 删除.memory_cleared标记文件（如果存在）
    memory_cleared_flag_file = os.path.join(memory_dir, ".memory_cleared")
    if os.path.exists(memory_cleared_flag_file):
        try:
            os.remove(memory_cleared_flag_file)
            util.log(1, f"删除记忆清除标记文件: {memory_cleared_flag_file}")
            # 重置记忆清除标记
            global memory_cleared
            memory_cleared = False
        except Exception as e:
            util.log(1, f"删除记忆清除标记文件时出错: {str(e)}")
    
    # 检查meta.json是否存在
    meta_file = os.path.join(memory_dir, "meta.json")
    is_complete = os.path.exists(meta_file)
    
    # 检查memory_stream目录是否存在，不存在则创建
    memory_stream_dir = os.path.join(memory_dir, "memory_stream")
    if not os.path.exists(memory_stream_dir):
        os.makedirs(memory_stream_dir)
        util.log(1, f"创建memory_stream目录: {memory_stream_dir}")
    
    # 检查必要的文件是否存在
    scratch_path = os.path.join(memory_dir, "scratch.json")
    embeddings_path = os.path.join(memory_stream_dir, "embeddings.json")
    nodes_path = os.path.join(memory_stream_dir, "nodes.json")
    
    # 检查文件是否存在且不为空
    is_complete = (os.path.exists(scratch_path) and os.path.getsize(scratch_path) > 2 and
                  os.path.exists(embeddings_path) and os.path.getsize(embeddings_path) > 2 and
                  os.path.exists(nodes_path) and os.path.getsize(nodes_path) > 2)
    
    # 如果文件不存在，创建空的JSON文件
    if not os.path.exists(scratch_path):
        with open(scratch_path, 'w', encoding='utf-8') as f:
            f.write('{}')
    
    if not os.path.exists(embeddings_path):
        with open(embeddings_path, 'w', encoding='utf-8') as f:
            f.write('{}')
    
    if not os.path.exists(nodes_path):
        with open(nodes_path, 'w', encoding='utf-8') as f:
            f.write('[]')
    
    return memory_dir, is_complete

def create_agent():
    """
    创建一个GenerativeAgent实例
    
    返回:
        agent: GenerativeAgent对象
    """
    global agent
    
    # 创建代理
    with agent_lock:
        if agent is None:
            memory_dir, is_exist = check_memory_files()
            agent = GenerativeAgent(memory_dir)
            
            # 检查是否有scratch属性，如果没有则添加
            if not hasattr(agent, 'scratch'):
                agent.scratch = {}
            
            # 如果memory目录不存在或为空，则初始化代理
            if not is_exist:
                # 初始化代理的scratch数据
                scratch_data = {
                    "first_name": cfg.config["attribute"]["name"],
                    "last_name": "",
                    "age": cfg.config["attribute"]["age"],
                    "gender": cfg.config["attribute"]["gender"],
                    "traits": cfg.config["attribute"]["additional"],
                    "status": "active",
                    "location": "home",
                    "occupation": cfg.config["attribute"]["job"],
                    "interests": [],
                    "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                agent.scratch = scratch_data
            else:
                # 加载之前保存的记忆
                load_agent_memory(agent)
        
    return agent

def load_agent_memory(agent):
    """
    从文件加载代理的记忆
    
    参数:
        agent: GenerativeAgent对象
    """
    try:
        # 获取memory目录路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        memory_dir = os.path.join(base_dir, "memory")
        memory_stream_dir = os.path.join(memory_dir, "memory_stream")
        
        # 加载scratch.json
        scratch_path = os.path.join(memory_dir, "scratch.json")
        if os.path.exists(scratch_path) and os.path.getsize(scratch_path) > 2:  # 文件存在且不为空
            with open(scratch_path, 'r', encoding='utf-8') as f:
                scratch_data = json.load(f)
                agent.scratch = scratch_data
        
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
    global agent
    try:
        with agent_lock:
            # 获取当前时间作为time_step
            time_step = get_current_time_step()
            
            # 记录对话内容
            memory_content = f"在对话中，我回答了用户{username}的问题：{content}\n，我的回答是：{response_text}"
            agent.remember(memory_content, time_step)
    except Exception as e:
        util.log(1, f"记忆对话内容出错: {str(e)}")

def question(content, uid=0, observation=""):
    """
    处理用户问题并返回回答
    
    参数:
        content: 用户问题内容
        uid: 用户ID，默认为0
        observation: 额外的观察信息，默认为空
        
    返回:
        response_text: 回答内容
    """
    global agent
    # 获取用户名
    username = member_db.new_instance().find_username_by_uid(uid) if uid != 0 else "User"
    
    # 创建代理
    agent = create_agent()
    
    # 获取对话历史
    history_messages = [] 
    history_messages.append([username, content])
    
    # 构建提示信息
    str_dialogue = ""
    for row in history_messages:
        str_dialogue += f"[{row[0]}]: {row[1]}\n"
    str_dialogue += f"[Fay]: [Fill in]\n"
    
    # 构建代理描述
    agent_desc = {
        "first_name": agent.scratch.get("first_name", "Fay"),
        "last_name": agent.scratch.get("last_name", ""),
        "age": agent.scratch.get("age", "25"),
        "gender": agent.scratch.get("gender", "女"),
        "traits": agent.scratch.get("traits", "友好、乐于助人"),
        "status": agent.scratch.get("status", "active"),
        "location": agent.scratch.get("location", "home"),
        "occupation": agent.scratch.get("occupation", "助手"),
    }
    
    # 获取相关记忆作为上下文
    context = ""
    if agent.memory_stream and len(agent.memory_stream.seq_nodes) > 0:
        # 获取当前时间步
        current_time_step = get_current_time_step()
        
        # 使用retrieve方法获取相关记忆
        try:
            related_memories = agent.memory_stream.retrieve(
                [content],  # 查询句子列表
                current_time_step,  # 当前时间步
                n_count=5,  # 获取5条相关记忆
                curr_filter="all",  # 获取所有类型的记忆
                hp=[0, 1, 0.5]  # 权重：[时间近度权重recency_w, 相关性权重relevance_w, 重要性权重importance_w]
            )
            
            if related_memories and content in related_memories:
                memory_nodes = related_memories[content]
                if memory_nodes:
                    context = "以下是相关的记忆：\n"
                    for node in memory_nodes:
                        context += f"- {node.content}\n"
        except Exception as e:
            util.log(1, f"获取相关记忆时出错: {str(e)}")
    
    # 使用流式请求获取回答
    session = requests.Session()
    session.verify = False
    httpproxy = cfg.proxy_config
    if httpproxy:
        session.proxies = {
            "http": f"http://{httpproxy}",
            "https": f"https://{httpproxy}"
        }
    
    # 构建消息
    prompt = f"""你是我的数字人，你名字是：{agent_desc['first_name']}，你性别为{agent_desc['gender']}，
    你年龄为{agent_desc['age']}，你职业为{agent_desc['occupation']}，
    {agent_desc['traits']}。
    你有以下记忆和上下文信息：{context}
    回答之前请一步一步想清楚。对于大部分问题，请直接回答并提供有用和准确的信息。
    所有回复请尽量控制在20字内。
    """
    
    messages = [{"role": "system", "content": prompt}]
    messages.append({"role": "user", "content": content})
    
    # 构建请求数据
    data = {
        "model": cfg.gpt_model_engine,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
        "user": f"user_{uid}"
    }
    
    # 开启流式传输
    data["stream"] = True
    
    url = cfg.gpt_base_url + "/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {cfg.key_gpt_api_key}'
    }
    
    try:
        response = session.post(url, json=data, headers=headers, stream=True)
        response.raise_for_status()

        full_response_text = ""
        accumulated_text = ""
        punctuation_marks = ["。", "！", "？", ".", "!", "?", "\n"]  
        is_first_sentence = True  
        for raw_line in response.iter_lines(decode_unicode=False):
            line = raw_line.decode('utf-8', errors='ignore')
            if not line or line.strip() == "":
                continue 

            if line.startswith("data: "):
                chunk = line[len("data: "):].strip()
                try:
                    json_data = json.loads(chunk)
                    finish_reason = json_data["choices"][0].get("finish_reason")
                    if finish_reason is not None:
                        if finish_reason == "stop":
                            # 确保最后一段文本也被发送
                            if accumulated_text:
                                if is_first_sentence:
                                    accumulated_text += "_<isfirst>"
                                    is_first_sentence = False
                                stream_manager.new_instance().write_sentence(uid, accumulated_text)
                            # 发送结束标记
                            stream_manager.new_instance().write_sentence(uid, "_<isend>")
                            break
                    
                    flush_text = json_data["choices"][0]["delta"].get("content", "")
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
                                stream_manager.new_instance().write_sentence(uid, to_write)
                            break

                    full_response_text += flush_text
                except json.JSONDecodeError:
                    continue

        # 在单独线程中记忆对话内容
        from scheduler.thread_manager import MyThread
        MyThread(target=remember_conversation_thread, args=(username, content, full_response_text)).start()
        
        return full_response_text

    except requests.exceptions.RequestException as e:
        util.log(1, f"请求失败: {e}")
        error_message = "抱歉，我现在太忙了，休息一会，请稍后再试。"
        stream_manager.new_instance().write_sentence(uid, error_message)
        return error_message

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
        memory_cleared_flag_file = os.path.join(memory_dir, ".memory_cleared")
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
    global agent
    
    try:
        with agent_lock:
            if agent is None:
                util.log(1, "代理未初始化，无需清除记忆")
                return
            
            # 清除记忆流中的节点
            agent = None
            
            # 设置记忆清除标记，防止在退出时保存空记忆
            set_memory_cleared_flag(True)
            
            util.log(1, "已成功清除代理在内存中的记忆")
            
            return True
    except Exception as e:
        util.log(1, f"清除代理记忆时出错: {str(e)}")
        return False

# 反思
def perform_daily_reflection():
    # 获取当前时间作为time_step
    current_time_step = get_current_time_step()
    
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
    
    # 执行反思
    agent.reflect(topic)
    
    # 记录反思执行情况
    util.log(1, f"反思主题: {topic}")

def save_agent_memory():
    """
    保存代理的记忆到文件
    """
    global agent
    
    # 检查记忆清除标记，如果已清除则不保存
    global memory_cleared
    if memory_cleared:
        util.log(1, "检测到记忆已被清除，跳过保存操作")
        return
    
    try:
        with agent_lock:
            # 检查.memory_cleared标记文件是否存在
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            memory_dir = os.path.join(base_dir, "memory")
            memory_cleared_flag_file = os.path.join(memory_dir, ".memory_cleared")
            
            if os.path.exists(memory_cleared_flag_file):
                util.log(1, "检测到记忆清除标记文件，跳过保存操作")
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
                        
                    # 保存scratch
                    with open(os.path.join(memory_dir, "scratch.json"), "w", encoding='utf-8') as f:
                        json.dump(agent.scratch or {}, f, ensure_ascii=False, indent=2)
                        
                    # 保存meta
                    with open(os.path.join(memory_dir, "meta.json"), "w", encoding='utf-8') as f:
                        meta_data = {"id": str(agent.id)} if hasattr(agent, 'id') else {}
                        json.dump(meta_data, f, ensure_ascii=False, indent=2)
                        
                    util.log(1, "通过备用方法成功保存记忆")
                except Exception as backup_e:
                    util.log(1, f"备用保存方法也失败: {str(backup_e)}")
            
            # 更新scratch中的时间
            try:
                agent.scratch["current_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                util.log(1, f"更新时间时出错: {str(e)}")
            
            util.log(1, f"已保存代理记忆")
    except Exception as e:
        util.log(1, f"保存代理记忆失败: {str(e)}")

if __name__ == "__main__":
    init_memory_scheduler()
    for _ in range(3):
        query = "Fay是什么"
        response = question(query)
        print(f"Q: {query}")
        print(f"A: {response}")
        time.sleep(1)

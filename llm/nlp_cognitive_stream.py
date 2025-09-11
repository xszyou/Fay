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

# 新增：本地知识库相关导入
import re
from pathlib import Path
import docx
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
try:
    from pptx import Presentation
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

# 用于处理 .doc 文件的库
try:
    import win32com.client
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False

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
os.environ["LANGCHAIN_PROJECT"] = "fay3.8.2_github"

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

# 新增：本地知识库相关函数
def read_doc_file(file_path):
    """
    读取doc文件内容
    
    参数:
        file_path: doc文件路径
        
    返回:
        str: 文档内容
    """
    try:
        # 方法1: 使用 win32com.client（Windows系统，推荐用于.doc文件）
        if WIN32COM_AVAILABLE:
            word = None
            doc = None
            try:
                import pythoncom
                pythoncom.CoInitialize()  # 初始化COM组件
                
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                doc = word.Documents.Open(file_path)
                content = doc.Content.Text
                
                # 先保存内容，再尝试关闭
                if content and content.strip():
                    try:
                        doc.Close()
                        word.Quit()
                    except Exception as close_e:
                        util.log(1, f"关闭Word应用程序时出错: {str(close_e)}，但内容已成功提取")
                    
                    try:
                        pythoncom.CoUninitialize()  # 清理COM组件
                    except:
                        pass
                    
                    return content.strip()
                
            except Exception as e:
                util.log(1, f"使用 win32com 读取 .doc 文件失败: {str(e)}")
            finally:
                # 确保资源被释放
                try:
                    if doc:
                        doc.Close()
                except:
                    pass
                try:
                    if word:
                        word.Quit()
                except:
                    pass
                try:
                    pythoncom.CoUninitialize()
                except:
                    pass
        
        # 方法2: 简单的二进制文本提取（备选方案）
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                # 尝试提取可打印的文本
                text_parts = []
                current_text = ""
                
                for byte in raw_data:
                    char = chr(byte) if 32 <= byte <= 126 or byte in [9, 10, 13] else None
                    if char:
                        current_text += char
                    else:
                        if len(current_text) > 3:  # 只保留长度大于3的文本片段
                            text_parts.append(current_text.strip())
                        current_text = ""
                
                if len(current_text) > 3:
                    text_parts.append(current_text.strip())
                
                # 过滤和清理文本
                filtered_parts = []
                for part in text_parts:
                    # 移除过多的重复字符和无意义的片段
                    if (len(part) > 5 and 
                        not part.startswith('Microsoft') and 
                        not all(c in '0123456789-_.' for c in part) and
                        len(set(part)) > 3):  # 字符种类要多样
                        filtered_parts.append(part)
                
                if filtered_parts:
                    return '\n'.join(filtered_parts)
                    
        except Exception as e:
            util.log(1, f"使用二进制方法读取 .doc 文件失败: {str(e)}")
        
        util.log(1, f"无法读取 .doc 文件 {file_path}，建议转换为 .docx 格式")
        return ""
        
    except Exception as e:
        util.log(1, f"读取doc文件 {file_path} 时出错: {str(e)}")
        return ""

def read_docx_file(file_path):
    """
    读取docx文件内容
    
    参数:
        file_path: docx文件路径
        
    返回:
        str: 文档内容
    """
    try:
        doc = docx.Document(file_path)
        content = []
        
        for element in doc.element.body:
            if isinstance(element, CT_P):
                paragraph = Paragraph(element, doc)
                if paragraph.text.strip():
                    content.append(paragraph.text.strip())
            elif isinstance(element, CT_Tbl):
                table = Table(element, doc)
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        content.append(" | ".join(row_text))
        
        return "\n".join(content)
    except Exception as e:
        util.log(1, f"读取docx文件 {file_path} 时出错: {str(e)}")
        return ""
    
def read_pptx_file(file_path):
    """
    读取pptx文件内容
    
    参数:
        file_path: pptx文件路径
        
    返回:
        str: 演示文稿内容
    """
    if not PPTX_AVAILABLE:
        util.log(1, "python-pptx 库未安装，无法读取 PowerPoint 文件")
        return ""
        
    try:
        prs = Presentation(file_path)
        content = []
        
        for i, slide in enumerate(prs.slides):
            slide_content = [f"第{i+1}页："]
            
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_content.append(shape.text.strip())
                    
            if len(slide_content) > 1:  # 有内容才添加
                content.append("\n".join(slide_content))
        
        return "\n\n".join(content)
    except Exception as e:
        util.log(1, f"读取pptx文件 {file_path} 时出错: {str(e)}")
        return ""

def load_local_knowledge_base():
    """
    加载本地知识库内容
    
    返回:
        dict: 文件名到内容的映射
    """
    knowledge_base = {}
    
    # 获取llm/data目录路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, "data")
    
    if not os.path.exists(data_dir):
        util.log(1, f"知识库目录不存在: {data_dir}")
        return knowledge_base
    
    # 遍历data目录中的文件
    for file_path in Path(data_dir).iterdir():
        if not file_path.is_file():
            continue
            
        file_name = file_path.name
        file_extension = file_path.suffix.lower()
        
        try:
            if file_extension == '.docx':
                content = read_docx_file(str(file_path))
            elif file_extension == '.doc':
                content = read_doc_file(str(file_path))
            elif file_extension == '.pptx':
                content = read_pptx_file(str(file_path))
            else:
                # 尝试作为文本文件读取
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    try:
                        with open(file_path, 'r', encoding='gbk') as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        util.log(1, f"无法解码文件: {file_name}")
                        continue
            
            if content.strip():
                knowledge_base[file_name] = content
                util.log(1, f"成功加载知识库文件: {file_name} ({len(content)} 字符)")
            
        except Exception as e:
            util.log(1, f"加载知识库文件 {file_name} 时出错: {str(e)}")
    
    return knowledge_base

def search_knowledge_base(query, knowledge_base, max_results=3):
    """
    在知识库中搜索相关内容
    
    参数:
        query: 查询内容
        knowledge_base: 知识库字典
        max_results: 最大返回结果数
        
    返回:
        list: 相关内容列表
    """
    if not knowledge_base:
        return []
    
    results = []
    query_lower = query.lower()
    
    # 搜索关键词
    query_keywords = re.findall(r'\w+', query_lower)
    
    for file_name, content in knowledge_base.items():
        content_lower = content.lower()
        
        # 计算匹配度
        score = 0
        matched_sentences = []
        
        # 按句子分割内容
        sentences = re.split(r'[。！？\n]', content)
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            sentence_lower = sentence.lower()
            sentence_score = 0
            
            # 计算关键词匹配度
            for keyword in query_keywords:
                if keyword in sentence_lower:
                    sentence_score += 1
            
            # 如果句子有匹配，记录
            if sentence_score > 0:
                matched_sentences.append((sentence.strip(), sentence_score))
                score += sentence_score
        
        # 如果有匹配的内容
        if score > 0:
            # 按匹配度排序句子
            matched_sentences.sort(key=lambda x: x[1], reverse=True)
            
            # 取前几个最相关的句子
            relevant_sentences = [sent[0] for sent in matched_sentences[:5] if sent[0]]
            
            if relevant_sentences:
                results.append({
                    'file_name': file_name,
                    'score': score,
                    'content': '\n'.join(relevant_sentences)
                })
    
    # 按匹配度排序
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results[:max_results]

# 全局知识库缓存
_knowledge_base_cache = None
_knowledge_base_load_time = None
_knowledge_base_file_times = {}  # 存储文件的最后修改时间

def check_knowledge_base_changes():
    """
    检查知识库文件是否有变化
    
    返回:
        bool: 如果有文件变化返回True，否则返回False
    """
    global _knowledge_base_file_times
    
    # 获取llm/data目录路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, "data")
    
    if not os.path.exists(data_dir):
        return False
    
    current_file_times = {}
    
    # 遍历data目录中的文件
    for file_path in Path(data_dir).iterdir():
        if not file_path.is_file():
            continue
        
        file_name = file_path.name
        file_extension = file_path.suffix.lower()
        
        # 只检查支持的文件格式
        if file_extension in ['.docx', '.doc', '.pptx', '.txt'] or file_extension == '':
            try:
                mtime = os.path.getmtime(str(file_path))
                current_file_times[file_name] = mtime
            except OSError:
                continue
    
    # 检查是否有变化
    if not _knowledge_base_file_times:
        # 第一次检查，保存文件时间
        _knowledge_base_file_times = current_file_times
        return True
    
    # 比较文件时间
    if set(current_file_times.keys()) != set(_knowledge_base_file_times.keys()):
        # 文件数量发生变化
        _knowledge_base_file_times = current_file_times
        return True
    
    for file_name, mtime in current_file_times.items():
        if file_name not in _knowledge_base_file_times or _knowledge_base_file_times[file_name] != mtime:
            # 文件被修改
            _knowledge_base_file_times = current_file_times
            return True
    
    return False

def init_knowledge_base():
    """
    初始化知识库，在系统启动时调用
    """
    global _knowledge_base_cache, _knowledge_base_load_time
    
    util.log(1, "初始化本地知识库...")
    _knowledge_base_cache = load_local_knowledge_base()
    _knowledge_base_load_time = time.time()
    
    # 初始化文件修改时间跟踪
    check_knowledge_base_changes()
    
    util.log(1, f"知识库初始化完成，共 {len(_knowledge_base_cache)} 个文件")

def get_knowledge_base():
    """
    获取知识库，使用缓存机制
    
    返回:
        dict: 知识库内容
    """
    global _knowledge_base_cache, _knowledge_base_load_time
    
    # 如果缓存为空，先初始化
    if _knowledge_base_cache is None:
        init_knowledge_base()
        return _knowledge_base_cache
    
    # 检查文件是否有变化
    if check_knowledge_base_changes():
        util.log(1, "检测到知识库文件变化，正在重新加载...")
        _knowledge_base_cache = load_local_knowledge_base()
        _knowledge_base_load_time = time.time()
        util.log(1, f"知识库重新加载完成，共 {len(_knowledge_base_cache)} 个文件")
    
    return _knowledge_base_cache


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
    schedule.every().day.at("23:00").do(perform_daily_reflection)
    
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
    punctuation_marks = [",", "，","。", "！", "？", ".", "!", "?", "\n"]  
    is_first_sentence = True
    
    # 记录当前会话版本，用于精准中断
    from core import stream_manager
    sm = stream_manager.new_instance()
    session_version = sm.get_session_version(username)

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
                n_count=100,  # 获取100条相关记忆
                curr_filter="all",  # 获取所有类型的记忆
                hp=[0.8, 0.5, 0.5],  # 权重：[时间近度权重recency_w, 相关性权重relevance_w, 重要性权重importance_w]
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
    
    # 新增：搜索本地知识库
    knowledge_context = ""
    try:
        knowledge_base = get_knowledge_base()
        if knowledge_base:
            knowledge_results = search_knowledge_base(content, knowledge_base, max_results=3)
            if knowledge_results:
                knowledge_context = "**本地知识库相关信息**：\n"
                for result in knowledge_results:
                    knowledge_context += f"来源文件：{result['file_name']}\n"
                    knowledge_context += f"{result['content']}\n\n"
                util.log(1, f"找到 {len(knowledge_results)} 条相关知识库信息")
    except Exception as e:
        util.log(1, f"搜索知识库时出错: {str(e)}")

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
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=content)]

    # 1. 获取mcp工具
    mcp_tools = get_mcp_tools()
    # 2. 存在mcp工具，走react agent
    if mcp_tools:

        is_agent_think_start = False#记录是否已经写入start标签
        #2.1 构建react agent
        tools = [_build_tool(t) for t in mcp_tools] if mcp_tools else []
        react_agent = create_react_agent(llm, tools)
        

        
        #2.2 react agent调用
        current_tool_name = None# 跟踪当前工具调用状态
        for chunk in react_agent.stream(
                    {"messages": messages}, {"configurable": {"thread_id": "tid{}".format(username)}}
                ):
            # 检查是否需要停止生成
            if sm.should_stop_generation(username, session_version=session_version):
                util.log(1, f"检测到停止标志，中断React Agent文本生成: {username}")
                break
                
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
                        else:
                            content_temp = react_response_text

                        stream_manager.new_instance().write_sentence(username, content_temp, session_version=session_version)
                except (KeyError, IndexError, AttributeError) as e:
                    # 如果提取失败，使用通用提示
                    react_response_text = f"正在调用MCP工具。\n"
                    stream_manager.new_instance().write_sentence(username, react_response_text, session_version=session_version)
            
            # 消息类型2：检测工具执行结果
            elif "tools" in chunk and current_tool_name:
                react_response_text = f"{current_tool_name}工具已经执行成功。\n"
                stream_manager.new_instance().write_sentence(username, react_response_text, session_version=session_version)
            
            # 消息类型3：检测最终回复
            else:
                try:
                    react_response_text = chunk["agent"]["messages"][0].content
                    if react_response_text and react_response_text.strip():
                        if is_agent_think_start:
                            react_response_text = "</think>" + react_response_text 
                        # 对React Agent的最终回复也进行分句处理
                        accumulated_text += react_response_text
                        # 使用安全的流式文本处理器和状态管理器
                        from utils.stream_text_processor import get_processor
                        from utils.stream_state_manager import get_state_manager

                        processor = get_processor()
                        state_manager = get_state_manager()

                        # 确保有活跃会话
                        if not state_manager.is_session_active(username):
                            state_manager.start_new_session(username, "react_agent")

                        # 如果累积文本达到一定长度，进行处理
                        if len(accumulated_text) >= 20:  # 设置一个合理的阈值
                            # 找到最后一个标点符号的位置
                            last_punct_pos = -1
                            for punct in processor.punctuation_marks:
                                pos = accumulated_text.rfind(punct)
                                if pos > last_punct_pos:
                                    last_punct_pos = pos

                            if last_punct_pos > 10:  # 确保有足够的内容发送
                                sentence_text = accumulated_text[:last_punct_pos + 1]
                                # 使用状态管理器准备句子
                                marked_text, _, _ = state_manager.prepare_sentence(username, sentence_text)
                                stream_manager.new_instance().write_sentence(username, marked_text, session_version=session_version)
                                accumulated_text = accumulated_text[last_punct_pos + 1:].lstrip()
                        
                except (KeyError, IndexError, AttributeError):
                    react_response_text = f"抱歉，我现在太忙了，休息一会，请稍后再试。"
                    if is_first_sentence:
                        react_response_text = "_<isfirst>" + react_response_text
                        is_first_sentence = False
                    stream_manager.new_instance().write_sentence(username, react_response_text, session_version=session_version)
            
            full_response_text += react_response_text
        
        # 确保React Agent最后一段文本也被发送，并标记为结束（若会话未被取消）
        from utils.stream_state_manager import get_state_manager
        state_manager = get_state_manager()

        if not sm.should_stop_generation(username, session_version=session_version):
            if accumulated_text:
                # 使用状态管理器准备最后的文本，强制标记为结束
                marked_text, _, _ = state_manager.prepare_sentence(username, accumulated_text, force_end=True)
                stream_manager.new_instance().write_sentence(username, marked_text, session_version=session_version)
            else:
                # 如果没有剩余文本，检查是否需要发送结束标记
                session_info = state_manager.get_session_info(username)
                if session_info and not session_info.get('is_end_sent', False):
                    # 发送一个空的结束标记
                    marked_text, _, _ = state_manager.prepare_sentence(username, "", force_end=True)
                    stream_manager.new_instance().write_sentence(username, marked_text, session_version=session_version)
                     
                     
    else:
        try:
            # 2.2 使用全局定义的llm对象进行流式请求
            for chunk in llm.stream(messages):
                # 检查是否需要停止生成
                if sm.should_stop_generation(username, session_version=session_version):
                    util.log(1, f"检测到停止标志，中断LLM文本生成: {username}")
                    break
                    
                flush_text = chunk.content
                if not flush_text:
                    continue
                accumulated_text += flush_text
                # 使用安全的流式处理逻辑和状态管理器
                from utils.stream_text_processor import get_processor
                from utils.stream_state_manager import get_state_manager

                processor = get_processor()
                state_manager = get_state_manager()

                # 确保有活跃会话
                if not state_manager.is_session_active(username):
                    state_manager.start_new_session(username, "llm_stream")

                # 如果累积文本达到一定长度，进行处理
                if len(accumulated_text) >= 20:  # 设置一个合理的阈值
                    # 找到最后一个标点符号的位置
                    last_punct_pos = -1
                    for punct in processor.punctuation_marks:
                        pos = accumulated_text.rfind(punct)
                        if pos > last_punct_pos:
                            last_punct_pos = pos

                    if last_punct_pos > 10:  # 确保有足够的内容发送
                        sentence_text = accumulated_text[:last_punct_pos + 1]
                        # 使用状态管理器准备句子
                        marked_text, _, _ = state_manager.prepare_sentence(username, sentence_text)
                        stream_manager.new_instance().write_sentence(username, marked_text, session_version=session_version)
                        accumulated_text = accumulated_text[last_punct_pos + 1:].lstrip()
                        
                full_response_text += flush_text
            # 确保最后一段文本也被发送，并标记为结束（若会话未被取消）
            from utils.stream_state_manager import get_state_manager
            state_manager = get_state_manager()

            if not sm.should_stop_generation(username, session_version=session_version):
                if accumulated_text:
                    # 使用状态管理器准备最后的文本，强制标记为结束
                    marked_text, _, _ = state_manager.prepare_sentence(username, accumulated_text, force_end=True)
                    stream_manager.new_instance().write_sentence(username, marked_text, session_version=session_version)
                else:
                    # 如果没有剩余文本，检查是否需要发送结束标记
                    session_info = state_manager.get_session_info(username)
                    if session_info and not session_info.get('is_end_sent', False):
                        # 发送一个空的结束标记
                        marked_text, _, _ = state_manager.prepare_sentence(username, "", force_end=True)
                        stream_manager.new_instance().write_sentence(username, marked_text, session_version=session_version)


        except requests.exceptions.RequestException as e:
            util.log(1, f"请求失败: {e}")
            error_message = "抱歉，我现在太忙了，休息一会，请稍后再试。"
            # 会话未被取消时才发送错误提示
            if not sm.should_stop_generation(username, session_version=session_version):
                stream_manager.new_instance().write_sentence(username, "_<isfirst>" + error_message + "_<isend>", session_version=session_version)
            full_response_text = error_message

    # 结束会话（不再需要发送额外的结束标记）
    from utils.stream_state_manager import get_state_manager
    state_manager = get_state_manager()
    state_manager.end_session(username)

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
            try:
                # 获取当前时间作为time_step
                current_time_step = get_current_time_step(username)
                agent.reflect(topic, time_step=current_time_step)
            except KeyError as e:
                util.log(1, f"反思时出现KeyError: {e}，跳过此次反思")
            except Exception as e:
                util.log(1, f"反思时出现错误: {e}，跳过此次反思")
        
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

import os
import json
import codecs
from langsmith.schemas import Feedback
import requests
from configparser import ConfigParser
import functools
from threading import Lock
import threading
from utils import util

# 线程本地存储，用于支持多个项目配置
_thread_local = threading.local()

# 全局锁，确保线程安全
lock = Lock()
def synchronized(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with lock:
            return func(*args, **kwargs)
    return wrapper

# 默认配置，用于全局访问
config: json = None
system_config: ConfigParser = None
system_chrome_driver = None
key_ali_nls_key_id = None
key_ali_nls_key_secret = None
key_ali_nls_app_key = None
key_ms_tts_key = None
Key_ms_tts_region = None
baidu_emotion_app_id = None
baidu_emotion_api_key = None
baidu_emotion_secret_key = None
key_gpt_api_key = None
gpt_model_engine = None
proxy_config = None
ASR_mode = None
local_asr_ip = None 
local_asr_port = None 
ltp_mode = None
gpt_base_url = None
tts_module = None
key_ali_tss_key_id = None
key_ali_tss_key_secret = None
key_ali_tss_app_key = None
volcano_tts_appid = None
volcano_tts_access_token = None
volcano_tts_cluster = None
volcano_tts_voice_type = None
start_mode = None
fay_url = None
system_conf_path = None
config_json_path = None

# config server中心配置，system.conf与config.json存在时不会使用配置中心
CONFIG_SERVER = {
    'BASE_URL': 'http://219.135.170.56:5500',  # 默认API服务器地址
    'API_KEY': 'your-api-key-here',       # 默认API密钥
    'PROJECT_ID': 'd19f7b0a-2b8a-4503-8c0d-1a587b90eb69'   # 项目ID，需要在使用前设置
}


def load_config_from_api(project_id=None):
    global CONFIG_SERVER

    """
    从API加载配置
    
    Args:
        project_id: 项目ID，如果为None则使用全局设置的项目ID
    
    Returns:
        包含配置信息的字典，加载失败则返回None
    """
    # 使用参数提供的项目ID或全局设置的项目ID
    pid = project_id or CONFIG_SERVER['PROJECT_ID']
    if not pid:
        util.log(2, "错误: 未指定项目ID，无法从API加载配置")
        return None
    
    # 构建API请求URL
    url = f"{CONFIG_SERVER['BASE_URL']}/api/projects/{pid}/config"
    
    # 设置请求头
    headers = {
        'X-API-Key': CONFIG_SERVER['API_KEY'],
        'Content-Type': 'application/json'
    }
    
    try:
        # 发送API请求
        response = requests.get(url, headers=headers)
        
        # 检查响应状态
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                # 提取配置数据
                project_data = result.get('project', {})
                
                # 创建并填充ConfigParser对象
                sys_config = ConfigParser()
                sys_config.add_section('key')
                
                # 获取系统配置字典
                system_dict = project_data.get('system_config', {})
                for section, items in system_dict.items():
                    if not sys_config.has_section(section):
                        sys_config.add_section(section)
                    for key, value in items.items():
                        sys_config.set(section, key, str(value))
                
                # 获取用户配置
                user_config = project_data.get('config_json', {})
                
                # 创建配置字典
                config_dict = {
                    'system_config': sys_config,
                    'config': user_config,
                    'project_id': pid,
                    'name': project_data.get('name', ''),
                    'description': project_data.get('description', ''),
                    'source': 'api'  # 标记配置来源
                }
                
                # 提取所有配置项到配置字典
                for section in sys_config.sections():
                    for key, value in sys_config.items(section):
                        config_dict[f'{section}_{key}'] = value
                
                return config_dict
            else:
                util.log(2, f"API错误: {result.get('message', '未知错误')}")
        else:
            util.log(2, f"API请求失败: HTTP状态码 {response.status_code}")
    except Exception as e:
        util.log(2, f"从API加载配置时出错: {str(e)}")
    
    return None

@synchronized
def load_config():
    """
    加载配置文件，如果本地文件不存在则直接使用API加载
    
    Returns:
        包含配置信息的字典
    """
    global config
    global system_config
    global key_ali_nls_key_id
    global key_ali_nls_key_secret
    global key_ali_nls_app_key
    global key_ms_tts_key
    global key_ms_tts_region
    global baidu_emotion_app_id
    global baidu_emotion_secret_key
    global baidu_emotion_api_key
    global key_gpt_api_key
    global gpt_model_engine
    global proxy_config
    global ASR_mode
    global local_asr_ip 
    global local_asr_port
    global ltp_mode 
    global gpt_base_url
    global tts_module
    global key_ali_tss_key_id
    global key_ali_tss_key_secret
    global key_ali_tss_app_key
    global volcano_tts_appid
    global volcano_tts_access_token
    global volcano_tts_cluster
    global volcano_tts_voice_type
    global start_mode
    global fay_url

    global CONFIG_SERVER
    global system_conf_path
    global config_json_path

    # 构建system.conf和config.json的完整路径
    if system_conf_path is None or config_json_path is None:
        system_conf_path = os.path.join(os.getcwd(), 'system.conf')
        config_json_path = os.path.join(os.getcwd(), 'config.json')
    
    sys_conf_exists = os.path.exists(system_conf_path)
    config_json_exists = os.path.exists(config_json_path)
    
    # 如果任一本地文件不存在，直接尝试从API加载
    if not sys_conf_exists or not config_json_exists:
        
        # 使用提取的项目ID或全局项目ID
        util.log(1, f"本地配置文件不完整（{system_conf_path if not sys_conf_exists else ''}{'和' if not sys_conf_exists and not config_json_exists else ''}{config_json_path if not config_json_exists else ''}不存在），尝试从API加载配置...")
        api_config = load_config_from_api(CONFIG_SERVER['PROJECT_ID'])
        
        if api_config:
            util.log(1, "成功从配置中心加载配置")
            system_config = api_config['system_config']
            config = api_config['config']

            # 缓存API配置到本地文件
            system_conf_path = os.path.join(os.getcwd(), 'cache_data', 'system.conf')
            config_json_path = os.path.join(os.getcwd(), 'cache_data', 'config.json')
            save_api_config_to_local(api_config, system_conf_path, config_json_path)
            
    # 如果本地文件存在，从本地文件加载
    # 加载system.conf
    system_config = ConfigParser()
    system_config.read(system_conf_path, encoding='UTF-8')
    
    # 从system.conf中读取所有配置项
    key_ali_nls_key_id = system_config.get('key', 'ali_nls_key_id', fallback=None)
    key_ali_nls_key_secret = system_config.get('key', 'ali_nls_key_secret', fallback=None)
    key_ali_nls_app_key = system_config.get('key', 'ali_nls_app_key', fallback=None)
    key_ali_tss_key_id = system_config.get('key', 'ali_tss_key_id', fallback=None)
    key_ali_tss_key_secret = system_config.get('key', 'ali_tss_key_secret', fallback=None)
    key_ali_tss_app_key = system_config.get('key', 'ali_tss_app_key', fallback=None)
    key_ms_tts_key = system_config.get('key', 'ms_tts_key', fallback=None)
    key_ms_tts_region  = system_config.get('key', 'ms_tts_region', fallback=None)
    baidu_emotion_app_id = system_config.get('key', 'baidu_emotion_app_id', fallback=None)
    baidu_emotion_api_key = system_config.get('key', 'baidu_emotion_api_key', fallback=None)
    baidu_emotion_secret_key = system_config.get('key', 'baidu_emotion_secret_key', fallback=None)
    key_gpt_api_key = system_config.get('key', 'gpt_api_key', fallback=None)
    gpt_model_engine = system_config.get('key', 'gpt_model_engine', fallback=None)
    ASR_mode = system_config.get('key', 'ASR_mode', fallback=None)
    local_asr_ip = system_config.get('key', 'local_asr_ip', fallback=None)
    local_asr_port = system_config.get('key', 'local_asr_port', fallback=None)
    proxy_config = system_config.get('key', 'proxy_config', fallback=None)
    ltp_mode = system_config.get('key', 'ltp_mode', fallback=None)
    gpt_base_url = system_config.get('key', 'gpt_base_url', fallback=None)
    tts_module = system_config.get('key', 'tts_module', fallback=None)
    volcano_tts_appid = system_config.get('key', 'volcano_tts_appid', fallback=None)
    volcano_tts_access_token = system_config.get('key', 'volcano_tts_access_token', fallback=None)
    volcano_tts_cluster = system_config.get('key', 'volcano_tts_cluster', fallback=None)
    volcano_tts_voice_type = system_config.get('key', 'volcano_tts_voice_type', fallback=None)

    start_mode = system_config.get('key', 'start_mode', fallback=None)
    fay_url = system_config.get('key', 'fay_url', fallback=None)
    # 如果fay_url为空或None，则动态获取本机IP地址
    if not fay_url:
        from utils.util import get_local_ip
        local_ip = get_local_ip()
        fay_url = f"http://{local_ip}:5000"
        # 更新system_config中的值，但不写入文件
        if not system_config.has_section('key'):
            system_config.add_section('key')
        system_config.set('key', 'fay_url', fay_url)
    
    # 读取用户配置
    with codecs.open(config_json_path, encoding='utf-8') as f:
        config = json.load(f)
    
    # 构建配置字典
    config_dict = {
        'system_config': system_config,
        'config': config,
        'ali_nls_key_id': key_ali_nls_key_id,
        'ali_nls_key_secret': key_ali_nls_key_secret,
        'ali_nls_app_key': key_ali_nls_app_key,
        'ms_tts_key': key_ms_tts_key,
        'ms_tts_region': key_ms_tts_region,
        'baidu_emotion_app_id': baidu_emotion_app_id,
        'baidu_emotion_api_key': baidu_emotion_api_key,
        'baidu_emotion_secret_key': baidu_emotion_secret_key,
        'gpt_api_key': key_gpt_api_key,
        'gpt_model_engine': gpt_model_engine,
        'ASR_mode': ASR_mode,
        'local_asr_ip': local_asr_ip,
        'local_asr_port': local_asr_port,
        'proxy_config': proxy_config,
        'ltp_mode': ltp_mode,

        'gpt_base_url': gpt_base_url,
        'tts_module': tts_module,
        'ali_tss_key_id': key_ali_tss_key_id,
        'ali_tss_key_secret': key_ali_tss_key_secret,
        'ali_tss_app_key': key_ali_tss_app_key,
        'volcano_tts_appid': volcano_tts_appid,
        'volcano_tts_access_token': volcano_tts_access_token,
        'volcano_tts_cluster': volcano_tts_cluster,
        'volcano_tts_voice_type': volcano_tts_voice_type,

        'start_mode': start_mode,
        'fay_url': fay_url,
        'source': 'local'  # 标记配置来源
    }
    
    return config_dict

def save_api_config_to_local(api_config, system_conf_path, config_json_path):
    """
    将API加载的配置保存到本地文件
    
    Args:
        api_config: API加载的配置字典
        system_conf_path: system.conf文件路径
        config_json_path: config.json文件路径
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(system_conf_path), exist_ok=True)
        os.makedirs(os.path.dirname(config_json_path), exist_ok=True)
        
        # 保存system.conf
        with open(system_conf_path, 'w', encoding='utf-8') as f:
            api_config['system_config'].write(f)
        
        # 保存config.json
        with codecs.open(config_json_path, 'w', encoding='utf-8') as f:
            json.dump(api_config['config'], f, ensure_ascii=False, indent=4)
            
        util.log(1, f"已将配置中心配置缓存到本地文件: {system_conf_path} 和 {config_json_path}")
    except Exception as e:
        util.log(2, f"保存配置中心配置缓存到本地文件时出错: {str(e)}")

@synchronized
def save_config(config_data):
    """
    保存配置到config.json文件
    
    Args:
        config_data: 要保存的配置数据
        config_dir: 配置文件目录，如果为None则使用当前目录
    """
    global config
    global config_json_path
    
    config = config_data
    
    # 保存到文件
    with codecs.open(config_json_path, mode='w', encoding='utf-8') as file:
        file.write(json.dumps(config_data, sort_keys=True, indent=4, separators=(',', ': ')))

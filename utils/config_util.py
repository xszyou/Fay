import os
import json
import codecs
import requests
from configparser import ConfigParser
import functools
from threading import Lock
import threading
from utils import util

# 条件导入 langsmith
try:
    # 检查是否有相关环境变量或包可用
    langsmith_env_vars = ['LANGCHAIN_API_KEY', 'LANGSMITH_API_KEY', 'LANGCHAIN_TRACING_V2']
    has_langsmith_env = any(os.getenv(var) for var in langsmith_env_vars)
    
    if has_langsmith_env:
        from langsmith.schemas import Feedback
        util.log(1, "检测到 LangSmith 环境变量，已导入 langsmith.schemas.Feedback")
    else:
        # 尝试导入以检查包是否可用
        import langsmith.schemas
        from langsmith.schemas import Feedback
        util.log(1, "langsmith 包可用，已导入 langsmith.schemas.Feedback")
except ImportError:
    # langsmith 包不可用，定义一个占位符类
    class Feedback:
        """langsmith 不可用时的占位符类"""
        pass
    util.log(2, "langsmith 包不可用，使用占位符类。如需使用 LangSmith 功能，请安装: pip install langsmith")
except Exception as e:
    # 其他导入错误
    class Feedback:
        """langsmith 导入失败时的占位符类"""
        pass
    util.log(2, f"langsmith 导入失败: {str(e)}，使用占位符类")

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
use_bionic_memory = None

# Embedding API 配置全局变量
embedding_api_model = None
embedding_api_base_url = None
embedding_api_key = None

SYSTEM_CONFIG_ENV_KEY = 'FAY_SYSTEM_CONF_JSON'

# 避免重复加载配置中心导致日志刷屏
_last_loaded_project_id = None
_last_loaded_config = None
_last_loaded_from_api = False  # 表示上次加载来自配置中心（含缓存）
_bootstrap_loaded_from_api = False  # 无本地配置时启动阶段已从配置中心加载过
_warned_public_config_keys = set()

# Public config center identifiers (warn users if matched)
PUBLIC_CONFIG_PROJECT_ID = 'd19f7b0a-2b8a-4503-8c0d-1a587b90eb69'
PUBLIC_CONFIG_BASE_URL = 'http://1.12.69.110:5500'


def _public_config_warn_key():
    base_url = (CONFIG_SERVER.get('BASE_URL') or '').rstrip('/')
    public_base = PUBLIC_CONFIG_BASE_URL.rstrip('/')
    if base_url == public_base:
        return f"base_url:{base_url}"
    if CONFIG_SERVER.get('PROJECT_ID') == PUBLIC_CONFIG_PROJECT_ID:
        return f"project_id:{CONFIG_SERVER.get('PROJECT_ID')}"
    return None


def _warn_public_config_once():
    key = _public_config_warn_key()
    if not key or key in _warned_public_config_keys:
        return
    _warned_public_config_keys.add(key)
    print("\033[1;33;41m警告：你正在使用社区公共配置,请尽快更换！\033[0m")

# config server中心配置，system.conf与config.json存在时不会使用配置中心
CONFIG_SERVER = {
    'BASE_URL': 'http://1.12.69.110:5500',  # 默认API服务器地址
    'API_KEY': 'your-api-key-here',       # 默认API密钥
    'PROJECT_ID': 'd19f7b0a-2b8a-4503-8c0d-1a587b90eb69'   # 项目ID，需要在使用前设置
}

def _refresh_config_center():
    env_project_id = os.getenv('FAY_CONFIG_CENTER_ID')
    if env_project_id:
        CONFIG_SERVER['PROJECT_ID'] = env_project_id

_refresh_config_center()


def _config_parser_to_dict(parser):
    data = {}
    if parser is None:
        return data
    for section in parser.sections():
        data[section] = {}
        for key, value in parser.items(section):
            data[section][key] = value
    return data


def _dict_to_config_parser(data):
    parser = ConfigParser()
    if not isinstance(data, dict):
        return parser
    for section, items in data.items():
        if not isinstance(items, dict):
            continue
        if not parser.has_section(section):
            parser.add_section(section)
        for key, value in items.items():
            parser.set(section, str(key), '' if value is None else str(value))
    return parser


def _save_system_config_to_env(parser, project_id=None, source='local'):
    if parser is None:
        return
    payload = {
        'meta': {
            'project_id': project_id,
            'source': source,
        },
        'sections': _config_parser_to_dict(parser),
    }
    try:
        os.environ[SYSTEM_CONFIG_ENV_KEY] = json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        util.log(2, f"save system.conf to env failed: {str(e)}")


def _load_system_config_from_env(expected_project_id=None):
    raw_value = os.getenv(SYSTEM_CONFIG_ENV_KEY)
    if not raw_value:
        return None

    try:
        payload = json.loads(raw_value)
        meta = {}
        sections = payload
        if isinstance(payload, dict) and isinstance(payload.get('sections'), dict):
            meta = payload.get('meta') or {}
            sections = payload.get('sections') or {}

        env_project_id = meta.get('project_id')
        if expected_project_id and env_project_id != expected_project_id:
            return None

        parser = _dict_to_config_parser(sections)
        if parser.sections():
            return parser
    except Exception as e:
        util.log(2, f"load system.conf from env failed: {str(e)}")

    return None

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
def load_config(force_reload=False):
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
    global use_bionic_memory
    global embedding_api_model
    global embedding_api_base_url
    global embedding_api_key

    global CONFIG_SERVER
    global system_conf_path
    global config_json_path
    global _last_loaded_project_id
    global _last_loaded_config
    global _last_loaded_from_api
    global _bootstrap_loaded_from_api

    _refresh_config_center()

    env_project_id = os.getenv('FAY_CONFIG_CENTER_ID')
    explicit_config_center = bool(env_project_id)
    using_config_center = explicit_config_center
    env_system_config = None if force_reload else _load_system_config_from_env(
        expected_project_id=env_project_id if explicit_config_center else None
    )
    if (
        env_project_id
        and not force_reload
        and _last_loaded_config is not None
        and _last_loaded_project_id == env_project_id
        and _last_loaded_from_api
    ):
        return _last_loaded_config

    default_system_conf_path = os.path.join(os.getcwd(), 'system.conf')
    default_config_json_path = os.path.join(os.getcwd(), 'config.json')
    cache_system_conf_path = os.path.join(os.getcwd(), 'cache_data', 'system.conf')
    cache_config_json_path = os.path.join(os.getcwd(), 'cache_data', 'config.json')
    root_system_conf_exists = env_system_config is not None or os.path.exists(default_system_conf_path)
    root_config_json_exists = os.path.exists(default_config_json_path)
    root_config_complete = root_system_conf_exists and root_config_json_exists

    # 构建system.conf和config.json相关路径.
    config_center_fallback = False
    if using_config_center:
        system_conf_path = cache_system_conf_path
        config_json_path = cache_config_json_path
    else:
        if (
            system_conf_path is None
            or config_json_path is None
            or system_conf_path == cache_system_conf_path
            or config_json_path == cache_config_json_path
        ):
            system_conf_path = default_system_conf_path
            config_json_path = default_config_json_path

        if not root_config_complete:
            cache_ready = (env_system_config is not None or os.path.exists(cache_system_conf_path)) and os.path.exists(cache_config_json_path)
            if (not _bootstrap_loaded_from_api) or (not cache_ready):
                using_config_center = True
                config_center_fallback = True
                system_conf_path = cache_system_conf_path
                config_json_path = cache_config_json_path
            else:
                system_conf_path = cache_system_conf_path
                config_json_path = cache_config_json_path

    forced_loaded = False
    loaded_from_api = False
    api_attempted = False
    if using_config_center:
        if explicit_config_center:
            util.log(1, f"检测到配置中心参数，优先加载项目配置: {CONFIG_SERVER['PROJECT_ID']}")
        else:
            util.log(1, f"未检测到本地system.conf或config.json，尝试从配置中心加载配置: {CONFIG_SERVER['PROJECT_ID']}")
        api_config = load_config_from_api(CONFIG_SERVER['PROJECT_ID'])
        api_attempted = True
        if api_config:
            util.log(1, "成功从配置中心加载配置")
            system_config = api_config['system_config']
            env_system_config = system_config
            _save_system_config_to_env(system_config, project_id=CONFIG_SERVER['PROJECT_ID'], source='api')
            config = api_config['config']
            loaded_from_api = True
            if config_center_fallback:
                _bootstrap_loaded_from_api = True

            # 将配置中心配置缓存到本地文件.
            system_conf_path = cache_system_conf_path
            config_json_path = cache_config_json_path
            save_api_config_to_local(
                api_config,
                system_conf_path,
                config_json_path,
                save_config_json=not os.path.exists(config_json_path),
                save_system_conf=False
            )
            forced_loaded = True

            _warn_public_config_once()
        else:
            util.log(2, "配置中心加载失败，尝试使用缓存配置")

    sys_conf_exists = env_system_config is not None or os.path.exists(system_conf_path)
    config_json_exists = os.path.exists(config_json_path)
    
    # 如果任一本地文件不存在，直接尝试从API加载
    if (not sys_conf_exists or not config_json_exists) and not forced_loaded:
        if using_config_center:
            if not api_attempted:
                util.log(1, "配置中心缓存缺失，尝试从配置中心加载配置...")
                api_config = load_config_from_api(CONFIG_SERVER['PROJECT_ID'])
                api_attempted = True
                if api_config:
                    util.log(1, "成功从配置中心加载配置")
                    system_config = api_config['system_config']
                    env_system_config = system_config
                    _save_system_config_to_env(system_config, project_id=CONFIG_SERVER['PROJECT_ID'], source='api')
                    config = api_config['config']
                    loaded_from_api = True
                    if config_center_fallback:
                        _bootstrap_loaded_from_api = True

                    # 将配置中心配置缓存到本地文件.
                    system_conf_path = cache_system_conf_path
                    config_json_path = cache_config_json_path
                    save_api_config_to_local(
                        api_config,
                        system_conf_path,
                        config_json_path,
                        save_config_json=not os.path.exists(config_json_path),
                        save_system_conf=False
                    )

                    _warn_public_config_once()
        else:
            # 使用项目配置或全局项目配置作为回退来源.
            util.log(1, f"本地配置文件不完整，尝试从API加载配置...")
            api_config = load_config_from_api(CONFIG_SERVER['PROJECT_ID'])

            if api_config:
                util.log(1, "成功从配置中心加载配置")
                system_config = api_config['system_config']
                env_system_config = system_config
                _save_system_config_to_env(system_config, project_id=CONFIG_SERVER['PROJECT_ID'], source='api')
                config = api_config['config']
                loaded_from_api = True

                # 将配置中心配置缓存到本地文件.
                system_conf_path = cache_system_conf_path
                config_json_path = cache_config_json_path
                save_api_config_to_local(
                    api_config,
                    system_conf_path,
                    config_json_path,
                    save_config_json=not os.path.exists(config_json_path),
                    save_system_conf=False
                )

                _warn_public_config_once()

    sys_conf_exists = env_system_config is not None or os.path.exists(system_conf_path)
    config_json_exists = os.path.exists(config_json_path)
    if using_config_center and (not sys_conf_exists or not config_json_exists):
        if _last_loaded_config is not None and _last_loaded_from_api:
            util.log(2, "配置中心缓存不可用，继续使用内存中的配置")
            return _last_loaded_config
    if config_center_fallback and using_config_center and (not sys_conf_exists or not config_json_exists):
        cache_ready = (env_system_config is not None or os.path.exists(cache_system_conf_path)) and os.path.exists(cache_config_json_path)
        if cache_ready:
            util.log(2, "配置中心不可用，回退使用缓存配置")
            using_config_center = False
            system_conf_path = cache_system_conf_path
            config_json_path = cache_config_json_path
        else:
            util.log(2, "配置中心不可用，回退使用本地配置文件")
            using_config_center = False
            system_conf_path = default_system_conf_path
            config_json_path = default_config_json_path
        sys_conf_exists = env_system_config is not None or os.path.exists(system_conf_path)
        config_json_exists = os.path.exists(config_json_path)
    # 如果本地文件存在，从本地文件加载
    # 加载system.conf
    if env_system_config is not None:
        system_config = env_system_config
    else:
        system_config = ConfigParser()
        if os.path.exists(system_conf_path):
            system_config.read(system_conf_path, encoding='UTF-8')
            _save_system_config_to_env(
                system_config,
                project_id=CONFIG_SERVER['PROJECT_ID'] if using_config_center else None,
                source='api' if using_config_center else 'local'
            )

    if not system_config.has_section('key'):
        system_config.add_section('key')
    
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

    # 读取 Embedding API 配置（复用 LLM 的 url 和 key）
    embedding_api_model = system_config.get('key', 'embedding_api_model', fallback='BAAI/bge-large-zh-v1.5')
    embedding_api_base_url = gpt_base_url  # 复用 LLM base_url
    embedding_api_key = key_gpt_api_key  # 复用 LLM api_key

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
        _save_system_config_to_env(
            system_config,
            project_id=CONFIG_SERVER['PROJECT_ID'] if using_config_center else None,
            source='api' if using_config_center else 'local'
        )
    
    # 读取用户配置
    with codecs.open(config_json_path, encoding='utf-8') as f:
        config = json.load(f)

    # 读取仿生记忆配置
    use_bionic_memory = config.get('memory', {}).get('use_bionic_memory', False)

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
        'use_bionic_memory': use_bionic_memory,

        # Embedding API 配置
        'embedding_api_model': embedding_api_model,
        'embedding_api_base_url': embedding_api_base_url,
        'embedding_api_key': embedding_api_key,

        'source': 'api' if using_config_center else 'local'  # 标记配置来源
    }

    _last_loaded_project_id = CONFIG_SERVER['PROJECT_ID'] if using_config_center else None
    _last_loaded_config = config_dict
    _last_loaded_from_api = using_config_center
    
    return config_dict

def save_api_config_to_local(api_config, system_conf_path, config_json_path, save_config_json=True, save_system_conf=False):
    """
    Persist API config to local files.
    
    Args:
        api_config: API response dict.
        system_conf_path: Path to system.conf.
        config_json_path: Path to config.json.
        save_config_json: Whether to write config.json.
    """
    try:
    # 确保目录存在.
        if save_system_conf and system_conf_path:
            os.makedirs(os.path.dirname(system_conf_path), exist_ok=True)
        os.makedirs(os.path.dirname(config_json_path), exist_ok=True)
        
        # 始终刷新 system.conf.
        if save_system_conf and system_conf_path:
            with open(system_conf_path, 'w', encoding='utf-8') as f:
                api_config['system_config'].write(f)
        
        # 默认只在首次下载时保存config.json.
        if save_config_json:
            with codecs.open(config_json_path, 'w', encoding='utf-8') as f:
                json.dump(api_config['config'], f, ensure_ascii=False, indent=4)
        if save_system_conf and system_conf_path:
            util.log(1, f"cached config center files to local: {system_conf_path}, {config_json_path}")
            return
        if save_config_json:
            util.log(1, f"cached config center config.json to local: {config_json_path}")
            return
        return
            
        util.log(1, f"已将配置中心配置缓存到本地文件: {system_conf_path} 和 {config_json_path}")
    except Exception as e:
        util.log(2, f"保存配置中心配置到本地文件时出错: {str(e)}")

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

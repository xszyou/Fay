from pathlib import Path
import sys
import os

# 添加项目根目录到系统路径
BASE_DIR = f"{Path(__file__).resolve().parent.parent}"
sys.path.append(BASE_DIR)

# 导入配置工具
from utils import config_util as cfg

# 确保配置已加载
cfg.load_config()

# 调试模式开关
DEBUG = False

# 从system.conf读取配置
OPENAI_API_KEY = cfg.key_gpt_api_key
OPENAI_API_BASE = cfg.gpt_base_url

MAX_CHUNK_SIZE = 4

# 使用system.conf中的模型配置
LLM_VERS = cfg.gpt_model_engine

## To do: Are the following needed in the new structure? Ideally Populations_Dir is for the user to define.
POPULATIONS_DIR = f"{BASE_DIR}/agent_bank/populations" 
LLM_PROMPT_DIR = f"{BASE_DIR}/simulation_engine/prompt_template" 
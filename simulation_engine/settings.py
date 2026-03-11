from pathlib import Path
import sys
import os


def _resolve_base_dir():
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS).resolve()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = str(_resolve_base_dir())
sys.path.append(BASE_DIR)

from utils import config_util as cfg

cfg.load_config()

DEBUG = False

OPENAI_API_KEY = cfg.key_gpt_api_key
OPENAI_API_BASE = cfg.gpt_base_url

MAX_CHUNK_SIZE = 4

LLM_VERS = cfg.gpt_model_engine

POPULATIONS_DIR = os.path.join(BASE_DIR, "agent_bank", "populations")
LLM_PROMPT_DIR = os.path.join(BASE_DIR, "simulation_engine", "prompt_template")

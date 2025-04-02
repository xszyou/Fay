from pathlib import Path

OPENAI_API_KEY = "sk-hAuN7OLqKJTdyDjNFdEfF4B0E53642E4B2BbCa248594Cd29"
OPENAI_API_BASE = "https://api.zyai.online/v1"  # 可以修改为你的自定义 base URL
KEY_OWNER = "xszyou"


DEBUG = False

MAX_CHUNK_SIZE = 4

LLM_VERS = "gpt-4o-mini"

BASE_DIR = f"{Path(__file__).resolve().parent.parent}"

## To do: Are the following needed in the new structure? Ideally Populations_Dir is for the user to define.
POPULATIONS_DIR = f"{BASE_DIR}/agent_bank/populations" 
LLM_PROMPT_DIR = f"{BASE_DIR}/simulation_engine/prompt_template"
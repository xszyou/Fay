import os
import json
import codecs
from configparser import ConfigParser

config: json = None
system_config: ConfigParser = None
key_ali_nls_key_id = None
key_ali_nls_key_secret = None
key_ali_nls_app_key = None
key_ngrok_cc_id = None
key_gpt_api_key = None
key_gpt_tts_key = None
gpt_base_url = None
gpt_tts_base_url = None
ASR_mode = None
local_asr_ip = None 
local_asr_port = None 
gpt_model_engine = None
tavily_api_key = None
key_ms_tts_key = None
key_ms_tts_region = None
tts_module = None
proxy_config = None

def load_config():
    global config
    global system_config
    global key_ali_nls_key_id
    global key_ali_nls_key_secret
    global key_ali_nls_app_key
    global key_ngrok_cc_id
    global key_gpt_api_key
    global key_gpt_tts_key
    global gpt_base_url
    global gpt_tts_base_url
    global key_ms_tts_key
    global key_ms_tts_region
    global tts_module
    global tavily_api_key
    global ASR_mode
    global local_asr_ip 
    global local_asr_port
    global proxy_config
    global gpt_model_engine

    system_config = ConfigParser()
    system_config.read('system.conf', encoding='UTF-8')
    key_ali_nls_key_id = system_config.get('key', 'ali_nls_key_id')
    key_ali_nls_key_secret = system_config.get('key', 'ali_nls_key_secret')
    key_ali_nls_app_key = system_config.get('key', 'ali_nls_app_key')
    key_ngrok_cc_id = system_config.get('key', 'ngrok_cc_id')
    key_gpt_api_key = system_config.get('key', 'gpt_api_key')
    key_gpt_tts_key = system_config.get('key', 'gpt_tts_key')
    gpt_base_url = system_config.get('key', 'gpt_base_url')
    gpt_tts_base_url = system_config.get('key', 'gpt_tts_base_url')
    key_ms_tts_key = system_config.get('key', 'ms_tts_key')
    key_ms_tts_region  = system_config.get('key', 'ms_tts_region')
    tts_module  = system_config.get('key', 'tts_module')
    ASR_mode = system_config.get('key', 'ASR_mode')
    local_asr_ip = system_config.get('key', 'local_asr_ip')
    local_asr_port = system_config.get('key', 'local_asr_port')
    proxy_config = system_config.get('key', 'proxy_config')
    gpt_model_engine = system_config.get('key', 'gpt_model_engine')
    tavily_api_key = system_config.get('key', 'tavily_api_key')
    config = json.load(codecs.open('config.json', encoding='utf-8'))

def save_config(config_data):
    global config
    config = config_data
    file = codecs.open('config.json', mode='w', encoding='utf-8')
    file.write(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))
    file.close()
    # for line in json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')).split("\n"):
    #     print(line)

import os
import json
import codecs
from configparser import ConfigParser

config: json = None
system_config: ConfigParser = None
system_chrome_driver = None
key_ali_nls_key_id = None
key_ali_nls_key_secret = None
key_ali_nls_app_key = None
key_ms_tts_key = None
Key_ms_tts_region = None
key_xf_ltp_app_id = None
key_xf_ltp_api_key = None
key_ngrok_cc_id = None
key_yuan_1_0_account = None
key_yuan_1_0_phone = None
key_chatgpt_api_key = None
key_chat_module = None
proxy_config = None
ASR_mode = None
local_asr_ip = None 
local_asr_port = None 
ltp_mode = None
key_fast_api_key = None
is_proxy = None

def load_config():
    global config
    global system_config
    global key_ali_nls_key_id
    global key_ali_nls_key_secret
    global key_ali_nls_app_key
    global key_ms_tts_key
    global key_ms_tts_region
    global key_xf_ltp_app_id
    global key_xf_ltp_api_key
    global key_ngrok_cc_id
    global key_yuan_1_0_account
    global key_yuan_1_0_phone
    global key_chatgpt_api_key
    global key_chat_module
    global key_lingju_api_key
    global key_lingju_api_authcode
    global proxy_config
    global ASR_mode
    global local_asr_ip 
    global local_asr_port
    global ltp_mode 
    global key_fast_gpt_key
    global is_proxy

    system_config = ConfigParser()
    system_config.read('system.conf', encoding='UTF-8')
    key_ali_nls_key_id = system_config.get('key', 'ali_nls_key_id')
    key_ali_nls_key_secret = system_config.get('key', 'ali_nls_key_secret')
    key_ali_nls_app_key = system_config.get('key', 'ali_nls_app_key')
    key_ms_tts_key = system_config.get('key', 'ms_tts_key')
    key_ms_tts_region  = system_config.get('key', 'ms_tts_region')
    key_xf_ltp_app_id = system_config.get('key', 'xf_ltp_app_id')
    key_xf_ltp_api_key = system_config.get('key', 'xf_ltp_api_key')
    key_ngrok_cc_id = system_config.get('key', 'ngrok_cc_id')
    key_yuan_1_0_account = system_config.get('key', 'yuan_1_0_account')
    key_yuan_1_0_phone = system_config.get('key', 'yuan_1_0_phone')
    key_chatgpt_api_key = system_config.get('key', 'chatgpt_api_key')
    key_chat_module = system_config.get('key', 'chat_module')
    key_lingju_api_key = system_config.get('key', 'lingju_api_key')
    key_lingju_api_authcode = system_config.get('key', 'lingju_api_authcode')
    ASR_mode = system_config.get('key', 'ASR_mode')
    local_asr_ip = system_config.get('key', 'local_asr_ip')
    local_asr_port = system_config.get('key', 'local_asr_port')
    proxy_config = system_config.get('key', 'proxy_config')
    is_proxy = system_config.get('key', 'is_proxy')
    ltp_mode = system_config.get('key', 'ltp_mode')
    key_fast_gpt_key = system_config.get('key', 'fast_gpt_key')
    config = json.load(codecs.open('config.json', encoding='utf-8'))

def save_config(config_data):
    global config
    config = config_data
    file = codecs.open('config.json', mode='w', encoding='utf-8')
    file.write(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))
    file.close()
    # for line in json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')).split("\n"):
    #     print(line)

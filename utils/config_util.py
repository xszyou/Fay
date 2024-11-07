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
baidu_emotion_app_id = None
baidu_emotion_api_key = None
baidu_emotion_secret_key = None
key_gpt_api_key = None
key_chat_module = None
gpt_model_engine = None
proxy_config = None
ASR_mode = None
local_asr_ip = None 
local_asr_port = None 
ltp_mode = None
key_xingchen_api_key = None
xingchen_characterid = None
gpt_base_url = None
ollama_ip = None
ollama_model = None
tts_module = None
key_ali_tss_key_id = None
key_ali_tss_key_secret = None
key_ali_tss_app_key = None
volcano_tts_appid = None
volcano_tts_access_token = None
volcano_tts_cluster = None
volcano_tts_voice_type = None
coze_bot_id = None
coze_api_key = None
start_mode = None
fay_url = None

def load_config():
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
    global key_chat_module
    global key_lingju_api_key
    global key_lingju_api_authcode
    global proxy_config
    global ASR_mode
    global local_asr_ip 
    global local_asr_port
    global ltp_mode 
    global key_xingchen_api_key
    global xingchen_characterid
    global gpt_base_url
    global ollama_ip
    global ollama_model
    global tts_module
    global key_ali_tss_key_id
    global key_ali_tss_key_secret
    global key_ali_tss_app_key
    global volcano_tts_appid
    global volcano_tts_access_token
    global volcano_tts_cluster
    global volcano_tts_voice_type
    global coze_bot_id
    global coze_api_key
    global start_mode
    global fay_url

    system_config = ConfigParser()
    system_config.read('system.conf', encoding='UTF-8')
    key_ali_nls_key_id = system_config.get('key', 'ali_nls_key_id')
    key_ali_nls_key_secret = system_config.get('key', 'ali_nls_key_secret')
    key_ali_nls_app_key = system_config.get('key', 'ali_nls_app_key')
    key_ali_tss_key_id = system_config.get('key', 'ali_tss_key_id')
    key_ali_tss_key_secret = system_config.get('key', 'ali_tss_key_secret')
    key_ali_tss_app_key = system_config.get('key', 'ali_tss_app_key')
    key_ms_tts_key = system_config.get('key', 'ms_tts_key')
    key_ms_tts_region  = system_config.get('key', 'ms_tts_region')
    baidu_emotion_app_id = system_config.get('key', 'baidu_emotion_app_id')
    baidu_emotion_api_key = system_config.get('key', 'baidu_emotion_api_key')
    baidu_emotion_secret_key = system_config.get('key', 'baidu_emotion_secret_key')
    key_gpt_api_key = system_config.get('key', 'gpt_api_key')
    gpt_model_engine = system_config.get('key', 'gpt_model_engine')
    key_chat_module = system_config.get('key', 'chat_module')
    key_lingju_api_key = system_config.get('key', 'lingju_api_key')
    key_lingju_api_authcode = system_config.get('key', 'lingju_api_authcode')
    ASR_mode = system_config.get('key', 'ASR_mode')
    local_asr_ip = system_config.get('key', 'local_asr_ip')
    local_asr_port = system_config.get('key', 'local_asr_port')
    proxy_config = system_config.get('key', 'proxy_config')
    ltp_mode = system_config.get('key', 'ltp_mode')
    key_xingchen_api_key = system_config.get('key', 'xingchen_api_key')
    xingchen_characterid = system_config.get('key', 'xingchen_characterid')
    gpt_base_url = system_config.get('key', 'gpt_base_url')
    ollama_ip = system_config.get('key', 'ollama_ip')
    ollama_model = system_config.get('key', 'ollama_model')
    tts_module = system_config.get('key', 'tts_module')
    volcano_tts_appid = system_config.get('key', 'volcano_tts_appid')
    volcano_tts_access_token = system_config.get('key', 'volcano_tts_access_token')
    volcano_tts_cluster = system_config.get('key', 'volcano_tts_cluster')
    volcano_tts_voice_type = system_config.get('key', 'volcano_tts_voice_type')
    coze_bot_id = system_config.get('key', 'coze_bot_id')
    coze_api_key = system_config.get('key', 'coze_api_key')
    start_mode = system_config.get('key', 'start_mode')
    fay_url = system_config.get('key', 'fay_url')
    config = json.load(codecs.open('config.json', encoding='utf-8'))

def save_config(config_data):
    global config
    config = config_data
    file = codecs.open('config.json', mode='w', encoding='utf-8')
    file.write(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))
    file.close()
    load_config()
    # for line in json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')).split("\n"):
    #     print(line)

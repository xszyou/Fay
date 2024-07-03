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
key_ngrok_cc_id = None
key_gpt_api_key = None
gpt_base_url = None
gpt_model_engine = None
key_chat_module = None
ltp_mode = None
proxy_config = None
key_ali_tss_key_id = None
key_ali_tss_key_secret = None
key_ali_tss_app_key = None
tts_module = None


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
    global key_ngrok_cc_id
    global key_gpt_api_key
    global gpt_model_engine
    global gpt_base_url
    global key_chat_module
    global key_lingju_api_key
    global key_lingju_api_authcode
    global ltp_mode 
    global proxy_config
    global key_ali_tss_key_id
    global key_ali_tss_key_secret
    global key_ali_tss_app_key
    global tts_module



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
    key_ngrok_cc_id = system_config.get('key', 'ngrok_cc_id')
    gpt_model_engine = system_config.get('key', 'gpt_model_engine')
    gpt_base_url = system_config.get('key', 'gpt_base_url')
    key_gpt_api_key = system_config.get('key', 'gpt_api_key')
    key_chat_module = system_config.get('key', 'chat_module')
    key_lingju_api_key = system_config.get('key', 'lingju_api_key')
    key_lingju_api_authcode = system_config.get('key', 'lingju_api_authcode')
    ltp_mode = system_config.get('key', 'ltp_mode')
    tts_module = system_config.get('key', 'tts_module')
    proxy_config = system_config.get('key', 'proxy_config')

    config = json.load(codecs.open('config.json', encoding='utf-8'))


def save_config(config_data):
    global config
    config = config_data
    file = codecs.open('config.json', mode='w', encoding='utf-8')
    file.write(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))
    file.close()
    # for line in json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')).split("\n"):
    #     print(line)

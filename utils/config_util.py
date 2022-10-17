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
key_xf_aiui_app_id = None
key_xf_aiui_api_key = None
key_xf_ltp_app_id = None
key_xf_ltp_api_key = None

def load_config():
    global config
    global system_config
    global system_chrome_driver
    global key_ali_nls_key_id
    global key_ali_nls_key_secret
    global key_ali_nls_app_key
    global key_ms_tts_key
    global key_ms_tts_region
    global key_xf_aiui_app_id
    global key_xf_aiui_api_key
    global key_xf_ltp_app_id
    global key_xf_ltp_api_key

    system_config = ConfigParser()
    system_config.read('system.conf', encoding='UTF-8')
    system_chrome_driver = os.path.abspath(system_config.get('system', 'chrome_driver'))
    key_ali_nls_key_id = system_config.get('key', 'ali_nls_key_id')
    key_ali_nls_key_secret = system_config.get('key', 'ali_nls_key_secret')
    key_ali_nls_app_key = system_config.get('key', 'ali_nls_app_key')
    key_ms_tts_key = system_config.get('key', 'ms_tts_key')
    key_ms_tts_region  = system_config.get('key', 'ms_tts_region')
    key_xf_aiui_app_id = system_config.get('key', 'xf_aiui_app_id')
    key_xf_aiui_api_key = system_config.get('key', 'xf_aiui_api_key')
    key_xf_ltp_app_id = system_config.get('key', 'xf_ltp_app_id')
    key_xf_ltp_api_key = system_config.get('key', 'xf_ltp_api_key')

    config = json.load(codecs.open('config.json', encoding='utf-8'))


def save_config(config_data):
    global config
    config = config_data
    file = codecs.open('config.json', mode='w', encoding='utf-8')
    file.write(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))
    file.close()
    # for line in json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')).split("\n"):
    #     print(line)

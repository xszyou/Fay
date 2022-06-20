import time
import urllib.request
import urllib.parse
import json
import hashlib
import base64
from utils import config_util as cfg

__URL = "https://ltpapi.xfyun.cn/v2/sa"


def __quest(text):
    body = urllib.parse.urlencode({'text': text}).encode('utf-8')
    param = {"type": "dependent"}
    x_param = base64.b64encode(json.dumps(param).replace(' ', '').encode('utf-8'))
    x_time = str(int(time.time()))
    x_checksum = hashlib.md5(cfg.key_xf_ltp_api_key.encode('utf-8') + str(x_time).encode('utf-8') + x_param).hexdigest()
    x_header = {
        'X-Appid': cfg.key_xf_ltp_app_id,
        'X-CurTime': x_time,
        'X-Param': x_param,
        'X-CheckSum': x_checksum
    }
    req = urllib.request.Request(__URL, body, x_header)
    result = urllib.request.urlopen(req)
    result = result.read()
    return json.loads(result.decode('utf-8'))


"""
情感分析

:param text: 文本

:returns: 情感分数 (0.7以上为褒义, 0.3-0.7为中性 0.3以下为贬义,, -1为分析失败)
"""


def get_score(text):
    result = __quest(text)
    if result['desc'] == 'success':
        return float(result['data']['score'])
    return -1


"""
情感分析

:param text: 文本

:returns: 情感极性分类 (2为褒义, 1为中性 0为贬义,, -1为分析失败)
"""


def get_sentiment(text):
    result = __quest(text)
    if result['desc'] == 'success':
        return int(result['data']['sentiment']) + 1
    return -1

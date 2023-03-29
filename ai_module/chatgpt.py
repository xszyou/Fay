import json
import requests

from utils import config_util as cfg

def question(cont):
    url="https://api.openai.com/v1/chat/completions"
    req = json.dumps({
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": cont}],
        "temperature": 0.7})
    headers = {'content-type': 'application/json', 'Authorization': 'Bearer ' + cfg.key_chatgpt_api_key}
    r = requests.post(url, headers=headers, data=req)
    rsp = json.loads(r.text).get('choices')
    a = rsp[0]['message']['content']
    return a
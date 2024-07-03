import json
import requests
import time
from core.authorize_tb import Authorize_Tb
from utils import config_util as cfg
from utils import util

def get_sentiment(cont):
    emotion = Emotion()
    answer = emotion.get_sentiment(cont)
    return answer

class Emotion:

    def __init__(self):
        self.app_id = cfg.baidu_emotion_app_id
        self.authorize_tb = Authorize_Tb()

    def get_sentiment(self, cont):
        token = self.__check_token()
        if token is None or token == 'expired':
            token_info = self.__get_token()
            if token_info is not None and  token_info['access_token']  is not None:
                #转换过期时间
                updated_in_seconds = time.time()
                expires_timedelta = token_info['expires_in']
                expiry_timestamp_in_seconds = updated_in_seconds + expires_timedelta
                expiry_timestamp_in_milliseconds = expiry_timestamp_in_seconds * 1000
                if token == 'expired':
                    self.authorize_tb.update_by_userid(self.app_id, token_info['access_token'], expiry_timestamp_in_milliseconds)
                else:
                    self.authorize_tb.add(self.app_id, token_info['access_token'], expiry_timestamp_in_milliseconds)
                token = token_info['access_token']
            else:
                token = None
   
        if token is not None:
            try:
                url=f"https://aip.baidubce.com/rpc/2.0/nlp/v1/sentiment_classify?access_token={token}"
                req = json.dumps({"text": cont})
                headers = {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }                
                r = requests.post(url, headers=headers,  data=req)
                if r.status_code != 200:
                    util.log(1, f"百度情感分析对接有误: {r.text}")
                    return 0
                info = json.loads(r.text)
                if not self.has_field(info,'error_code'):
                    return info['items'][0]['sentiment']
                else:
                    util.log(1, f"百度情感分析对接有误： {info['error_msg']}") 
                    return 0
            except Exception as e:
                util.log(1, f"百度情感分析对接有误： {str(e)}")           
                return 0
        else:
            return 0

    def __check_token(self):
        self.authorize_tb.init_tb()
        info = self.authorize_tb.find_by_userid(self.app_id)
        if info is not None:
            if info[1] >= int(time.time())*1000:
                return info[0]
            else:
                return 'expired'
        else:
            return None 

    def __get_token(self):
        try:
            url=f"https://aip.baidubce.com/oauth/2.0/token?client_id={cfg.baidu_emotion_api_key}&client_secret={cfg.baidu_emotion_secret_key}&grant_type=client_credentials"            
            headers = {'Content-Type':'application/json;charset=UTF-8'}
            r = requests.post(url, headers=headers)    
            if r.status_code != 200:
                info = json.loads(r.text)
                if info["error"] == "invalid_client":
                    util.log(1, f"请检查baidu_emotion_api_key")
                else:
                    util.log(1, f"请检查baidu_emotion_secret_key")
                return None            
            info = json.loads(r.text)
            if not self.has_field(info,'error_code'):
                return info
            else:
                util.log(1, f"百度情感分析对接有误： {info['error_msg']}") 
                util.log(1, f"请检查baidu_emotion_api_key和baidu_emotion_secret_key") 
                return None
        except Exception as e:
            util.log(1, f"百度情感分析有1误： {str(e)}")
            return None

    
    def has_field(self, array, field):
        return any(field in item for item in array)
  


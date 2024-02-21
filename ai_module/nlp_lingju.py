import json
import requests
import uuid
from datetime import datetime, timedelta
import time
from utils import util
from utils import config_util as cfg
from core.authorize_tb import Authorize_Tb

def question(cont):
    lingju = Lingju()
    answer = lingju.question(cont)
    return answer

class Lingju:

    def __init__(self):
        self.userid = str(uuid.getnode())
        self.authorize_tb = Authorize_Tb()

    def question(self, cont):
        token = self.__check_token()
        if token is None or token == 'expired':
            token_info = self.__get_token()
            if token_info is not None and  token_info['data']['accessToken']  is not None:
                #转换过期时间
                updated_in_seconds = time.time()
                updated_datetime = datetime.fromtimestamp(updated_in_seconds)
                expires_timedelta = timedelta(days=token_info['data']['expires'])
                expiry_datetime = updated_datetime + expires_timedelta
                expiry_timestamp_in_seconds = expiry_datetime.timestamp()
                expiry_timestamp_in_milliseconds = int(expiry_timestamp_in_seconds) * 1000
                token = token_info['data']['accessToken']
                if token == 'expired':
                    self.authorize_tb.update_by_userid(self.userid, token_info['data']['accessToken'], expiry_timestamp_in_milliseconds)
                else:
                    self.authorize_tb.add(self.userid, token_info['data']['accessToken'], expiry_timestamp_in_milliseconds)
            else:
                token = None
   
        if token is not None:
            try:
                url="https://dev.lingju.ai/httpapi/ljchat.do"
                req = json.dumps({"accessToken": token,  "input": cont})
                headers = {'Content-Type':'application/json;charset=UTF-8'}
                r = requests.post(url, headers=headers,  data=req)
                if r.status_code != 200:
                    util.log(1, f"灵聚api对接有误: {r.text}")
                    return "哎呀，出错了！请重新发一下" 
                info = json.loads(r.text)
                if info['status'] != 0:
                    return info['description']
                else:
                    answer = json.loads(info['answer'])
                    return answer['rtext']
            except Exception as e:
                util.log(1, f"灵聚api对接有误： {str(e)}")           
                return "哎呀，出错了！请重新发一下" 

    def __check_token(self):
        self.authorize_tb.init_tb()
        info = self.authorize_tb.find_by_userid(self.userid)
        if info is not None:
            if info[1] >= int(time.time())*1000:
                return info[0]
            else:
                return 'expired'
        else:
            return None 

    def __get_token(self):
        try:
            cfg.load_config()
            url=f"https://dev.lingju.ai/httpapi/authorize.do?appkey={cfg.key_lingju_api_key}&userid={self.userid}&authcode={cfg.key_lingju_api_authcode}"            
            headers = {'Content-Type':'application/json;charset=UTF-8'}
            r = requests.post(url, headers=headers)    
            if r.status_code != 200:
                util.log(1, f"灵聚api对接有误: {r.text}")
                return None            
            info = json.loads(r.text)
            if info['status'] != 0:
                util.log(1, f"灵聚api对接有误：{info['description']}")
                return None
            else:
                return info
        except Exception as e:
            util.log(1, f"灵聚api对接有误： {str(e)}")
            return None

    def __get_location(self):
        try:
            response = requests.get('http://ip-api.com/json/')
            data = response.json()
            return data['lat'], data['lon'], data['city']
        except requests.exceptions.RequestException as e:
            util.log(1, f"获取位置失败: {str(e)}")           
            return 0, 0, "北京"
        


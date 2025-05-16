import http.client
import urllib.parse
import json
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from core.authorize_tb import Authorize_Tb
import time
from utils import util, config_util
from utils import config_util as cfg
import wave

class Speech:
    def __init__(self):
        self.key_ali_nls_key_id = cfg.key_ali_tss_key_id
        self.key_ali_nls_key_secret = cfg.key_ali_tss_key_secret
        self.ali_nls_app_key = cfg.key_ali_tss_app_key
        self.token = None
        self.authorize_tb = Authorize_Tb()
        self.__history_data = []

    def connect(self):
        pass

    def __get_history(self, voice_name, style, text):
        for data in self.__history_data:
            if data[0] == voice_name and data[1] == style and data[2] == text:
                return data[3]
        return None    

    def set_token(self):
        token = self.__check_token()
        if token is None or token == 'expired':
            token_info = self.__get_token()
            if token_info is not None and  token_info['Id']  is not None:
                expires_timedelta = token_info['ExpireTime']
                expiry_timestamp_in_milliseconds = expires_timedelta * 1000
                if token == 'expired':
                    self.authorize_tb.update_by_userid(self.key_ali_nls_key_id, token_info['Id'], expiry_timestamp_in_milliseconds)
                else:
                    self.authorize_tb.add(self.key_ali_nls_key_id, token_info['Id'], expiry_timestamp_in_milliseconds)
                token = token_info['Id']
            else:
                print(f"请检查阿里云tts对接")
                token = None
                
        self.token = token
    

    def __check_token(self):
        self.authorize_tb.init_tb()
        info = self.authorize_tb.find_by_userid(self.key_ali_nls_key_id)
        if info is not None:
            if info[1] >= int(time.time())*1000:
                return info[0]
            else:
                return 'expired'
        else:
            return None 

    def __get_token(self):
        try:
            global _token
            __client = AcsClient(
                self.key_ali_nls_key_id,
                self.key_ali_nls_key_secret,
                "cn-shanghai"
            )

            __request = CommonRequest()
            __request.set_method('POST')
            __request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')
            __request.set_version('2019-02-28')
            __request.set_action_name('CreateToken')
            info = json.loads(__client.do_action_with_exception(__request))
            _token = info['Token']
            return info['Token']
        except Exception as e:
            print(f"阿里云tts对接有误： {str(e)}")
            return None

    

    def to_sample(self, text, style) :
        file_url = None
        try:
            history = self.__get_history(config_util.config["attribute"]["voice"] if config_util.config["attribute"]["voice"] is not None and config_util.config["attribute"]["voice"].strip() != "" else "阿斌", style, text)
            if history is not None:
                return history
            self.set_token()
            if self.token != None:       
                host = 'nls-gateway-cn-shanghai.aliyuncs.com'
                url = 'https://' + host + '/stream/v1/tts'
                # 设置HTTPS Headers。
                httpHeaders = {
                    'Content-Type': 'application/json'
                    }
                # text = f"<speak>{text}</speak>"
                # 设置HTTPS Body。
                body = {'appkey': self.ali_nls_app_key, 'token': self.token,'speech_rate':0, 'text': text, 'format': 'mp3', 'sample_rate': 16000, 'voice': config_util.config["attribute"]["voice"]}
                body = json.dumps(body)
                conn = http.client.HTTPSConnection(host)
                conn.request(method='POST', url=url, body=body, headers=httpHeaders)
                # 处理服务端返回的响应。
                response = conn.getresponse()
                tt = time.time()
                contentType = response.getheader('Content-Type')
                body = response.read()
                if 'audio/mpeg' == contentType :
                    file_url = './samples/sample-' + str(int(time.time() * 1000)) + '.mp3'
                    with wave.open(file_url, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(16000)
                        wf.writeframes(body)
                
                else :
                    util.log(1, "[x] 语音转换失败！")
                    util.log(1, "[x] 原因: " + str(body))
                    file_url = None
                    return file_url
                conn.close() 
                return file_url
            else:
                util.log(1, "[x] 语音转换失败！")
                util.log(1, "[x] 原因: 对接有误" )
                file_url = None
                return file_url
        except Exception as e :
                util.log(1, "[x] 语音转换失败！")
                util.log(1, "[x] 原因: " + str(str(e)))
                file_url = None
                return file_url


    def close(self):
       pass



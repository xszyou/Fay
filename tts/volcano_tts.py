import base64
import json
import uuid
import requests
import time
from utils import util, config_util
from utils import config_util as cfg
import wave


class Speech:
    def __init__(self):
        self.appid = cfg.volcano_tts_appid
        self.access_token = cfg.volcano_tts_access_token
        self.cluster = cfg.volcano_tts_cluster
        self.__history_data = []

    def connect(self):
        pass

    def __get_history(self, voice_name, style, text):
        for data in self.__history_data:
            if data[0] == voice_name and data[1] == style and data[2] == text:
                return data[3]
        return None    

    def to_sample(self, text, style) :
        if cfg.volcano_tts_voice_type != None and cfg.volcano_tts_voice_type != '':
            voice = cfg.volcano_tts_voice_type
        else:
            voice = config_util.config["attribute"]["voice"] if config_util.config["attribute"]["voice"] is not None and config_util.config["attribute"]["voice"].strip() != "" else "爽快思思/Skye"
        try:
            history = self.__get_history(voice, style, text)
            if history is not None:
                return history           
            host = "openspeech.bytedance.com"
            api_url = f"https://{host}/api/v1/tts"
            header = {"Authorization": f"Bearer;{self.access_token}"}

            request_json = {
                "app": {
                    "appid": self.appid,
                    "token": "access_token",
                    "cluster": self.cluster
                },
                "user": {
                    "uid": "388808087185088"
                },
                "audio": {
                    "voice_type": voice,
                    "encoding": "wav",
                    "speed_ratio": 1.0,
                    "volume_ratio": 1.0,
                    "pitch_ratio": 1.0,
                },
                "request": {
                    "reqid": str(uuid.uuid4()),
                    "text": text,
                    "text_type": "plain",
                    "operation": "query",
                    "with_frontend": 1,
                    "frontend_type": "unitTson"

                }
            }
            response = requests.post(api_url, json.dumps(request_json), headers=header)
            if "data" in response.json():
                data = response.json()["data"]
                file_url = './samples/sample-' + str(int(time.time() * 1000)) + '.wav'
                with wave.open(file_url, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(base64.b64decode(data))
            else :
                util.log(1, "[x] 语音转换失败！")
                file_url = None
                return file_url
            return file_url
           
        except Exception as e :
                util.log(1, "[x] 语音转换失败！")
                util.log(1, "[x] 原因: " + str(str(e)))
                file_url = None
                return file_url


    def close(self):
       pass



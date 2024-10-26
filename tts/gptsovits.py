import requests
import time
from utils import util
import wave
class Speech:

    def connect(self):
        pass

   
    def close(self):
       pass

    def to_sample(self, text, style) :    
        url = "http://127.0.0.1:9880"
        data = {
        "text": text,
        "text_language": "zh",
        "cut_punc": "，。"
    }
        try:
            response = requests.post(url, json=data)
            file_url = './samples/sample-' + str(int(time.time() * 1000)) + '.wav'
            if response.status_code == 200:
                with wave.open(file_url, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(16000)
                        wf.writeframes(response.content)
                return file_url
            
            else:
                util.log(1, "[x] 语音转换失败！")
                util.log(1, "[x] 原因: " + str(response.text))
                return None
        
        except Exception as e :
                util.log(1, "[x] 语音转换失败！")
                util.log(1, "[x] 原因: " + str(str(e)))
                file_url = None
                return file_url
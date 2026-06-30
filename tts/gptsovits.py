import requests
import time
from utils import util
import wave
from gradio_client import Client
class Speech:

    def connect(self):
        pass

   
    def close(self):
       pass

    def to_sample(self, text, style) :    
        url = "http://127.0.0.1:9872"
        data = {
        "text": text,
        "text_language": "zh",
        "cut_punc": "，。"
    }
        try:
            client = Client(url)
            file_url = client.predict(
                "/Users/leosyzhang/sourcecode/ai/aivoice/GPT-SoVITS/ReferenceWav/四爷/说话-小桂子这一身的才华，去哪儿都会被埋没.wav",
                "小桂子这一身的才华，去哪儿都会被埋没",
                "Chinese",
                text,
                "Chinese",
                "No slice",
                1,
                0,
                0,
                True,
                fn_index=3
            )
            util.log(1, file_url)
            return file_url
        
        except Exception as e :
                util.log(1, "[x] 语音转换失败！")
                util.log(1, "[x] 原因: " + str(str(e)))
                file_url = None
                return file_url

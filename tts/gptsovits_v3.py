import requests
import time
from utils import util
import wave
class Speech:

    def __init__(self):
         pass

    def connect(self):
        pass

   
    def close(self):
       pass

    def to_sample(self, text, style) :    
        url = "http://127.0.0.1:9880/tts"
        data = {
        "text": text,                   # str.(required) text to be synthesized
        "text_lang": "zh",              # str.(required) language of the text to be synthesized
        "ref_audio_path": "I:/GPT-SoVITS-beta0706/111.wav",         # str.(required) reference audio path.
        "prompt_text": "抱歉，我现在太忙了，休息一会，请稍后再试。",            # str.(optional) prompt text for the reference audio
        "prompt_lang": "zh",            # str.(required) language of the prompt text for the reference audio
        "top_k": 5,                   # int.(optional) top k sampling
        "top_p": 1,                   # float.(optional) top p sampling
        "temperature": 1,             # float.(optional) temperature for sampling
        "text_split_method": "cut5",  # str.(optional) text split method, see text_segmentation_method.py for details.
        "batch_size": 1,              # int.(optional) batch size for inference
        "batch_threshold": 0.75,      # float.(optional) threshold for batch splitting.
        "split_bucket": True,         # bool.(optional) whether to split the batch into multiple buckets.
        "speed_factor":1.0,           # float.(optional) control the speed of the synthesized audio.
        "fragment_interval":0.3,      # float.(optional) to control the interval of the audio fragment.
        "seed": -1,                   # int.(optional) random seed for reproducibility.
        "media_type": "wav",          # str.(optional) media type of the output audio, support "wav", "raw", "ogg", "aac".
        "streaming_mode": False,      # bool.(optional) whether to return a streaming response.
        "parallel_infer": True,       # bool.(optional) whether to use parallel inference.
        "repetition_penalty": 1.35    # float.(optional) repetition penalty for T2S model.
    }
        try:
            response = requests.post(url, json=data)
            file_url = './samples/sample-' + str(int(time.time() * 1000)) + '.wav'
            if response.status_code == 200:
                with wave.open(file_url, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(32000)
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
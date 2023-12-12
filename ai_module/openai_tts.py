import requests
import json
import time
from utils import util, config_util

class Speech:
    def __init__(self):
        self.api_key = config_util.key_gpt_api_key
        self.history_data = []

    def __get_history(self, text):
        for data in self.history_data:
            if data[0] == text:
                return data[1]
        return None

    def connect(self):
        pass

    def close(self):
        pass

    def to_sample(self, text, voice="nova", response_format="mp3", speed=1):
        history = self.__get_history(text)
        if history is not None:
            return history

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        url = "https://api.openai.com/v1/audio/speech"
        query = {
            "model": "tts-1-hd",#tts-1、tts-1-hd
            "input": text,
            "voice": voice,
            "response_format": response_format,
            "speed": speed
        }
        try:
            response = requests.post(url=url, data=json.dumps(query), headers=headers)

            file_url = './samples/sample-' + str(int(time.time() * 1000)) + '.mp3'
            with open(file_url, "wb") as audio_file:
                audio_file.write(response.content)

            self.history_data.append((text, file_url))
        except Exception as e :
            util.log(1, "[x] 语音转换失败！")
            util.log(1, "[x] 原因: " + str(str(e)))
            file_url = None
        return file_url

if __name__ == '__main__':
    openai_tts = Speech(api_key='')  # 替换为您的 OpenAI API Key
    text = "你好！我是FAY！今天天气真好！"
    audio_file_url = openai_tts.to_sample(text)

    print("音频文件已保存:", audio_file_url)
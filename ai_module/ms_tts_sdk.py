import time

import azure.cognitiveservices.speech as speechsdk

from core import tts_voice
from core.tts_voice import EnumVoice
from utils import util, config_util
from utils import config_util as cfg


class Speech:
    def __init__(self):
        self.__speech_config = speechsdk.SpeechConfig(subscription=cfg.key_ms_tts_key, region="eastasia")
        self.__speech_config.speech_recognition_language = "zh-CN"
        self.__speech_config.speech_synthesis_voice_name = "zh-CN-XiaoxiaoNeural"
        self.__speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)
        self.__synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.__speech_config, audio_config=None)
        self.__connection = None
        self.__history_data = []

    def __get_history(self, voice_name, style, text):
        for data in self.__history_data:
            if data[0] == voice_name and data[1] == style and data[2] == text:
                return data[3]
        return None

    def connect(self):
        self.__connection = speechsdk.Connection.from_speech_synthesizer(self.__synthesizer)
        self.__connection.open(True)
        util.log(1, "TTS 服务已经连接！")

    def close(self):
        if self.__connection is not None:
            self.__connection.close()

    """
    文字转语音
    :param text: 文本信息
    :param style: 说话风格、语气
    :returns: 音频文件路径
    """

    def to_sample(self, text, style):
        voice_type = tts_voice.get_voice_of(config_util.config["attribute"]["voice"])
        voice_name = EnumVoice.XIAO_XIAO.value["voiceName"]
        if voice_type is not None:
            voice_name = voice_type.value["voiceName"]
        history = self.__get_history(voice_name, style, text)
        if history is not None:
            return history
        ssml = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="zh-CN">' \
               '<voice name="{}">' \
               '<mstts:express-as style="{}" styledegree="{}">' \
               '{}' \
               '</mstts:express-as>' \
               '</voice>' \
               '</speak>'.format(voice_name, style, 1.8, text)
        result = self.__synthesizer.speak_ssml(ssml)
        audio_data_stream = speechsdk.AudioDataStream(result)
        file_url = './samples/sample-' + str(int(time.time() * 1000)) + '.mp3'
        audio_data_stream.save_to_wav_file(file_url)
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            self.__history_data.append((voice_name, style, text, file_url))
            return file_url
        else:
            util.log(1, "[x] 语音转换失败！")
            util.log(1, "[x] 原因: " + str(result.reason))
            return None

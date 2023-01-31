import time

import azure.cognitiveservices.speech as speechsdk

from core import tts_voice
from core.tts_voice import EnumVoice
from utils import util, config_util
from utils import config_util as cfg
import pygame



class Speech:
    def __init__(self):
        self.__speech_config = speechsdk.SpeechConfig(subscription=cfg.key_ms_tts_key, region=cfg.key_ms_tts_region)
        self.__speech_config.speech_recognition_language = "zh-CN"
        self.__speech_config.speech_synthesis_voice_name = "zh-CN-XiaoxiaoNeural"
        self.__speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm)
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

        file_url = './samples/sample-' + str(int(time.time() * 1000)) + '.wav'
        audio_data_stream.save_to_wav_file(file_url)
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            self.__history_data.append((voice_name, style, text, file_url))
            return file_url
        else:
            util.log(1, "[x] 语音转换失败！")
            util.log(1, "[x] 原因: " + str(result.reason))
            return None
if __name__ == '__main__':
    cfg.load_config()
    sp = Speech()
    sp.connect()
    pygame.init()
    text = """一座城市，总有一条标志性道路，它见证着这座城市的时代变迁，并随着城市历史积淀砥砺前行，承载起城市的非凡荣耀。季华路，见证了佛山的崛起，从而也被誉为“最代表佛山城市发展的一条路”。季华路位于佛山市禅城区，是佛山市总体道路规划网中东西走向的城市主干道，全长20公里，是佛山市公路网络规划"四纵、九横、两环"主骨架中的重要组成部分，西接禅城南庄、高明、三水，东连南海、广州，横跨佛山一环、禅西大道、佛山大道、岭南大道、南海大道五大主干道，贯穿中心城区四个镇街，沿途经过多处文化古迹和重要产业区，是名副其实的“交通动脉”。同时季华路也是佛山的经济“大动脉”，代表着佛山蓬勃发展的现在，也影响着佛山日新月异的未来。
        季华六路起于南海大道到文华北截至，道路为东西走向，全长1.5公里，该路段为1996年完成建设并投入使用，该道路为一级公路，路面使用混凝土材质，道路为双向5车道，路宽30米，途径1个行政单位，一条隧道，该路段设有格栅518个，两边护栏1188米，沙井盖158个，其中供水26个，市政77个，移动通讯2个，联通通讯3个，电信通讯3个，交通信号灯1个，人行天桥2个，电梯4台，标志牌18个，标线为1.64万米。
        道路南行是文华中路，可通往亚洲艺术公园，亚洲艺术公园位于佛山市发展区的中心，占地40公顷，其中水体面积26.6公顷，以岭南水乡为文脉，以水上森林为绿脉，以龙舟竞渡为水脉，通过建筑、雕塑、植物、桥梁等设计要素，营造出一个具有亚洲艺术风采的艺术园地。曾获选佛山十大最美公园之一。
        道路北行是文华北路，可通往佛山市委市政府。佛山市委市政府是广东省佛山市的行政管理机关。
        道路西行到达文华公园。佛山市文华公园位于佛山市禅城区季华路以南（电视塔旁）、文华路以西，大福路以东路段，建设面积约11万平方米，主要将传统文化和现代园林有机结合，全园布局以大树木、大草坪、多彩植被和人工湖为表现主体，精致的溪涧、小桥、亲水平台点缀其间，通过棕榈植物错落有序的巧妙搭配，令园区既蕴涵亚热带曼妙风情，又不失岭南园艺的独特风采。通过“借景”、“透景”造园手法，与邻近的电视塔相映成趣，它的落成，为附近市民的休闲生活添上了色彩绚丽的一笔。

        季华五路是季华路最先建设的一段道路，起于岭南大道到佛山大道截至，道路为东西走向，全长2.1公里，该路段为1993年完成建设并投入使用，该道路为一级公路，路面使用混凝土材质，道路为双向5车道，路宽30米，途径1个行政单位，该路段设有格栅634个，两边护栏1310米，沙井盖180个，其中供水30个，市政81个，移动通讯5个，联通通讯3个，交通信号灯2个，人行天桥3个，电梯12台，标志牌26个，标线为2.131万米。
        沿途经过季华园，季华园即佛山季华公园，位于佛山市城南新区，1994年5月建成。占地200多亩。场内所有设施免费使用。景点介绍风格清新、意境优雅季华公园是具有亚热带风光的大型开放游览性公园。由于场内所有设施免费使用，地方广阔，每天都吸引着众多的游人前来休闲、运动等。
        道路南行是佛山大道中，可通往乐从方向乐从镇，地处珠三角腹地，广佛经济圈核心带，是国家级重大国际产业、城市发展合作平台--中德工业服务区、中欧城镇化合作示范区的核心。
        道路北行佛山大道中，可通往佛山火车站，佛山火车站是广东省的铁路枢纽之一，广三铁路经过该站。"""
    s = sp.to_sample(text, "cheerful")
    print(s)
    pygame.mixer.music.load(s)
    pygame.mixer.music.play()
    sp.close()
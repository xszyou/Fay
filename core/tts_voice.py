from enum import Enum


class EnumVoice(Enum):
    XIAO_XIAO = {
        "name": "晓晓",
        "voiceName": "zh-CN-XiaoxiaoNeural",
        "styleList": {
            "angry": "angry",
            "lyrical": "lyrical",
            "calm": "gentle",
            "assistant": "affectionate",
            "cheerful": "cheerful"
        }
    }
    YUN_XI = {
        "name": "云溪",
        "voiceName": "zh-CN-YunxiNeural",
        "styleList": {
            "angry": "angry",
            "lyrical": "disgruntled",
            "calm": "calm",
            "assistant": "assistant",
            "cheerful": "cheerful"
        }
    }
    YUN_JIAN = {
        "name": "云健",
        "voiceName": "zh-CN-YunjianNeural",
        "styleList": {
            "angry": "angry",
            "lyrical": "disgruntled",
            "calm": "calm",
            "assistant": "assistant",
            "cheerful": "cheerful"
        }
    }
    XIAO_YI = {
        "name": "晓伊",
        "voiceName": "zh-CN-XiaoyiNeural",
        "styleList": {
            "angry": "angry",
            "lyrical": "lyrical",
            "calm": "gentle",
            "assistant": "affectionate",
            "cheerful": "cheerful"
        }
    }
    YUN_YANG = {
        "name": "云阳",
        "voiceName": "zh-CN-YunyangNeural",
        "styleList": {
            "angry": "angry",
            "lyrical": "lyrical",
            "calm": "gentle",
            "assistant": "affectionate",
            "cheerful": "cheerful"
        }
    }
    YUN_XIA = {
        "name": "云夏",
        "voiceName": "zh-CN-YunxiaNeural",
        "styleList": {
            "angry": "angry",
            "lyrical": "lyrical",
            "calm": "gentle",
            "assistant": "affectionate",
            "cheerful": "cheerful"
        }
    }




def get_voice_list():
    return [EnumVoice.YUN_XI, EnumVoice.XIAO_XIAO, EnumVoice.YUN_JIAN, EnumVoice.XIAO_YI, EnumVoice.YUN_YANG, EnumVoice.YUN_XIA]


def get_voice_of(name):
    for voice in get_voice_list():
        if voice.name == name:
            return voice
    return None

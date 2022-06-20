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


def get_voice_list():
    return [EnumVoice.YUN_XI, EnumVoice.XIAO_XIAO]


def get_voice_of(name):
    for voice in get_voice_list():
        if voice.name == name:
            return voice
    return None

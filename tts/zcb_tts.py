"""
智创宝TTS模块 - 用于Fay TTS接口
"""

import os
import time
import requests
from utils import util
from utils import config_util as cfg
from ai_module.tts_zcb import ZcbDigitalHuman


class Speech:
    """智创宝TTS Speech类，符合Fay TTS接口规范"""

    def __init__(self):
        self.client = ZcbDigitalHuman(
            api_token=cfg.zcb_api_token,
            model_id=cfg.zcb_model_id,
            video_url=cfg.zcb_video_url
        )
        self.__history_data = []

    def connect(self):
        """连接（智创宝API无需预连接）"""
        pass

    def __get_history(self, text):
        """从历史缓存中获取音频"""
        for data in self.__history_data:
            if data[0] == text:
                return data[1]
        return None

    def __add_history(self, text, file_path):
        """添加到历史缓存"""
        self.__history_data.append((text, file_path))
        # 限制缓存大小
        if len(self.__history_data) > 100:
            self.__history_data.pop(0)

    def __download_audio(self, audio_url):
        """
        下载音频文件到本地samples目录

        Args:
            audio_url: 远程音频URL

        Returns:
            本地文件路径 或 None
        """
        try:
            # 确保samples目录存在
            samples_dir = './samples'
            if not os.path.exists(samples_dir):
                os.makedirs(samples_dir)

            # 生成本地文件名
            timestamp = int(time.time() * 1000)
            # 根据URL判断文件扩展名
            if '.wav' in audio_url.lower():
                ext = '.wav'
            elif '.mp3' in audio_url.lower():
                ext = '.mp3'
            else:
                ext = '.mp3'  # 默认mp3

            local_path = os.path.join(samples_dir, f'zcb-{timestamp}{ext}')

            # 下载文件
            response = requests.get(audio_url, timeout=60)
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                util.log(1, f"[ZCB TTS] 音频已下载: {local_path}")
                return local_path
            else:
                util.log(1, f"[ZCB TTS] 下载音频失败: HTTP {response.status_code}")
                return None

        except Exception as e:
            util.log(1, f"[ZCB TTS] 下载音频异常: {str(e)}")
            return None

    def to_sample(self, text, style):
        """
        将文字转换为语音

        Args:
            text: 要合成的文字
            style: 情感风格（智创宝暂不支持，忽略）

        Returns:
            本地音频文件路径 或 None
        """
        try:
            # 检查历史缓存
            history = self.__get_history(text)
            if history is not None and os.path.exists(history):
                util.log(1, f"[ZCB TTS] 使用缓存音频: {history}")
                return history

            util.log(1, f"[ZCB TTS] 开始合成: {text[:30]}...")

            # 调用智创宝API生成音频
            audio_url = self.client.generate_audio_only(text)

            if audio_url:
                # 下载音频到本地
                local_path = self.__download_audio(audio_url)
                if local_path:
                    self.__add_history(text, local_path)
                    return local_path
                else:
                    util.log(1, "[ZCB TTS] 下载音频失败")
                    return None
            else:
                util.log(1, "[ZCB TTS] 生成音频失败")
                return None

        except Exception as e:
            util.log(1, f"[ZCB TTS] 语音合成异常: {str(e)}")
            return None

    def to_video(self, text):
        """
        将文字转换为数字人视频（扩展功能）

        Args:
            text: 要合成的文字

        Returns:
            视频URL 或 None
        """
        try:
            util.log(1, f"[ZCB TTS] 开始生成数字人视频: {text[:30]}...")
            video_url = self.client.generate_digital_human_video(text)
            if video_url:
                util.log(1, f"[ZCB TTS] 数字人视频生成成功: {video_url}")
            return video_url
        except Exception as e:
            util.log(1, f"[ZCB TTS] 数字人视频生成异常: {str(e)}")
            return None

    def close(self):
        """关闭连接（智创宝API无需关闭）"""
        pass

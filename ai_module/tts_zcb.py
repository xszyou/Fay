"""
数字人API对接模块 - 智创宝服务
支持声音克隆和数字人视频合成
"""

import json
import time
import requests
from utils import config_util as cfg
from utils import util


class ZcbDigitalHuman:
    """智创宝数字人API对接类"""

    BASE_URL = "https://zcbservice.aizfw.cn/kyyApi"

    def __init__(self, api_token=None, model_id=None, video_url=None):
        """
        初始化数字人API客户端

        Args:
            api_token: API密钥，如未提供则从配置读取
            model_id: 声音模型ID，如未提供则从配置读取
            video_url: 数字人形象视频地址，如未提供则从配置读取
        """
        self.api_token = api_token or getattr(cfg, 'zcb_api_token', '')
        self.model_id = model_id or getattr(cfg, 'zcb_model_id', '')
        self.video_url = video_url or getattr(cfg, 'zcb_video_url', '')

        # 轮询配置
        self.poll_interval = 2  # 轮询间隔（秒）
        self.max_poll_time = 300  # 最大等待时间（秒）

    def _get_headers(self, with_token=True):
        """获取请求头"""
        headers = {
            'Content-Type': 'application/json'
        }
        if with_token:
            headers['token'] = self.api_token
        return headers

    def _post_request(self, endpoint, data):
        """发送POST请求"""
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=data,
                timeout=30
            )
            if response.status_code != 200:
                util.log(1, f"[ZCB] 请求失败 {endpoint}: HTTP {response.status_code}")
                return None
            return response.json()
        except Exception as e:
            util.log(1, f"[ZCB] 请求异常 {endpoint}: {str(e)}")
            return None

    def _get_request(self, endpoint, params=None):
        """发送GET请求"""
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )
            if response.status_code != 200:
                util.log(1, f"[ZCB] 请求失败 {endpoint}: HTTP {response.status_code}")
                return None
            return response.json()
        except Exception as e:
            util.log(1, f"[ZCB] 请求异常 {endpoint}: {str(e)}")
            return None

    # ========== 声音克隆相关 ==========

    def submit_audio_task(self, text, language="Chinese", model_id=None):
        """
        提交声音克隆任务

        Args:
            text: 要合成的文字
            language: 语言，默认Chinese
            model_id: 声音模型ID，如未提供则使用初始化时的配置

        Returns:
            taskId 或 None
        """
        data = {
            "modelId": model_id or self.model_id,
            "contentText": text,
            "language": language
        }

        util.log(1, f"[ZCB] 提交声音克隆任务: {text[:50]}...")
        result = self._post_request("apiSoundCloning/generateAudio", data)

        if result and 'taskId' in result:
            util.log(1, f"[ZCB] 声音克隆任务已提交: {result['taskId']}")
            return result['taskId']
        elif result and 'data' in result and 'taskId' in result['data']:
            task_id = result['data']['taskId']
            util.log(1, f"[ZCB] 声音克隆任务已提交: {task_id}")
            return task_id
        else:
            util.log(1, f"[ZCB] 提交声音克隆任务失败: {result}")
            return None

    def get_audio_result(self, task_id):
        """
        查询音频生成结果

        Args:
            task_id: 任务ID

        Returns:
            audioUrl 或 None
        """
        result = self._get_request("apiSoundCloning/getAudioByTaskId", {"taskId": task_id})

        if result:
            # 尝试多种可能的返回格式
            if 'audioUrl' in result and result['audioUrl']:
                return result['audioUrl']
            elif 'data' in result and result['data']:
                if isinstance(result['data'], str):
                    return result['data']
                elif isinstance(result['data'], dict) and 'audioUrl' in result['data']:
                    return result['data']['audioUrl']
        return None

    def wait_for_audio(self, task_id):
        """
        轮询等待音频生成完成

        Args:
            task_id: 任务ID

        Returns:
            audioUrl 或 None
        """
        util.log(1, f"[ZCB] 等待音频生成: {task_id}")
        start_time = time.time()

        while time.time() - start_time < self.max_poll_time:
            audio_url = self.get_audio_result(task_id)
            if audio_url:
                util.log(1, f"[ZCB] 音频生成完成: {audio_url}")
                return audio_url

            time.sleep(self.poll_interval)

        util.log(1, f"[ZCB] 音频生成超时: {task_id}")
        return None

    # ========== 数字人剪辑相关 ==========

    def submit_video_task(self, audio_url, video_url=None, model_version=2):
        """
        提交数字人剪辑任务

        Args:
            audio_url: 音频地址
            video_url: 数字人形象视频地址，如未提供则使用初始化时的配置
            model_version: 模型版本，默认2

        Returns:
            projectId 或 None
        """
        data = {
            "audioUrl": audio_url,
            "videoUrl": video_url or self.video_url,
            "modelVersion": model_version
        }

        util.log(1, f"[ZCB] 提交数字人剪辑任务")
        result = self._post_request("apiMediaProject/createMediaProject", data)

        if result and 'projectId' in result:
            util.log(1, f"[ZCB] 数字人剪辑任务已提交: {result['projectId']}")
            return result['projectId']
        elif result and 'data' in result and 'projectId' in result['data']:
            project_id = result['data']['projectId']
            util.log(1, f"[ZCB] 数字人剪辑任务已提交: {project_id}")
            return project_id
        else:
            util.log(1, f"[ZCB] 提交数字人剪辑任务失败: {result}")
            return None

    def get_video_result(self, project_id):
        """
        查询视频生成结果

        Args:
            project_id: 项目ID

        Returns:
            mediaUrl 或 None
        """
        data = {"projectId": project_id}
        result = self._post_request("apiMakeVideo/getVideoResult", data)

        if result:
            # 尝试多种可能的返回格式
            if 'mediaUrl' in result and result['mediaUrl']:
                return result['mediaUrl']
            elif 'data' in result and result['data']:
                if isinstance(result['data'], str):
                    return result['data']
                elif isinstance(result['data'], dict) and 'mediaUrl' in result['data']:
                    return result['data']['mediaUrl']
        return None

    def wait_for_video(self, project_id):
        """
        轮询等待视频生成完成

        Args:
            project_id: 项目ID

        Returns:
            mediaUrl 或 None
        """
        util.log(1, f"[ZCB] 等待视频生成: {project_id}")
        start_time = time.time()

        while time.time() - start_time < self.max_poll_time:
            media_url = self.get_video_result(project_id)
            if media_url:
                util.log(1, f"[ZCB] 视频生成完成: {media_url}")
                return media_url

            time.sleep(self.poll_interval)

        util.log(1, f"[ZCB] 视频生成超时: {project_id}")
        return None

    # ========== 完整流程 ==========

    def generate_digital_human_video(self, text, language="Chinese"):
        """
        完整流程：文字 -> 声音克隆 -> 数字人视频

        Args:
            text: 要合成的文字
            language: 语言，默认Chinese

        Returns:
            最终视频URL 或 None
        """
        util.log(1, f"[ZCB] 开始生成数字人视频: {text[:50]}...")

        # 步骤1: 提交声音克隆任务
        task_id = self.submit_audio_task(text, language)
        if not task_id:
            util.log(1, "[ZCB] 声音克隆任务提交失败")
            return None

        # 步骤2: 等待音频生成完成
        audio_url = self.wait_for_audio(task_id)
        if not audio_url:
            util.log(1, "[ZCB] 音频生成失败或超时")
            return None

        # 步骤3: 提交数字人剪辑任务
        project_id = self.submit_video_task(audio_url)
        if not project_id:
            util.log(1, "[ZCB] 数字人剪辑任务提交失败")
            return None

        # 步骤4: 等待视频生成完成
        media_url = self.wait_for_video(project_id)
        if not media_url:
            util.log(1, "[ZCB] 视频生成失败或超时")
            return None

        util.log(1, f"[ZCB] 数字人视频生成成功: {media_url}")
        return media_url

    def generate_audio_only(self, text, language="Chinese"):
        """
        仅生成音频（不生成视频）

        Args:
            text: 要合成的文字
            language: 语言，默认Chinese

        Returns:
            音频URL 或 None
        """
        task_id = self.submit_audio_task(text, language)
        if not task_id:
            return None
        return self.wait_for_audio(task_id)


# ========== 便捷函数 ==========

def generate_video(text, api_token=None, model_id=None, video_url=None):
    """
    便捷函数：生成数字人视频

    Args:
        text: 要合成的文字
        api_token: API密钥（可选，默认从配置读取）
        model_id: 声音模型ID（可选，默认从配置读取）
        video_url: 数字人形象视频地址（可选，默认从配置读取）

    Returns:
        最终视频URL 或 None
    """
    client = ZcbDigitalHuman(api_token, model_id, video_url)
    return client.generate_digital_human_video(text)


def generate_audio(text, api_token=None, model_id=None):
    """
    便捷函数：仅生成音频

    Args:
        text: 要合成的文字
        api_token: API密钥（可选，默认从配置读取）
        model_id: 声音模型ID（可选，默认从配置读取）

    Returns:
        音频URL 或 None
    """
    client = ZcbDigitalHuman(api_token, model_id)
    return client.generate_audio_only(text)


# 测试代码
if __name__ == "__main__":
    # 示例用法
    client = ZcbDigitalHuman(
        api_token="your_api_token",
        model_id="your_model_id",
        video_url="your_video_url"
    )

    # 生成完整数字人视频
    # result = client.generate_digital_human_video("你好，欢迎使用数字人服务！")
    # print(f"视频地址: {result}")

    # 或者仅生成音频
    # audio = client.generate_audio_only("你好，这是测试音频。")
    # print(f"音频地址: {audio}")

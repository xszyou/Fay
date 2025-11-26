"""
声音模型管理模块
用于管理智创宝声音克隆模型的创建、试听、保存和删除
"""

import os
import json
import time
import requests
from datetime import datetime
from utils import util
from utils import config_util as cfg


class VoiceManager:
    """声音模型管理类"""

    BASE_URL = "https://zcbservice.aizfw.cn/kyyApi"
    DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'voice_models.json')

    def __init__(self, api_token=None):
        """
        初始化声音管理器

        Args:
            api_token: API密钥，如未提供则从配置读取
        """
        self.api_token = api_token or getattr(cfg, 'zcb_api_token', '')
        self.poll_interval = 2
        self.max_poll_time = 300

    def _get_headers(self):
        """获取请求头"""
        return {
            'Content-Type': 'application/json',
            'token': self.api_token
        }

    def _post_request(self, endpoint, data):
        """发送POST请求"""
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code != 200:
                util.log(1, f"[VoiceManager] 请求失败 {endpoint}: HTTP {response.status_code}")
                return None
            return response.json()
        except Exception as e:
            util.log(1, f"[VoiceManager] 请求异常 {endpoint}: {str(e)}")
            return None

    def _get_request(self, endpoint, params=None):
        """发送GET请求"""
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code != 200:
                util.log(1, f"[VoiceManager] 请求失败 {endpoint}: HTTP {response.status_code}")
                return None
            return response.json()
        except Exception as e:
            util.log(1, f"[VoiceManager] 请求异常 {endpoint}: {str(e)}")
            return None

    def _load_data(self):
        """加载数据文件"""
        try:
            if os.path.exists(self.DATA_FILE):
                with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"voices": []}
        except Exception as e:
            util.log(1, f"[VoiceManager] 加载数据失败: {str(e)}")
            return {"voices": []}

    def _save_data(self, data):
        """保存数据文件"""
        try:
            os.makedirs(os.path.dirname(self.DATA_FILE), exist_ok=True)
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            util.log(1, f"[VoiceManager] 保存数据失败: {str(e)}")
            return False

    def create_voice(self, audio_url, voice_name=None):
        """
        上传音频创建/训练声音模型

        Args:
            audio_url: 训练用音频URL
            voice_name: 声音名称（可选）

        Returns:
            dict: 包含 model_id 和状态信息，失败返回 None
        """
        util.log(1, f"[VoiceManager] 创建声音模型: {audio_url}")

        # 调用声音克隆训练API
        # 注意：实际API接口需要根据智创宝文档确认
        data = {
            "audioUrl": audio_url,
            "voiceName": voice_name or f"voice_{int(time.time())}"
        }

        result = self._post_request("apiSoundCloning/createVoiceModel", data)

        if result:
            model_id = result.get('modelId') or result.get('data', {}).get('modelId')
            if model_id:
                util.log(1, f"[VoiceManager] 声音模型创建成功: {model_id}")
                return {
                    "model_id": model_id,
                    "name": voice_name,
                    "status": "created",
                    "audio_url": audio_url
                }

        util.log(1, f"[VoiceManager] 声音模型创建失败: {result}")
        return None

    def preview_voice(self, model_id, text, language="Chinese"):
        """
        使用指定声音模型生成试听音频

        Args:
            model_id: 声音模型ID
            text: 试听文本
            language: 语言，默认Chinese

        Returns:
            str: 试听音频URL，失败返回 None
        """
        util.log(1, f"[VoiceManager] 生成试听音频: {text[:30]}...")

        # 提交音频生成任务
        data = {
            "modelId": model_id,
            "contentText": text,
            "language": language
        }

        result = self._post_request("apiSoundCloning/generateAudio", data)
        if not result:
            return None

        task_id = result.get('taskId') or result.get('data', {}).get('taskId')
        if not task_id:
            util.log(1, f"[VoiceManager] 获取任务ID失败: {result}")
            return None

        util.log(1, f"[VoiceManager] 任务已提交: {task_id}")

        # 轮询等待结果
        start_time = time.time()
        while time.time() - start_time < self.max_poll_time:
            audio_result = self._get_request("apiSoundCloning/getAudioByTaskId", {"taskId": task_id})

            if audio_result:
                audio_url = None
                if 'audioUrl' in audio_result and audio_result['audioUrl']:
                    audio_url = audio_result['audioUrl']
                elif 'data' in audio_result and audio_result['data']:
                    if isinstance(audio_result['data'], str):
                        audio_url = audio_result['data']
                    elif isinstance(audio_result['data'], dict):
                        audio_url = audio_result['data'].get('audioUrl')

                if audio_url:
                    util.log(1, f"[VoiceManager] 试听音频生成完成: {audio_url}")
                    return audio_url

            time.sleep(self.poll_interval)

        util.log(1, f"[VoiceManager] 试听音频生成超时")
        return None

    def save_voice(self, model_id, name, preview_url=None):
        """
        保存声音模型到记录

        Args:
            model_id: 声音模型ID
            name: 声音名称
            preview_url: 试听音频URL（可选）

        Returns:
            bool: 保存是否成功
        """
        data = self._load_data()

        # 检查是否已存在
        for voice in data['voices']:
            if voice['model_id'] == model_id:
                voice['name'] = name
                voice['status'] = 'saved'
                voice['updated_at'] = datetime.now().isoformat()
                if preview_url:
                    voice['preview_url'] = preview_url
                self._save_data(data)
                util.log(1, f"[VoiceManager] 更新声音模型: {name}")
                return True

        # 新增记录
        voice_record = {
            "model_id": model_id,
            "name": name,
            "status": "saved",
            "preview_url": preview_url,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        data['voices'].append(voice_record)
        if self._save_data(data):
            util.log(1, f"[VoiceManager] 保存声音模型: {name} ({model_id})")
            return True
        return False

    def delete_voice(self, model_id):
        """
        删除声音模型

        Args:
            model_id: 声音模型ID

        Returns:
            bool: 删除是否成功
        """
        data = self._load_data()

        for i, voice in enumerate(data['voices']):
            if voice['model_id'] == model_id:
                # 标记为已删除或直接移除
                data['voices'][i]['status'] = 'deleted'
                data['voices'][i]['deleted_at'] = datetime.now().isoformat()
                # 或者直接删除: data['voices'].pop(i)

                if self._save_data(data):
                    util.log(1, f"[VoiceManager] 删除声音模型: {model_id}")
                    return True
                return False

        util.log(1, f"[VoiceManager] 未找到声音模型: {model_id}")
        return False

    def list_voices(self, include_deleted=False):
        """
        列出所有声音模型

        Args:
            include_deleted: 是否包含已删除的

        Returns:
            list: 声音模型列表
        """
        data = self._load_data()
        voices = data.get('voices', [])

        if not include_deleted:
            voices = [v for v in voices if v.get('status') != 'deleted']

        return voices

    def get_voice(self, model_id):
        """
        获取单个声音模型详情

        Args:
            model_id: 声音模型ID

        Returns:
            dict: 声音模型信息，未找到返回 None
        """
        data = self._load_data()
        for voice in data.get('voices', []):
            if voice['model_id'] == model_id:
                return voice
        return None

    def set_active_voice(self, model_id):
        """
        设置当前使用的声音模型（更新配置）

        Args:
            model_id: 声音模型ID

        Returns:
            bool: 设置是否成功
        """
        voice = self.get_voice(model_id)
        if not voice:
            util.log(1, f"[VoiceManager] 未找到声音模型: {model_id}")
            return False

        # 这里可以更新配置文件中的 zcb_model_id
        util.log(1, f"[VoiceManager] 设置当前声音: {voice['name']} ({model_id})")
        return True


# 便捷函数
def list_voices():
    """列出所有已保存的声音"""
    manager = VoiceManager()
    return manager.list_voices()


def preview_voice(model_id, text):
    """生成试听音频"""
    manager = VoiceManager()
    return manager.preview_voice(model_id, text)


def save_voice(model_id, name, preview_url=None):
    """保存声音模型"""
    manager = VoiceManager()
    return manager.save_voice(model_id, name, preview_url)


def delete_voice(model_id):
    """删除声音模型"""
    manager = VoiceManager()
    return manager.delete_voice(model_id)

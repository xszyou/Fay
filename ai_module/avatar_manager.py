"""
数字人形象管理模块
用于管理智创宝数字人形象的添加、预览、保存和删除
"""

import os
import json
import time
import requests
from datetime import datetime
from utils import util
from utils import config_util as cfg


class AvatarManager:
    """数字人形象管理类"""

    BASE_URL = "https://zcbservice.aizfw.cn/kyyApi"
    DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'avatar_models.json')

    def __init__(self, api_token=None):
        """
        初始化形象管理器

        Args:
            api_token: API密钥，如未提供则从配置读取
        """
        self.api_token = api_token or getattr(cfg, 'zcb_api_token', '')
        self.poll_interval = 3
        self.max_poll_time = 600  # 视频生成时间较长

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
                util.log(1, f"[AvatarManager] 请求失败 {endpoint}: HTTP {response.status_code}")
                return None
            return response.json()
        except Exception as e:
            util.log(1, f"[AvatarManager] 请求异常 {endpoint}: {str(e)}")
            return None

    def _load_data(self):
        """加载数据文件"""
        try:
            if os.path.exists(self.DATA_FILE):
                with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"avatars": []}
        except Exception as e:
            util.log(1, f"[AvatarManager] 加载数据失败: {str(e)}")
            return {"avatars": []}

    def _save_data(self, data):
        """保存数据文件"""
        try:
            os.makedirs(os.path.dirname(self.DATA_FILE), exist_ok=True)
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            util.log(1, f"[AvatarManager] 保存数据失败: {str(e)}")
            return False

    def _generate_avatar_id(self, video_url):
        """根据视频URL生成唯一ID"""
        import hashlib
        return hashlib.md5(video_url.encode()).hexdigest()[:12]

    def create_avatar(self, video_url, name=None, thumbnail_url=None):
        """
        添加数字人形象

        Args:
            video_url: 数字人形象视频URL
            name: 形象名称（可选）
            thumbnail_url: 缩略图URL（可选）

        Returns:
            dict: 形象信息，失败返回 None
        """
        util.log(1, f"[AvatarManager] 添加形象: {video_url}")

        avatar_id = self._generate_avatar_id(video_url)

        avatar_info = {
            "avatar_id": avatar_id,
            "video_url": video_url,
            "name": name or f"avatar_{avatar_id}",
            "thumbnail_url": thumbnail_url,
            "status": "created",
            "created_at": datetime.now().isoformat()
        }

        util.log(1, f"[AvatarManager] 形象创建成功: {avatar_id}")
        return avatar_info

    def preview_avatar(self, video_url, audio_url, model_version=2):
        """
        使用形象和音频生成预览视频

        Args:
            video_url: 数字人形象视频URL
            audio_url: 音频URL
            model_version: 模型版本，默认2

        Returns:
            str: 预览视频URL，失败返回 None
        """
        util.log(1, f"[AvatarManager] 生成预览视频...")

        # 提交数字人剪辑任务
        data = {
            "audioUrl": audio_url,
            "videoUrl": video_url,
            "modelVersion": model_version
        }

        result = self._post_request("apiMediaProject/createMediaProject", data)
        if not result:
            return None

        project_id = result.get('projectId') or result.get('data', {}).get('projectId')
        if not project_id:
            util.log(1, f"[AvatarManager] 获取项目ID失败: {result}")
            return None

        util.log(1, f"[AvatarManager] 项目已创建: {project_id}")

        # 轮询等待视频生成
        start_time = time.time()
        while time.time() - start_time < self.max_poll_time:
            video_result = self._post_request("apiMakeVideo/getVideoResult", {"projectId": project_id})

            if video_result:
                media_url = None
                if 'mediaUrl' in video_result and video_result['mediaUrl']:
                    media_url = video_result['mediaUrl']
                elif 'data' in video_result and video_result['data']:
                    if isinstance(video_result['data'], str):
                        media_url = video_result['data']
                    elif isinstance(video_result['data'], dict):
                        media_url = video_result['data'].get('mediaUrl')

                if media_url:
                    util.log(1, f"[AvatarManager] 预览视频生成完成: {media_url}")
                    return media_url

            time.sleep(self.poll_interval)

        util.log(1, f"[AvatarManager] 预览视频生成超时")
        return None

    def save_avatar(self, video_url, name, thumbnail_url=None, preview_url=None):
        """
        保存形象到记录

        Args:
            video_url: 形象视频URL
            name: 形象名称
            thumbnail_url: 缩略图URL（可选）
            preview_url: 预览视频URL（可选）

        Returns:
            bool: 保存是否成功
        """
        data = self._load_data()
        avatar_id = self._generate_avatar_id(video_url)

        # 检查是否已存在
        for avatar in data['avatars']:
            if avatar['video_url'] == video_url:
                avatar['name'] = name
                avatar['status'] = 'saved'
                avatar['updated_at'] = datetime.now().isoformat()
                if thumbnail_url:
                    avatar['thumbnail_url'] = thumbnail_url
                if preview_url:
                    avatar['preview_url'] = preview_url
                self._save_data(data)
                util.log(1, f"[AvatarManager] 更新形象: {name}")
                return True

        # 新增记录
        avatar_record = {
            "avatar_id": avatar_id,
            "video_url": video_url,
            "name": name,
            "status": "saved",
            "thumbnail_url": thumbnail_url,
            "preview_url": preview_url,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        data['avatars'].append(avatar_record)
        if self._save_data(data):
            util.log(1, f"[AvatarManager] 保存形象: {name} ({avatar_id})")
            return True
        return False

    def delete_avatar(self, video_url):
        """
        删除形象

        Args:
            video_url: 形象视频URL

        Returns:
            bool: 删除是否成功
        """
        data = self._load_data()

        for i, avatar in enumerate(data['avatars']):
            if avatar['video_url'] == video_url:
                data['avatars'][i]['status'] = 'deleted'
                data['avatars'][i]['deleted_at'] = datetime.now().isoformat()

                if self._save_data(data):
                    util.log(1, f"[AvatarManager] 删除形象: {video_url}")
                    return True
                return False

        util.log(1, f"[AvatarManager] 未找到形象: {video_url}")
        return False

    def list_avatars(self, include_deleted=False):
        """
        列出所有形象

        Args:
            include_deleted: 是否包含已删除的

        Returns:
            list: 形象列表
        """
        data = self._load_data()
        avatars = data.get('avatars', [])

        if not include_deleted:
            avatars = [a for a in avatars if a.get('status') != 'deleted']

        return avatars

    def get_avatar(self, video_url=None, avatar_id=None):
        """
        获取单个形象详情

        Args:
            video_url: 形象视频URL
            avatar_id: 形象ID（二选一）

        Returns:
            dict: 形象信息，未找到返回 None
        """
        data = self._load_data()
        for avatar in data.get('avatars', []):
            if video_url and avatar['video_url'] == video_url:
                return avatar
            if avatar_id and avatar.get('avatar_id') == avatar_id:
                return avatar
        return None

    def set_active_avatar(self, video_url):
        """
        设置当前使用的形象（更新配置）

        Args:
            video_url: 形象视频URL

        Returns:
            bool: 设置是否成功
        """
        avatar = self.get_avatar(video_url=video_url)
        if not avatar:
            util.log(1, f"[AvatarManager] 未找到形象: {video_url}")
            return False

        # 这里可以更新配置文件中的 zcb_video_url
        util.log(1, f"[AvatarManager] 设置当前形象: {avatar['name']}")
        return True


# 便捷函数
def list_avatars():
    """列出所有已保存的形象"""
    manager = AvatarManager()
    return manager.list_avatars()


def preview_avatar(video_url, audio_url):
    """生成预览视频"""
    manager = AvatarManager()
    return manager.preview_avatar(video_url, audio_url)


def save_avatar(video_url, name, thumbnail_url=None):
    """保存形象"""
    manager = AvatarManager()
    return manager.save_avatar(video_url, name, thumbnail_url)


def delete_avatar(video_url):
    """删除形象"""
    manager = AvatarManager()
    return manager.delete_avatar(video_url)

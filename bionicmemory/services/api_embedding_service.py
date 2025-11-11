import logging
import requests
from typing import List, Optional
import threading
import os
import sys

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    import utils.config_util as cfg
    CONFIG_UTIL_AVAILABLE = True
except ImportError as e:
    CONFIG_UTIL_AVAILABLE = False
    cfg = None

# 使用统一日志配置
from bionicmemory.utils.logging_config import get_logger
logger = get_logger(__name__)

if not CONFIG_UTIL_AVAILABLE:
    logger.warning("无法导入 config_util，将使用环境变量配置")

class ApiEmbeddingService:
    """API Embedding服务 - 单例模式，调用 OpenAI 兼容的 API"""

    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._initialize_config()
                    ApiEmbeddingService._initialized = True

    def _initialize_config(self):
        """初始化配置，只执行一次"""
        try:
            # 优先从 system.conf 读取配置
            api_base_url = None
            api_key = None
            model_name = None

            if CONFIG_UTIL_AVAILABLE and cfg:
                try:
                    # 确保配置已加载
                    if cfg.config is None:
                        cfg.load_config()

                    # 从 config_util 获取配置（自动复用 LLM 配置）
                    api_base_url = cfg.embedding_api_base_url
                    api_key = cfg.embedding_api_key
                    model_name = cfg.embedding_api_model

                    logger.info(f"从 system.conf 读取配置:")
                    logger.info(f"  - embedding_api_model: {model_name}")
                    logger.info(f"  - embedding_api_base_url: {api_base_url}")
                    logger.info(f"  - embedding_api_key: {'已配置' if api_key else '未配置'}")
                except Exception as e:
                    logger.warning(f"从 system.conf 读取配置失败: {e}")

            # 验证必需配置并提供更好的错误提示
            if not api_base_url:
                api_base_url = os.getenv('EMBEDDING_API_BASE_URL')
                if not api_base_url:
                    error_msg = ("未配置 embedding_api_base_url！\n"
                                "请确保 system.conf 中配置了 gpt_base_url，"
                                "或设置环境变量 EMBEDDING_API_BASE_URL")
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                logger.warning(f"使用环境变量配置: base_url={api_base_url}")

            if not api_key:
                api_key = os.getenv('EMBEDDING_API_KEY')
                if not api_key:
                    error_msg = ("未配置 embedding_api_key！\n"
                                "请确保 system.conf 中配置了 gpt_api_key，"
                                "或设置环境变量 EMBEDDING_API_KEY")
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                logger.warning("使用环境变量配置: api_key")

            if not model_name:
                model_name = os.getenv('EMBEDDING_API_MODEL', 'text-embedding-ada-002')
                logger.warning(f"未配置 embedding_api_model，使用默认值: {model_name}")

            # 保存配置信息
            self.api_base_url = api_base_url.rstrip('/')  # 移除末尾的斜杠
            self.api_key = api_key
            self.model_name = model_name
            self.embedding_dim = None  # 将在首次调用时动态获取
            self.timeout = 60  # API 请求超时时间（秒），默认 60 秒
            self.max_retries = 2  # 最大重试次数

            logger.info(f"API Embedding 服务初始化完成")
            logger.info(f"模型: {self.model_name}")
            logger.info(f"API 地址: {self.api_base_url}")

        except Exception as e:
            logger.error(f"API Embedding 服务初始化失败: {e}")
            raise

    def encode_text(self, text: str) -> List[float]:
        """编码单个文本（带重试机制）"""
        import time

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                # 调用 API 进行编码
                url = f"{self.api_base_url}/embeddings"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                payload = {
                    "model": self.model_name,
                    "input": text
                }

                # 记录请求信息
                text_preview = text[:50] + "..." if len(text) > 50 else text
                logger.info(f"发送 embedding 请求 (尝试 {attempt + 1}/{self.max_retries + 1}): 文本长度={len(text)}, 预览='{text_preview}'")

                response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()

                result = response.json()
                embedding = result['data'][0]['embedding']

                # 首次调用时获取实际维度
                if self.embedding_dim is None:
                    self.embedding_dim = len(embedding)
                    logger.info(f"动态获取 embedding 维度: {self.embedding_dim}")

                logger.info(f"embedding 生成成功")
                return embedding

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries + 1}): {e}")
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # 指数退避: 1s, 2s, 4s
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"所有重试均失败，文本长度: {len(text)}")
                    raise

            except Exception as e:
                last_error = e
                logger.error(f"文本编码失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {e}")
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    raise

    def encode_texts(self, texts: List[str]) -> List[List[float]]:
        """批量编码文本"""
        try:
            # 调用 API 进行批量编码
            url = f"{self.api_base_url}/embeddings"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            payload = {
                "model": self.model_name,
                "input": texts
            }

            # 批量请求使用更长的超时时间
            batch_timeout = self.timeout * 2  # 批量请求超时时间加倍
            logger.info(f"发送批量 embedding 请求: 文本数={len(texts)}, 超时={batch_timeout}秒")
            response = requests.post(url, json=payload, headers=headers, timeout=batch_timeout)
            response.raise_for_status()

            result = response.json()
            embeddings = [item['embedding'] for item in result['data']]

            return embeddings
        except Exception as e:
            logger.error(f"批量文本编码失败: {e}")
            raise

    def get_model_info(self) -> dict:
        """获取模型信息"""
        return {
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "api_base_url": self.api_base_url,
            "initialized": self._initialized,
            "service_type": "api"
        }

# 全局实例
_global_embedding_service = None

def get_embedding_service() -> ApiEmbeddingService:
    """获取全局embedding服务实例"""
    global _global_embedding_service
    if _global_embedding_service is None:
        _global_embedding_service = ApiEmbeddingService()
    return _global_embedding_service

import logging
import numpy as np
from typing import List, Optional
from sentence_transformers import SentenceTransformer
import torch
import hashlib
import threading
import os
import sys
from dotenv import load_dotenv,find_dotenv

# 设置离线模式，避免访问Hugging Face
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'

# 设置国内 Hugging Face 镜像站点（作为备用）
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 加载环境变量
load_dotenv()

# 导入配置工具
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
    logger.warning("无法导入 config_util，将使用 .env 配置")

class LocalEmbeddingService:
    """本地Embedding服务 - 单例模式，模型驻留内存"""
    
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
                    self._initialize_model()
                    LocalEmbeddingService._initialized = True
    
    def _initialize_model(self):
        """初始化模型，只执行一次"""
        try:
            # 优先从 system.conf 读取配置
            user_model_name = None
            cache_dir_config = None

            if CONFIG_UTIL_AVAILABLE and cfg:
                try:
                    # 确保配置已加载
                    if cfg.config is None:
                        cfg.load_config()

                    # 从 config_util 获取配置
                    user_model_name = cfg.embedding_model
                    cache_dir_config = cfg.embedding_cache_dir

                    if user_model_name:
                        logger.info(f"从 system.conf 读取配置: embedding_model={user_model_name}")
                    if cache_dir_config:
                        logger.info(f"从 system.conf 读取配置: embedding_cache_dir={cache_dir_config}")
                except Exception as e:
                    logger.warning(f"从 system.conf 读取配置失败: {e}")

            # 降级到 .env 或默认值
            if not user_model_name:
                user_model_name = os.getenv('LOCAL_EMBEDDING_MODEL', 'Qwen/Qwen3-Embedding-0.6B')
                logger.info(f"使用 .env 或默认配置: embedding_model={user_model_name}")

            if not cache_dir_config:
                cache_dir_config = os.getenv('LOCAL_EMBEDDING_CACHE_DIR', 'models/embeddings')
                logger.info(f"使用 .env 或默认配置: embedding_cache_dir={cache_dir_config}")

            # 处理相对路径
            if not os.path.isabs(cache_dir_config):
                cache_dir = os.path.join(os.getcwd(), cache_dir_config)
            else:
                cache_dir = cache_dir_config

            cache_dir_abs = os.path.abspath(cache_dir)

            # 按规则拼成路径
            model_path = os.path.join(cache_dir_abs, f"models--{user_model_name.replace('/', '--')}", "snapshots",
                                    "c54f2e6e80b2d7b7de06f51cec4959f6b3e03418")

            # 转换为绝对路径
            model_name_abs = os.path.abspath(model_path)


            logger.info(f"用户设置的模型名称: {user_model_name}")
            logger.info(f"按规则拼成的模型路径: {model_path}")
            logger.info(f"程序实际使用的模型绝对路径: {model_name_abs}")
            logger.info(f"程序实际使用的缓存绝对路径: {cache_dir_abs}")
            logger.info(f"模型路径是否存在: {os.path.exists(model_name_abs)}")
            logger.info(f"缓存路径是否存在: {os.path.exists(cache_dir_abs)}")
            
            # 检查路径是否存在，如果不存在则自动下载
            if not os.path.exists(model_name_abs):
                logger.info(f"模型路径不存在: {model_name_abs}")
                logger.info("开始自动下载模型...")
                
                # 确保缓存目录存在
                os.makedirs(cache_dir_abs, exist_ok=True)
                
                # 使用 SentenceTransformer 自动下载模型
                logger.info(f"正在下载模型: {user_model_name}")
                self.model = SentenceTransformer(user_model_name, cache_folder=cache_dir_abs)
                logger.info("模型下载完成！")
            else:
                logger.info(f"使用本地模型: {model_name_abs}")
                # 使用绝对路径
                self.model = SentenceTransformer(model_name_abs, cache_folder=cache_dir_abs)
            
            # 设置为评估模式
            self.model.eval()
            
            # 如果支持GPU，使用GPU
            if torch.cuda.is_available():
                self.model = self.model.cuda()
                logger.info("使用GPU加速")
            else:
                logger.info("使用CPU")
            
            logger.info(f"{model_name_abs}模型加载完成")
            logger.info(f"模型缓存路径: {cache_dir_abs}")
            
            # 保存配置信息
            self.model_name = user_model_name
            self.cache_dir = cache_dir
            
        except Exception as e:
            logger.error(f"{model_name_abs}模型加载失败: {e}")
            raise
    
    def encode_text(self, text: str) -> List[float]:
        """编码单个文本"""
        try:
            # 使用驻留的模型进行编码
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()  # 转换为list
        except Exception as e:
            logger.error(f"文本编码失败: {e}")
            raise
    
    def encode_texts(self, texts: List[str]) -> List[List[float]]:
        """批量编码文本"""
        try:
            # 使用驻留的模型进行批量编码
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()  # 转换为list
        except Exception as e:
            logger.error(f"批量文本编码失败: {e}")
            raise
    
    def get_model_info(self) -> dict:
        """获取模型信息"""
        return {
            "model_name": getattr(self, 'model_name', 'Qwen/Qwen3-Embedding-0.6B'),
            "embedding_dim": 1024,
            "device": "cuda" if torch.cuda.is_available() else "cpu",
            "initialized": self._initialized,
            "cache_dir": getattr(self, 'cache_dir', os.path.join(os.getcwd(), "ChromaWithForgetting", "models", "embeddings"))
        }

# 导入 API Embedding 服务
from bionicmemory.services.api_embedding_service import ApiEmbeddingService

# 全局实例
_global_embedding_service = None

def get_embedding_service() -> ApiEmbeddingService:
    """获取全局embedding服务实例（现在返回 API 服务）"""
    global _global_embedding_service
    if _global_embedding_service is None:
        _global_embedding_service = ApiEmbeddingService()
    return _global_embedding_service

"""
摘要生成服务
基于 ChatHelper 实现长内容摘要功能
"""

import logging
import os
from typing import Optional
from dotenv import load_dotenv

from bionicmemory.services.chat_helper import ChatHelper

# 使用统一日志配置
from bionicmemory.utils.logging_config import get_logger
logger = get_logger(__name__)

# 加载环境变量
load_dotenv()

class SummaryService:
    """摘要生成服务"""
    
    def __init__(self):
        """初始化摘要服务"""
        # 从环境变量读取配置
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('OPENAI_API_BASE')
        self.model_name = os.getenv('OPENAI_MODEL_NAME')
        self.summary_max_length = int(os.getenv('SUMMARY_MAX_LENGTH', '500'))
        
        # 验证必需配置
        if not self.api_key:
            raise ValueError("缺少必需的环境变量: OPENAI_API_KEY")
        if not self.base_url:
            raise ValueError("缺少必需的环境变量: OPENAI_API_BASE")
        if not self.model_name:
            raise ValueError("缺少必需的环境变量: OPENAI_MODEL_NAME")
        
        # 初始化LLM助手
        self.chat_helper = ChatHelper(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        logger.info(f"摘要服务初始化完成")
        logger.info(f"使用模型: {self.model_name}")
        logger.info(f"摘要最大长度: {self.summary_max_length}")
    
    def generate_summary(self, content: str, max_length: Optional[int] = None) -> str:
        """
        生成内容摘要
        
        Args:
            content: 原始内容
            max_length: 摘要最大长度，如果不提供则使用环境变量配置
            
        Returns:
            str: 生成的摘要
        """
        if not content:
            return ""
        
        # 如果内容长度小于阈值，直接返回原内容
        if len(content) <= self.summary_max_length:
            return content
        
        try:
            # 构建摘要提示词
            prompt = self._build_summary_prompt(content, max_length or self.summary_max_length)
            
            # 调用LLM生成摘要
            summary = self.chat_helper.generate_text(
                prompt=prompt,
                model=self.model_name,
                max_tokens=max_length or self.summary_max_length,
                temperature=0.3,  # 低温度，确保摘要的准确性
                top_p=0.8
            )
            
            # 清理摘要内容
            summary = self._clean_summary(summary)
            
            logger.info(f"摘要生成成功: {len(content)} -> {len(summary)} 字符")
            return summary
            
        except Exception as e:
            logger.error(f"摘要生成失败: {e}")
            # 降级到简单截断
            return self._fallback_summary(content, max_length or self.summary_max_length)
    
    def _build_summary_prompt(self, content: str, max_length: int) -> str:
        """
        构建摘要生成提示词
        
        Args:
            content: 原始内容
            max_length: 摘要最大长度
            
        Returns:
            str: 构建的提示词
        """
        prompt = f"""请为以下内容生成一个简洁的摘要，要求：

1. 摘要长度控制在 {max_length} 字符以内
2. 保留核心信息和关键要点
3. 使用简洁明了的语言
4. 确保摘要的完整性和准确性

原始内容：
{content}

请生成摘要："""
        
        return prompt
    
    def _clean_summary(self, summary: str) -> str:
        """
        清理摘要内容
        
        Args:
            summary: 原始摘要
            
        Returns:
            str: 清理后的摘要
        """
        if not summary:
            return ""
        
        # 移除多余的空白字符
        summary = summary.strip()
        
        # 移除可能的提示词残留
        summary = summary.replace("摘要：", "").replace("摘要:", "")
        summary = summary.replace("总结：", "").replace("总结:", "")
        
        # 如果摘要以引号开始和结束，移除引号
        if summary.startswith('"') and summary.endswith('"'):
            summary = summary[1:-1]
        if summary.startswith("'") and summary.endswith("'"):
            summary = summary[1:-1]
        
        return summary.strip()
    
    def _fallback_summary(self, content: str, max_length: int) -> str:
        """
        降级摘要方案（简单截断）
        
        Args:
            content: 原始内容
            max_length: 最大长度
            
        Returns:
            str: 截断后的内容
        """
        logger.warning("使用降级摘要方案：简单截断")
        
        # 尝试在句号处截断
        summary = content[:max_length]
        
        # 查找最后一个句号位置
        last_period = summary.rfind('。')
        if last_period > max_length * 0.8:  # 如果句号在80%位置之后
            summary = summary[:last_period + 1]
        
        # 如果内容被截断，添加省略号
        if len(content) > max_length:
            summary += "..."
        
        return summary
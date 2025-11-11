import logging
import openai
from typing import List

# 使用统一日志配置
from bionicmemory.utils.logging_config import get_logger

class ChatHelper:
    """聊天助手类，专门处理LLM聊天功能"""
    
    def __init__(self, api_key: str, base_url: str):
        """
        初始化聊天助手
        
        Args:
            api_key: API密钥（必须）
            base_url: API基础URL（必须）
        """
        if not api_key or not base_url:
            raise ValueError("api_key和base_url是必须参数")
        
        self.api_key = api_key
        self.base_url = base_url
        
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        self.logger = get_logger(__name__)
        self.logger.info("聊天助手初始化完成")
    
    def create_chat_completions(self, model: str, messages: List[dict], stream: bool = False, 
                               top_p: float = 0.5, temperature: float = 0.2, user: str = None):
        """
        创建聊天完成
        
        Args:
            model: 模型名称（必须）
            messages: 消息列表（必须）
            stream: 是否流式输出
            top_p: 核采样参数
            temperature: 温度参数
            user: 用户标识
        """
        if not model or not messages:
            raise ValueError("model和messages参数是必须的")
        
        kwargs = {
            "model": model,
            "messages": messages,
            "top_p": top_p,
            "temperature": temperature,
            "stream": stream
        }
        
        if user:
            kwargs["user"] = user
            
        completion = self.client.chat.completions.create(**kwargs)
        return completion

    def generate_text(self, prompt: str, model: str, max_tokens: int = 500, 
                     temperature: float = 0.2, top_p: float = 0.5) -> str:
        """
        生成文本内容
        
        Args:
            prompt: 提示词（必须）
            model: 模型名称（必须）
            max_tokens: 最大生成token数
            temperature: 温度参数
            top_p: 核采样参数
            
        Returns:
            str: 生成的文本内容
        """
        if not prompt or not model:
            raise ValueError("prompt和model参数是必须的")
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p
            )
            
            generated_text = response.choices[0].message.content
            self.logger.debug(f"成功生成文本，长度: {len(generated_text)}")
            return generated_text
            
        except Exception as e:
            error_msg = f"生成文本失败: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    def get_models(self):
        """获取可用模型列表"""
        models = self.client.models.list()
        return [model.id for model in models.data]

    def get_model(self, model_id):
        """获取特定模型详情"""
        model = self.client.models.retrieve(model_id)
        return model

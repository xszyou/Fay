"""
基于OpenAI官方库的代理服务器
使用OpenAI官方客户端处理所有请求，确保完全兼容
"""

from contextlib import asynccontextmanager
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from fastapi import FastAPI, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

# OpenAI官方库
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.embedding import Embedding

# BionicMemory核心组件
from bionicmemory.core.memory_system import LongShortTermMemorySystem, SourceType
from bionicmemory.services.memory_cleanup_scheduler import MemoryCleanupScheduler
from bionicmemory.core.chroma_service import ChromaService
from bionicmemory.algorithms.newton_cooling_helper import CoolingRate
from bionicmemory.services.local_embedding_service import get_embedding_service

# 使用统一日志配置
from bionicmemory.utils.logging_config import get_logger
logger = get_logger(__name__)

# ========== 环境变量配置 ==========
# 禁用ChromaDB遥测
os.environ["ANONYMIZED_TELEMETRY"] = "False"

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))
CHROMA_CLIENT_TYPE = os.getenv("CHROMA_CLIENT_TYPE", "persistent")

# ========== OpenAI配置 ==========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "deepseek-chat")

# 记忆系统配置
SUMMARY_MAX_LENGTH = int(os.getenv('SUMMARY_MAX_LENGTH', '500'))
MAX_RETRIEVAL_RESULTS = int(os.getenv('MAX_RETRIEVAL_RESULTS', '7'))
CLUSTER_MULTIPLIER = int(os.getenv('CLUSTER_MULTIPLIER', '3'))
RETRIEVAL_MULTIPLIER = int(os.getenv('RETRIEVAL_MULTIPLIER', '2'))

# ========== 工具函数 ==========

def extract_user_message(messages: List[Dict]) -> Optional[str]:
    """从消息列表中提取用户消息"""
    for message in reversed(messages):  # 从最新消息开始查找
        if message.get("role") == "user":
            return message.get("content", "")
    return None

def extract_user_id_from_request(body_data: Dict) -> str:
    """从OpenAI请求中提取用户ID"""
    try:
        logger.info("🔍 开始提取用户ID...")
        
        # 1. 优先从对话协议中的user字段提取
        if "user" in body_data:
            raw_user = body_data["user"]
            if isinstance(raw_user, str) and raw_user.strip():
                user_id = raw_user.strip()
                logger.info(f"✅ 使用对话协议user字段: {user_id}")
                return user_id
        
        # 2. 默认值：default_user
        user_id = "default_user"
        logger.info(f"✅ 使用默认用户ID: {user_id}")
        return user_id
        
    except Exception as e:
        logger.error(f"❌ 提取用户ID失败: {e}")
        return "default_user"

def enhance_chat_with_memory(body_data: Dict, user_id: str) -> Tuple[Dict, List[float]]:
    """
    使用记忆系统增强聊天请求
    
    Args:
        body_data: 请求体数据
        user_id: 用户ID
    
    Returns:
        (增强后的body_data, enhanced_query_embedding)
    """
    global memory_system
    
    if not memory_system:
        logger.warning("⚠️ 记忆系统未初始化，跳过记忆增强")
        return body_data, None
    
    try:
        messages = body_data.get("messages", [])
        if not messages:
            return body_data, None
        
        # 提取用户消息
        user_message = extract_user_message(messages)
        if not user_message:
            return body_data, None
        
        # 使用记忆系统处理用户消息
        short_term_records, system_prompt, query_embedding = memory_system.process_user_message(
            user_message, user_id
        )
        
        if short_term_records:
            logger.info(f"🧠 找到 {len(short_term_records)} 条相关记忆")
            logger.info(f"🧠 生成的系统提示语长度: {len(system_prompt)}")
            
            # 直接使用memory_system生成的系统提示语作为系统消息
            system_message = {
                "role": "system",
                "content": system_prompt
            }
            
            # 在用户消息前插入系统消息
            enhanced_messages = [system_message] + (messages[-3:] if len(messages) > 3 else messages)
            body_data["messages"] = enhanced_messages
            
            logger.info(f"🧠 记忆增强完成，消息数量: {len(messages)} -> {len(enhanced_messages)}")
            logger.info(f"🧠 记忆增强完成，消息内容: {enhanced_messages}")
        
        return body_data, query_embedding
        
    except Exception as e:
        logger.error(f"❌ 记忆增强失败: {e}")
        return body_data, None

async def process_ai_reply_async(response_content: str, user_id: str, current_user_content: str = None):
    """异步处理AI回复（不阻塞响应性能）"""
    global memory_system
    
    if not memory_system:
        return
    
    try:
        # 执行记忆系统处理（正确的业务逻辑顺序）
        await memory_system.process_agent_reply_async(response_content, user_id, current_user_content)
        
    except Exception as e:
        logger.error(f"❌ 异步处理AI回复失败: {e}")

# ========== 全局变量 ==========
memory_system = None
memory_cleanup_scheduler = None
chroma_service = None

# OpenAI客户端
openai_client = None
async_openai_client = None

# ========== 初始化函数 ==========

def initialize_memory_system():
    """初始化记忆系统"""
    global memory_system, memory_cleanup_scheduler, chroma_service
    
    try:
        logger.info("正在初始化记忆系统...")
        
        # 初始化ChromaDB服务（只使用本地embedding）
        chroma_service = ChromaService()
        logger.info("ChromaDB服务初始化完成（本地embedding模式）")
        
        # 初始化记忆系统
        memory_system = LongShortTermMemorySystem(
            chroma_service=chroma_service,
            summary_threshold=SUMMARY_MAX_LENGTH,
            max_retrieval_results=MAX_RETRIEVAL_RESULTS,
            cluster_multiplier=CLUSTER_MULTIPLIER,
            retrieval_multiplier=RETRIEVAL_MULTIPLIER,
        )
        
        # 启动时清空短期记忆库
        try:
            # 清空短期记忆库
            short_term_deleted_ids = chroma_service.delete_documents(
                memory_system.short_term_collection_name
            )
            logger.info(f"启动清空短期记忆库，删除 {len(short_term_deleted_ids)} 条记录")
            
        except Exception as _e:
            logger.warning("启动清空短期记忆库失败", exc_info=True)
        
        # 初始化清理调度器
        memory_cleanup_scheduler = MemoryCleanupScheduler(memory_system=memory_system)
        memory_cleanup_scheduler.start()
        
        logger.info("记忆系统初始化完成")
        return True
    except Exception as e:
        logger.error(f"记忆系统初始化失败: {str(e)}", exc_info=True)
        return False

def initialize_openai_clients():
    """初始化OpenAI客户端"""
    global openai_client, async_openai_client
    
    try:
        logger.info("正在初始化OpenAI客户端...")
        
        # 同步客户端
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE
        )
        
        # 异步客户端
        async_openai_client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE
        )
        
        logger.info("OpenAI客户端初始化完成")
        return True
    except Exception as e:
        logger.error(f"OpenAI客户端初始化失败: {e}")
        return False

# ========== 生命周期事件处理器 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    initialize_memory_system()
    initialize_openai_clients()
    yield
    # 关闭时清理
    if memory_cleanup_scheduler:
        memory_cleanup_scheduler.stop()
        logger.info("记忆清理调度器已停止")

# ========== FastAPI应用初始化 ==========
app = FastAPI(title="BionicMemory OpenAI Proxy", version="2.0.0", lifespan=lifespan)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 健康检查端点 ==========
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "BionicMemory OpenAI Proxy",
        "timestamp": datetime.now().isoformat(),
        "memory_system_initialized": memory_system is not None,
        "openai_client_initialized": openai_client is not None,
        "cleanup_scheduler_running": memory_cleanup_scheduler is not None if memory_cleanup_scheduler else False
    }

# ========== 主要路由处理 ==========
@app.api_route("/v1/{path:path}", methods=["POST", "GET"])
async def proxy(request: Request, path: str):
    """
    代理所有 /v1/* 请求
    使用OpenAI官方库处理，确保完全兼容
    """
    body = await request.body()
    
    # 记录基本请求信息
    logger.info(f"📥 收到请求: {request.method} /v1/{path}")
    
    # ========== 路由处理 ==========
    if path.startswith("embeddings"):
        # Embedding API - 使用本地embedding服务
        return await handle_embedding_request(request, path, body)
        
    elif path == "chat/completions":
        # Chat Completions API - 使用OpenAI客户端 + 记忆增强
        return await handle_chat_request(request, path, body)
        
    else:
        # 其他 API - 使用OpenAI客户端透传
        return await handle_other_request(request, path, body)

# ========== 处理函数 ==========

async def handle_embedding_request(request: Request, path: str, body: bytes):
    """处理embedding请求 - 使用本地embedding服务"""
    try:
        # 解析请求体
        if body:
            body_data = json.loads(body)
            input_text = body_data.get("input", "")
            model = body_data.get("model", "")
            
            # 使用本地embedding服务
            logger.info("使用本地embedding服务")
            embedding_service = get_embedding_service()
            embeddings = embedding_service.get_embeddings([input_text])
            
            # 构造OpenAI兼容的响应
            response_data = {
                "object": "list",
                "data": [{
                    "object": "embedding",
                    "index": 0,
                    "embedding": embeddings[0]
                }],
                "model": model,
                "usage": {
                    "prompt_tokens": len(input_text.split()),
                    "total_tokens": len(input_text.split())
                }
            }
            
            return JSONResponse(content=response_data)
                
    except Exception as e:
        logger.error(f"❌ 处理embedding请求失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"处理embedding请求失败: {str(e)}"}
        )

async def handle_chat_request(request: Request, path: str, body: bytes):
    """处理对话请求 - 使用OpenAI客户端 + 记忆增强"""
    try:
        # 解析请求体
        body_data = None
        user_id = None
        enhanced_query_embedding = None
        current_user_content = None
        
        if body:
            body_data = json.loads(body)
            # 提取用户ID
            user_id = extract_user_id_from_request(body_data)
            
            # 替换模型名称
            if "model" in body_data:
                body_data["model"] = OPENAI_MODEL_NAME
            
            # 记忆增强处理
            enhanced_body_data, query_embedding = enhance_chat_with_memory(body_data, user_id)
            current_user_content = body_data.get("messages", [])[-1].get("content", "")
            body_data = enhanced_body_data
        
        # 检查是否为流式响应
        is_stream = body_data and body_data.get("stream", False) if body_data else False
        
        if is_stream:
            # 流式响应 - 使用异步OpenAI客户端
            logger.info("🌊 处理流式响应（使用OpenAI客户端）")
            
            try:
                # 使用OpenAI客户端创建流式响应
                stream = await async_openai_client.chat.completions.create(
                    model=body_data.get("model", OPENAI_MODEL_NAME),
                    messages=body_data.get("messages", []),
                    stream=True,
                    **{k: v for k, v in body_data.items() 
                       if k not in ["model", "messages", "stream"]}
                )
                
                async def openai_stream_wrapper():
                    full_content = ""
                    async for chunk in stream:
                        # 使用OpenAI原生格式
                        chunk_data = chunk.model_dump()
                        content = chunk_data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if content:
                            full_content += content
                        
                        # 转换为SSE格式
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                    # 流式结束后异步存储记忆
                    if full_content and body_data:
                        asyncio.create_task(process_ai_reply_async(
                            full_content, user_id, current_user_content
                        ))
                    
                    yield "data: [DONE]\n\n"
                
                return StreamingResponse(
                    openai_stream_wrapper(),
                    status_code=200,
                    headers={
                        "Content-Type": "text/plain; charset=utf-8",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive"
                    }
                )
                
            except Exception as e:
                logger.error(f"❌ OpenAI流式处理失败: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"流式处理失败: {str(e)}"}
                )
        else:
            # 非流式响应 - 使用同步OpenAI客户端
            logger.info("📝 处理非流式响应（使用OpenAI客户端）")
            
            try:
                response = openai_client.chat.completions.create(
                    model=body_data.get("model", OPENAI_MODEL_NAME),
                    messages=body_data.get("messages", []),
                    **{k: v for k, v in body_data.items() 
                       if k not in ["model", "messages"]}
                )
                
                # 异步存储记忆
                if response.choices[0].message.content and body_data:
                    asyncio.create_task(process_ai_reply_async(
                        response.choices[0].message.content, 
                        user_id, 
                        current_user_content
                    ))
                
                # 返回OpenAI原生响应
                return JSONResponse(content=response.model_dump())
                
            except Exception as e:
                logger.error(f"❌ OpenAI非流式处理失败: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"非流式处理失败: {str(e)}"}
                )
            
    except Exception as e:
        logger.error(f"❌ 处理对话请求失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"处理对话请求失败: {str(e)}"}
        )

async def handle_other_request(request: Request, path: str, body: bytes):
    """处理其他API - 使用OpenAI客户端透传"""
    try:
        # 解析请求体
        body_data = json.loads(body) if body else {}
        
        # 使用OpenAI客户端处理其他请求
        logger.info(f"🔄 处理其他请求: {path}")
        
        # 根据路径选择处理方法
        if path == "models":
            # 模型列表请求
            models_response = {
                "object": "list",
                "data": [
                    {
                        "id": OPENAI_MODEL_NAME,
                        "object": "model",
                        "created": int(datetime.now().timestamp()),
                        "owned_by": "bionicmemory"
                    }
                ]
            }
            return JSONResponse(content=models_response)
        
        else:
            # 其他请求透传
            try:
                # 使用OpenAI客户端处理
                if request.method == "GET":
                    # GET请求处理
                    response = openai_client._client.get(f"/v1/{path}")
                    return JSONResponse(content=response.json())
                else:
                    # POST请求处理
                    response = openai_client._client.post(
                        f"/v1/{path}",
                        json=body_data,
                        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
                    )
                    return JSONResponse(content=response.json())
                    
            except Exception as e:
                logger.error(f"❌ OpenAI客户端处理其他请求失败: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"处理请求失败: {str(e)}"}
                )
        
    except Exception as e:
        logger.error(f"❌ 处理其他请求失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"处理其他请求失败: {str(e)}"}
        )

# ========== 启动配置 ==========
if __name__ == "__main__":
    uvicorn.run(
        "bionicmemory.api.proxy_server_openai:app",
        host=API_HOST,
        port=API_PORT,
        log_level="info",
        access_log=True,
        reload=False
    )

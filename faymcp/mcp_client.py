#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import time
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client

# 设置日志记录
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class McpClient:
    """
    MCP客户端类，用于连接MCP服务器并调用其工具
    """
    def __init__(self, server_url, api_key=None):
        """
        初始化MCP客户端
        :param server_url: MCP服务器URL
        :param api_key: MCP服务器API密钥（可选）
        """
        self.server_url = server_url
        self.api_key = api_key
        self.session = None
        self.tools = None
        self.connected = False
        self.event_loop = None
        self._ensure_event_loop()
        
    def _ensure_event_loop(self):
        """
        确保有可用的事件循环
        """
        try:
            self.event_loop = asyncio.get_event_loop()
        except RuntimeError:
            # 如果当前线程没有事件循环，创建一个新的
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
    
    async def _connect_async(self):
        """
        异步连接到MCP服务器
        """
        try:
            # 创建退出栈
            self.exit_stack = AsyncExitStack()
            
            logger.info(f"正在连接到 SSE 服务: {self.server_url}")
            # 准备请求头，如果有API密钥则添加到请求头中
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
                
            # 增加超时设置
            streams = await self.exit_stack.enter_async_context(
                sse_client(url=self.server_url, timeout=60, headers=headers)  # 增加超时时间到60秒并传递请求头
            )
            logger.info("SSE 连接已建立")
            
            # 创建会话
            self.session = await self.exit_stack.enter_async_context(ClientSession(*streams))
            await self.session.initialize()
            logger.info("会话已创建")
            
            # 获取工具列表
            logger.info("正在获取工具列表...")
            try:
                # 使用asyncio.wait_for添加超时控制
                tools_response = await asyncio.wait_for(self.session.list_tools(), timeout=30)
                logger.info(f"可用工具: {tools_response}")
                
                # 提取工具列表
                if hasattr(tools_response, 'tools') and tools_response.tools:
                    self.tools = tools_response.tools
                else:
                    # 如果返回的是直接的工具列表
                    self.tools = tools_response
                
                self.connected = True
                return True, self.tools
            except asyncio.TimeoutError:
                logger.error("获取工具列表超时")
                return False, "获取工具列表超时"
                
        except Exception as e:
            logger.error(f"连接或调用过程中出错: {e}")
            error_msg = str(e)
            # 检查是否是网络相关错误
            if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                logger.error("网络连接问题，请检查网络或服务器状态")
                return False, "网络连接问题，请检查网络或服务器状态"
            # 检查是否是认证错误
            elif "auth" in error_msg.lower() or "unauthorized" in error_msg.lower():
                logger.error("可能存在认证问题，请检查是否需要提供 API 密钥")
                return False, "认证问题，请检查是否需要提供 API 密钥"
            # 检查是否是SSE相关错误
            elif "sse" in error_msg.lower() or "stream" in error_msg.lower():
                logger.error("SSE流处理错误，可能是服务器提前关闭了连接")
                return False, "SSE流处理错误，可能是服务器提前关闭了连接"
            return False, f"连接错误: {error_msg}"
    
    def connect(self):
        """
        连接到MCP服务器
        :return: (是否成功, 工具列表或错误信息)
        """
        return self.event_loop.run_until_complete(self._connect_async())
    
    async def _call_tool_async(self, method, params=None):
        """
        异步调用MCP工具
        :param method: 方法名
        :param params: 参数字典
        :return: 调用结果
        """
        if not self.connected or not self.session:
            return False, "未连接到MCP服务器"
            
        try:
            if params is None:
                params = {}
                
            logger.info(f"调用工具: {method}, 参数: {params}")
            result = await asyncio.wait_for(self.session.call_tool(method, params), timeout=30)
            logger.info(f"调用结果: {result}")
            return True, result
        except Exception as e:
            return False, f"调用工具失败: {str(e)}"
    
    def call_tool(self, method, params=None):
        """
        调用MCP工具
        :param method: 方法名
        :param params: 参数字典
        :return: (是否成功, 结果或错误信息)
        """
        return self.event_loop.run_until_complete(self._call_tool_async(method, params))
    
    def list_tools(self):
        """
        获取可用工具列表
        :return: 工具列表
        """
        if not self.connected:
            success, result = self.connect()
            if not success:
                return []
        return self.tools or []
    
    def disconnect(self):
        """
        断开与MCP服务器的连接
        """
        if self.connected and self.exit_stack:
            try:
                self.event_loop.run_until_complete(self.exit_stack.aclose())
                self.connected = False
                self.session = None
                logger.info("已断开与MCP服务器的连接")
                return True
            except Exception as e:
                logger.error(f"断开连接时出错: {e}")
                return False
        return True  # 如果本来就没连接，也返回成功

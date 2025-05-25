"""
Claude API处理器实现
"""

import json
import os
from typing import Dict, Any, List, Optional, Union
from anthropic import AsyncAnthropic

from ..core.config import get_settings
from ..core.logger import get_logger
from ..core.exceptions import ClaudeAPIError, ToolCallError
from ..utils.helpers import retry_async, generate_request_id
from .amap_client import AmapMCPClient


class ClaudeHandler:
    """Claude API处理器"""
    
    def __init__(self, amap_client: AmapMCPClient):
        self.settings = get_settings()
        self.logger = get_logger("claude_handler")
        self.amap_client = amap_client
        
        # 设置代理环境变量（如果启用）
        self._setup_proxies()
        
        # 初始化Claude客户端
        self.anthropic = AsyncAnthropic(
            api_key=self.settings.anthropic_api_key,
            # 添加额外的配置参数
            timeout=60.0,  # 设置超时时间
            max_retries=2,   # 设置最大重试次数
            # 添加代理配置（如果启用）
            http_client=self._get_http_client() if self.settings.proxy_enabled else None
        )
        
        # 工具缓存
        self._claude_tools: Optional[List[Dict[str, Any]]] = None
    
    def _setup_proxies(self):
        """设置代理环境变量（如果启用）"""
        if self.settings.proxy_enabled:
            self.logger.info("代理配置已启用，正在设置环境变量")
            
            # 设置代理环境变量
            if self.settings.http_proxy:
                os.environ["http_proxy"] = self.settings.http_proxy
                self.logger.debug(f"已设置HTTP代理: {self.settings.http_proxy}")
                
            if self.settings.https_proxy:
                os.environ["https_proxy"] = self.settings.https_proxy
                self.logger.debug(f"已设置HTTPS代理: {self.settings.https_proxy}")
                
            if self.settings.all_proxy:
                os.environ["ALL_PROXY"] = self.settings.all_proxy
                self.logger.debug(f"已设置ALL_PROXY代理: {self.settings.all_proxy}")
        else:
            self.logger.debug("代理配置未启用")
    
    def _get_http_client(self):
        """获取配置了代理的HTTP客户端"""
        try:
            import httpx
            
            # 构建单一代理URL，优先使用HTTPS代理，其次HTTP代理，最后是ALL_PROXY
            proxy = None
            if self.settings.https_proxy:
                proxy = self.settings.https_proxy
            elif self.settings.http_proxy:
                proxy = self.settings.http_proxy
            elif self.settings.all_proxy:
                proxy = self.settings.all_proxy
            
            if proxy:
                self.logger.info(f"为Anthropic客户端创建代理配置: {proxy}")
                # 创建并返回带有代理配置的httpx客户端实例
                client = httpx.AsyncClient(proxy=proxy)
                return client
            else:
                return None
        except ImportError:
            self.logger.warning("未安装httpx库，无法创建自定义HTTP客户端")
            return None
    
    @retry_async(max_retries=2, delay=1.0)
    async def process_query(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理用户查询
        
        Args:
            query: 用户查询内容
            context: 额外上下文信息
            system_prompt: 系统提示词
            
        Returns:
            处理结果
        """
        request_id = generate_request_id()
        
        try:
            self.logger.info("开始处理Claude查询", 
                           request_id=request_id, 
                           query_length=len(query))
            
            # 准备工具列表
            tools = await self._prepare_tools()
            
            # 构建消息
            messages = self._build_messages(query, context)
            
            # 构建系统提示词
            system = system_prompt or self._build_system_prompt()
            
            # 调用Claude API
            try:
                response = await self.anthropic.messages.create(
                    model=self.settings.claude_model,
                    max_tokens=self.settings.claude_max_tokens,
                    messages=messages,
                    tools=tools if tools else None,  # 确保工具参数正确
                    system=system,
                    # 添加额外的API参数
                    temperature=0.7,  # 控制随机性
                    # anthropic_version="2023-06-01"  # 指定API版本（可选）
                )
            except Exception as api_error:
                self.logger.error(
                    "Claude API调用失败", 
                    request_id=request_id,
                    model=self.settings.claude_model,
                    api_error=str(api_error),
                    api_key_prefix=self.settings.anthropic_api_key[:10] + "..." if self.settings.anthropic_api_key else "None"
                )
                raise ClaudeAPIError(f"Claude API调用失败: {api_error}")
            
            # 处理响应和工具调用
            result = await self._handle_response(response, messages, tools, request_id)
            
            self.logger.info("Claude查询处理完成", request_id=request_id)
            return result
            
        except Exception as e:
            self.logger.error("Claude查询处理失败", 
                            request_id=request_id, 
                            error=str(e))
            raise ClaudeAPIError(f"查询处理失败: {e}")
    
    async def _prepare_tools(self) -> List[Dict[str, Any]]:
        """准备Claude工具列表"""
        if self._claude_tools is None:
            try:
                # 获取MCP工具列表
                mcp_tools = await self.amap_client.list_available_tools()
                
                # 转换为Claude工具格式
                self._claude_tools = [
                    {
                        "name": tool["name"],
                        "description": tool["description"],
                        "input_schema": tool["input_schema"]
                    }
                    for tool in mcp_tools
                ]
                
                self.logger.info("工具列表准备完成", tools_count=len(self._claude_tools))
                
            except Exception as e:
                self.logger.error("准备工具列表失败", error=str(e))
                self._claude_tools = []
        
        return self._claude_tools
    
    def _build_messages(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """构建消息列表"""
        messages = []
        
        # 添加上下文信息（如果有）
        if context:
            context_text = self._format_context(context)
            if context_text:
                messages.append({
                    "role": "user",
                    "content": f"上下文信息：{context_text}\n\n用户查询：{query}"
                })
            else:
                messages.append({
                    "role": "user", 
                    "content": query
                })
        else:
            messages.append({
                "role": "user",
                "content": query
            })
        
        return messages
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的地址解析助手，能够使用高德地图API来帮助用户解析地址、获取地理信息。

你的主要功能包括：
1. 地址解析和标准化
2. 地理编码（地址转坐标）
3. 逆地理编码（坐标转地址）
4. POI（兴趣点）搜索
5. 路径规划和距离计算

使用指南：
- 当用户提供地址时，优先使用地理编码工具获取精确坐标
- 当用户提供坐标时，使用逆地理编码获取详细地址信息
- 对于模糊地址，尝试使用POI搜索找到最匹配的结果
- 始终提供清晰、准确的中文回复
- 如果遇到错误，请友好地解释问题并建议解决方案

请根据用户的具体需求选择合适的工具，并提供有用的地理信息。"""
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """格式化上下文信息"""
        if not context:
            return ""
        
        formatted_parts = []
        
        # 处理常见的上下文字段
        if "location" in context:
            formatted_parts.append(f"当前位置：{context['location']}")
        
        if "city" in context:
            formatted_parts.append(f"所在城市：{context['city']}")
        
        if "preferences" in context:
            formatted_parts.append(f"用户偏好：{context['preferences']}")
        
        # 处理其他字段
        for key, value in context.items():
            if key not in ["location", "city", "preferences"]:
                formatted_parts.append(f"{key}：{value}")
        
        return "；".join(formatted_parts)
    
    async def _handle_response(
        self, 
        response: Any, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]],
        request_id: str
    ) -> Dict[str, Any]:
        """处理Claude响应和工具调用"""
        result = {
            "request_id": request_id,
            "success": True,
            "response": "",
            "tool_calls": [],
            "final_answer": ""
        }
        
        try:
            # 处理响应内容
            response_parts = []
            assistant_content = []
            
            for content in response.content:
                if content.type == 'text':
                    response_parts.append(content.text)
                    assistant_content.append(content)
                elif content.type == 'tool_use':
                    # 执行工具调用
                    tool_result = await self._execute_tool_call(content, request_id)
                    result["tool_calls"].append(tool_result)
                    
                    assistant_content.append(content)
                    
                    # 添加工具调用到消息历史
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content
                    })
                    
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": tool_result["result"]
                            }
                        ]
                    })
                    
                    # 获取工具调用后的响应
                    follow_up_response = await self.anthropic.messages.create(
                        model=self.settings.claude_model,
                        max_tokens=self.settings.claude_max_tokens,
                        messages=messages,
                        tools=tools
                    )
                    
                    # 处理后续响应
                    for follow_content in follow_up_response.content:
                        if follow_content.type == 'text':
                            response_parts.append(follow_content.text)
            
            result["response"] = "\n".join(response_parts)
            result["final_answer"] = result["response"]
            
            return result
            
        except Exception as e:
            self.logger.error("处理Claude响应失败", 
                            request_id=request_id, 
                            error=str(e))
            result["success"] = False
            result["error"] = str(e)
            return result
    
    async def _execute_tool_call(
        self, 
        tool_call: Any, 
        request_id: str
    ) -> Dict[str, Any]:
        """执行工具调用"""
        tool_result = {
            "tool_name": tool_call.name,
            "arguments": tool_call.input,
            "success": False,
            "result": None,
            "error": None
        }
        
        try:
            self.logger.info("执行工具调用", 
                           request_id=request_id,
                           tool_name=tool_call.name,
                           arguments=tool_call.input)
            
            # 调用MCP工具
            result = await self.amap_client.call_tool(
                tool_call.name, 
                tool_call.input
            )
            
            tool_result["success"] = True
            tool_result["result"] = result
            
            self.logger.info("工具调用成功", 
                           request_id=request_id,
                           tool_name=tool_call.name)
            
        except Exception as e:
            self.logger.error("工具调用失败", 
                            request_id=request_id,
                            tool_name=tool_call.name,
                            error=str(e))
            tool_result["error"] = str(e)
            tool_result["result"] = f"工具调用失败: {e}"
        
        return tool_result
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        return await self._prepare_tools()
    
    def clear_tools_cache(self) -> None:
        """清除工具缓存"""
        self._claude_tools = None
        self.logger.info("工具缓存已清除")
    
    async def test_api_connection(self) -> Dict[str, Any]:
        """
        测试Claude API连接
        
        Returns:
            测试结果
        """
        test_result = {
            "success": False,
            "error": None,
            "model": self.settings.claude_model,
            "api_key_configured": bool(self.settings.anthropic_api_key)
        }
        
        try:
            self.logger.info("开始测试Claude API连接")
            
            # 简单的测试消息
            simple_message = {
                "role": "user",
                "content": "Hello, can you respond with 'API connection successful'?"
            }
            
            response = await self.anthropic.messages.create(
                model=self.settings.claude_model,
                max_tokens=50,
                messages=[simple_message],
                temperature=0.1
            )
            
            if response and response.content:
                test_result["success"] = True
                test_result["response"] = response.content[0].text if response.content else ""
                self.logger.info("Claude API连接测试成功")
            else:
                test_result["error"] = "收到空响应"
                
        except Exception as e:
            test_result["error"] = str(e)
            self.logger.error("Claude API连接测试失败", error=str(e))
        
        return test_result
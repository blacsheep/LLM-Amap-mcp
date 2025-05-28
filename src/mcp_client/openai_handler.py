"""
OpenAI兼容API处理器实现
支持OpenAI、Azure OpenAI、以及其他兼容OpenAI API格式的LLM服务
"""

import json
import os
from typing import Dict, Any, List, Optional, Union
from openai import AsyncOpenAI

from ..core.config import get_settings
from ..core.logger import get_logger
from ..core.exceptions import ClaudeAPIError, ToolCallError
from ..utils.helpers import retry_async, generate_request_id
from .amap_client import AmapMCPClient
from .base_llm_handler import BaseLLMHandler


class OpenAIHandler(BaseLLMHandler):
    """OpenAI兼容API处理器"""
    
    def __init__(self, amap_client: AmapMCPClient):
        super().__init__(amap_client)
        
        # 设置代理环境变量（如果启用）
        self._setup_proxies()
        
        # 初始化OpenAI客户端
        client_kwargs = {
            "api_key": self.settings.openai_api_key,
            "timeout": 60.0,
            "max_retries": 2,
        }
        
        # 如果配置了自定义base_url，则使用它
        if self.settings.openai_base_url:
            client_kwargs["base_url"] = self.settings.openai_base_url
        
        # 添加代理配置（如果启用）
        if self.settings.proxy_enabled:
            http_client = self._get_http_client()
            if http_client:
                client_kwargs["http_client"] = http_client
        
        self.openai = AsyncOpenAI(**client_kwargs)
    
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
                self.logger.info(f"为OpenAI客户端创建代理配置: {proxy}")
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
            self.logger.info("开始处理OpenAI查询", 
                           request_id=request_id, 
                           query_length=len(query))
            
            # 准备工具列表
            tools = await self._prepare_openai_tools()
            
            # 构建消息
            messages = self._build_messages(query, context, system_prompt)
            
            # 调用OpenAI API
            try:
                completion_kwargs = {
                    "model": self.settings.openai_model,
                    "max_tokens": self.settings.openai_max_tokens,
                    "messages": messages,
                    "temperature": self.settings.openai_temperature,
                }
                
                # 只有在有工具时才添加tools参数
                if tools:
                    completion_kwargs["tools"] = tools
                    completion_kwargs["tool_choice"] = "auto"
                
                response = await self.openai.chat.completions.create(**completion_kwargs)
                
            except Exception as api_error:
                self.logger.error(
                    "OpenAI API调用失败", 
                    request_id=request_id,
                    model=self.settings.openai_model,
                    api_error=str(api_error),
                    api_key_prefix=self.settings.openai_api_key[:10] + "..." if self.settings.openai_api_key else "None"
                )
                raise ClaudeAPIError(f"OpenAI API调用失败: {api_error}")
            
            # 处理响应和工具调用
            result = await self._handle_response(response, messages, tools, request_id)
            
            self.logger.info("OpenAI查询处理完成", request_id=request_id)
            return result
            
        except Exception as e:
            self.logger.error("OpenAI查询处理失败", 
                            request_id=request_id, 
                            error=str(e))
            raise ClaudeAPIError(f"查询处理失败: {e}")
    
    async def _prepare_openai_tools(self) -> List[Dict[str, Any]]:
        """准备OpenAI工具列表"""
        mcp_tools = await self._prepare_tools()
        
        # 转换为OpenAI工具格式
        openai_tools = []
        for tool in mcp_tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]
                }
            }
            openai_tools.append(openai_tool)
        
        return openai_tools
    
    def _build_messages(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """构建消息列表"""
        messages = []
        
        # 添加系统消息
        system = system_prompt or self._build_system_prompt()
        messages.append({
            "role": "system",
            "content": system
        })
        
        # 添加用户消息（包含上下文）
        if context:
            context_text = self._format_context(context)
            if context_text:
                user_content = f"上下文信息：{context_text}\n\n用户查询：{query}"
            else:
                user_content = query
        else:
            user_content = query
        
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        return messages
    
    async def _handle_response(
        self, 
        response: Any, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]],
        request_id: str
    ) -> Dict[str, Any]:
        """处理OpenAI响应和工具调用"""
        result = {
            "request_id": request_id,
            "success": True,
            "response": "",
            "tool_calls": [],
            "final_answer": ""
        }
        
        try:
            current_response = response
            current_messages = messages.copy()
            response_parts = []
            
            # 循环处理直到没有更多工具调用
            max_iterations = self.settings.tool_max_iterations  # 使用配置的最大迭代次数
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                self.logger.info(
                    "开始处理第%d轮工具调用响应", 
                    iteration,
                    request_id=request_id
                )
                
                choice = current_response.choices[0]
                message = choice.message
                
                # 处理文本响应
                if message.content:
                    response_parts.append(message.content)
                
                # 检查是否有工具调用
                has_tool_calls = False
                if message.tool_calls:
                    has_tool_calls = True
                    
                    # 添加助手消息到历史
                    current_messages.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })
                    
                    # 执行工具调用
                    for tool_call in message.tool_calls:
                        try:
                            # 解析工具参数
                            arguments = json.loads(tool_call.function.arguments)
                            
                            # 执行工具调用
                            tool_result = await self._execute_tool_call(
                                tool_call.function.name,
                                arguments,
                                request_id
                            )
                            result["tool_calls"].append(tool_result)
                            
                            # 添加工具结果到消息历史
                            current_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(tool_result["result"], ensure_ascii=False)
                            })
                            
                        except json.JSONDecodeError as e:
                            self.logger.error("工具参数解析失败", 
                                            request_id=request_id,
                                            tool_name=tool_call.function.name,
                                            arguments=tool_call.function.arguments,
                                            error=str(e))
                            # 添加错误结果
                            current_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": f"参数解析失败: {e}"
                            })
                
                # 如果没有工具调用，则结束循环
                if not has_tool_calls:
                    self.logger.info(
                        "没有更多工具调用，处理完成",
                        request_id=request_id,
                        iteration=iteration
                    )
                    break
                    
                # 如果有工具调用，则继续下一轮
                try:
                    self.logger.info(
                        "发现工具调用，继续下一轮",
                        request_id=request_id,
                        iteration=iteration,
                        tools_count=len(result["tool_calls"])
                    )
                    
                    # 获取工具调用后的响应
                    current_response = await self.openai.chat.completions.create(
                        model=self.settings.openai_model,
                        max_tokens=self.settings.openai_max_tokens,
                        messages=current_messages,
                        temperature=self.settings.openai_temperature,
                        tools=tools if tools else None,
                        tool_choice="auto" if tools else None
                    )
                except Exception as additional_error:
                    self.logger.error(
                        "工具结果后的API调用失败", 
                        request_id=request_id,
                        iteration=iteration,
                        error=str(additional_error)
                    )
                    response_parts.append(f"无法完成后续回答: {additional_error}")
                    break
            
            # 如果达到最大迭代次数仍未完成
            if iteration >= max_iterations:
                self.logger.warning(
                    "工具调用达到最大迭代次数",
                    request_id=request_id,
                    max_iterations=max_iterations
                )
                response_parts.append("工具调用次数过多，未能完成所有处理。")
            
            # 合并所有响应文本
            result["response"] = "\n".join(response_parts)
            result["final_answer"] = result["response"]
            
            self.logger.info(
                "OpenAI响应处理完成",
                request_id=request_id,
                iterations=iteration,
                tools_count=len(result["tool_calls"])
            )
            
            return result
            
        except Exception as e:
            self.logger.error("处理OpenAI响应失败", 
                            request_id=request_id, 
                            error=str(e))
            result["success"] = False
            result["error"] = str(e)
            return result
    
    async def test_api_connection(self) -> Dict[str, Any]:
        """
        测试OpenAI API连接
        
        Returns:
            测试结果
        """
        test_result = {
            "success": False,
            "error": None,
            "model": self.settings.openai_model,
            "api_key_configured": bool(self.settings.openai_api_key),
            "base_url": self.settings.openai_base_url
        }
        
        try:
            self.logger.info("开始测试OpenAI API连接")
            
            # 简单的测试消息
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant."
                },
                {
                    "role": "user",
                    "content": "Hello, can you respond with 'API connection successful'?"
                }
            ]
            
            response = await self.openai.chat.completions.create(
                model=self.settings.openai_model,
                max_tokens=50,
                messages=messages,
                temperature=0.1
            )
            
            if response and response.choices:
                test_result["success"] = True
                test_result["response"] = response.choices[0].message.content
                self.logger.info("OpenAI API连接测试成功")
            else:
                test_result["error"] = "收到空响应"
                
        except Exception as e:
            test_result["error"] = str(e)
            self.logger.error("OpenAI API连接测试失败", error=str(e))
        
        return test_result 
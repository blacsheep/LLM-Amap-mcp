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
from .base_llm_handler import BaseLLMHandler


class ClaudeHandler(BaseLLMHandler):
    """Claude API处理器"""
    
    def __init__(self, amap_client: AmapMCPClient):
        super().__init__(amap_client)
        
        # 设置代理环境变量（如果启用）
        self._setup_proxies()
        
        # 确定是否启用token高效工具调用
        enable_token_efficient = (
            self.settings.claude_model in ["claude-3-7-sonnet-20250219", "claude-3-sonnet-20240229"] and
            self.settings.enable_token_efficient_tools
        )
        
        # 初始化Claude客户端
        headers = {}
        if enable_token_efficient:
            headers["anthropic-beta"] = "token-efficient-tools-2025-02-19"
            self.logger.info("已启用Claude token高效工具调用")
        
        self.anthropic = AsyncAnthropic(
            api_key=self.settings.anthropic_api_key,
            # 添加额外的配置参数
            timeout=60.0,  # 设置超时时间
            max_retries=2,   # 设置最大重试次数
            # 添加代理配置（如果启用）
            http_client=self._get_http_client() if self.settings.proxy_enabled else None,
            # 添加beta头（如果启用token高效工具调用）
            default_headers=headers if headers else None
        )
    
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
                
                has_tool_use = False
                assistant_content = []
                
                # 处理当前响应内容
                for content in current_response.content:
                    if content.type == 'text':
                        response_parts.append(content.text)
                        assistant_content.append(content)
                    elif content.type == 'tool_use':
                        has_tool_use = True
                        assistant_content.append(content)
                        
                        # 执行工具调用
                        tool_result = await self._execute_tool_call(
                            content.name, content.input, request_id
                        )
                        tool_result = self._prepare_tool_result_for_claude(tool_result)
                        result["tool_calls"].append(tool_result)
                        
                        # 添加assistant消息（带有工具调用）到消息历史
                        current_messages.append({
                            "role": "assistant",
                            "content": assistant_content
                        })
                        
                        # 准备工具结果内容
                        tool_result_content = tool_result["result"]
                        if tool_result_content is not None and not isinstance(tool_result_content, str):
                            try:
                                tool_result_content = json.dumps(tool_result_content, ensure_ascii=False)
                            except Exception as e:
                                self.logger.warning(
                                    "无法将工具结果转换为JSON字符串",
                                    request_id=request_id,
                                    error=str(e)
                                )
                                # 如果无法转换为JSON，则强制转换为字符串
                                tool_result_content = str(tool_result_content)
                        
                        # 添加用户消息（带有工具结果）到消息历史
                        current_messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": content.id,
                                    "content": tool_result_content
                                }
                            ]
                        })
                
                # 如果没有工具调用，则结束循环
                if not has_tool_use:
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
                    
                    current_response = await self.anthropic.messages.create(
                        model=self.settings.claude_model,
                        max_tokens=self.settings.claude_max_tokens,
                        messages=current_messages,
                        tools=tools if tools else None,
                        system=self._build_system_prompt(),
                        temperature=0.7,
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
                "Claude响应处理完成",
                request_id=request_id,
                iterations=iteration,
                tools_count=len(result["tool_calls"])
            )
            
            return result
            
        except Exception as e:
            self.logger.error("处理Claude响应失败", 
                            request_id=request_id,
                            error=str(e))
            raise ToolCallError(f"处理响应失败: {e}")
    
    async def _execute_tool_call(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any], 
        request_id: str
    ) -> Dict[str, Any]:
        """执行工具调用（根据Claude的格式）"""
        return await super()._execute_tool_call(tool_name, arguments, request_id)
    
    def _prepare_tool_result_for_claude(self, tool_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        准备工具调用结果，使其符合Claude API的要求
        
        Args:
            tool_result: 工具调用结果
            
        Returns:
            符合Claude API要求的工具调用结果
        """
        # 获取结果
        result = tool_result.get("result")
        
        # 确保结果为字符串或内容块列表
        if result is not None and not isinstance(result, str):
            try:
                # 将对象转换为JSON字符串
                result = json.dumps(result, ensure_ascii=False)
                tool_result["result"] = result
            except Exception as e:
                self.logger.warning("无法将工具调用结果转换为JSON字符串", error=str(e))
        
        return tool_result

    async def _process_claude_response(
        self,
        response_content: List[Any],
        query: str,
        request_id: str
    ) -> Dict[str, Any]:
        """处理Claude响应和工具调用"""
        result = {
            "success": True,
            "final_answer": "",
            "tool_calls": [],
            "error": None
        }
        
        # 先收集所有文本
        text_parts = []
        
        for content_item in response_content:
            if content_item.type == "text":
                text_parts.append(content_item.text)
            elif content_item.type == "tool_use":
                # 执行工具调用
                tool_result = await self._execute_tool_call(
                    content_item.name,
                    content_item.input,
                    request_id
                )
                
                # 准备工具调用结果，使其符合Claude API的要求
                tool_result = self._prepare_tool_result_for_claude(tool_result)
                
                result["tool_calls"].append(tool_result)
                
                # 添加工具调用到消息历史
                await self._add_tool_use_to_message_history(
                    request_id,
                    content_item.id,
                    content_item.name,
                    content_item.input,
                    tool_result
                )
        
        # 合并文本
        result["final_answer"] = "\n".join(text_parts)
        
        # 检查是否有工具调用还没有结果
        for content_item in response_content:
            if (content_item.type == "tool_use" and 
                not any(tc["tool_name"] == content_item.name for tc in result["tool_calls"])):
                
                # 再次处理工具调用（递归方式）
                self.logger.warning(f"发现未处理的工具调用: {content_item.name}")
                tool_result = await self._execute_tool_call(
                    content_item.name,
                    content_item.input,
                    request_id
                )
                
                # 准备工具调用结果，使其符合Claude API的要求
                tool_result = self._prepare_tool_result_for_claude(tool_result)
                
                result["tool_calls"].append(tool_result)
                
                # 添加工具调用到消息历史
                await self._add_tool_use_to_message_history(
                    request_id,
                    content_item.id,
                    content_item.name,
                    content_item.input,
                    tool_result
                )
        
        return result
    
    async def test_api_connection(self) -> Dict[str, Any]:
        """
        测试Claude API连接
        
        Returns:
            测试结果
        """
        request_id = generate_request_id()
        result = {
            "success": False,
            "model": self.settings.claude_model,
            "message": "",
            "error": None
        }
        
        try:
            self.logger.info("测试Claude API连接", request_id=request_id)
            
            # 构建简单的测试消息
            messages = [{"role": "user", "content": "Hello, Claude!"}]
            
            # 调用Claude API
            response = await self.anthropic.messages.create(
                model=self.settings.claude_model,
                max_tokens=10,  # 限制token数量，加快响应速度
                messages=messages,
                system="You are a helpful assistant.",
            )
            
            result["success"] = True
            result["message"] = "Claude API连接正常"
            self.logger.info("Claude API连接测试成功", request_id=request_id)
            
        except Exception as e:
            self.logger.error("Claude API连接测试失败", 
                            request_id=request_id,
                            error=str(e))
            result["error"] = str(e)
            result["message"] = f"Claude API连接失败: {e}"
        
        return result
        
    async def _add_tool_use_to_message_history(
        self,
        request_id: str,
        tool_use_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_result: Dict[str, Any]
    ) -> None:
        """
        添加工具调用到消息历史
        
        Args:
            request_id: 请求ID
            tool_use_id: 工具使用ID
            tool_name: 工具名称
            tool_input: 工具输入参数
            tool_result: 工具调用结果
        """
        try:
            # 首先，确保工具结果是字符串格式
            result_content = tool_result.get("result")
            
            if result_content is not None and not isinstance(result_content, str):
                try:
                    # 将结果转换为JSON字符串
                    result_content = json.dumps(result_content, ensure_ascii=False)
                except Exception as e:
                    self.logger.warning(
                        "无法将工具结果转换为JSON字符串",
                        request_id=request_id,
                        tool_name=tool_name,
                        error=str(e)
                    )
                    # 如果无法转换为JSON，则强制转换为字符串
                    result_content = str(result_content)
            
            # 记录日志
            self.logger.debug(
                "添加工具调用到消息历史",
                request_id=request_id,
                tool_name=tool_name,
                tool_use_id=tool_use_id
            )
            
            # 返回，实际的消息历史添加已在_process_claude_response方法中完成
            return
            
        except Exception as e:
            self.logger.error(
                "添加工具调用到消息历史失败",
                request_id=request_id,
                tool_name=tool_name,
                error=str(e)
            )
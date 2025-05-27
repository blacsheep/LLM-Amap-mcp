"""
LLM处理器抽象基类
定义统一的LLM处理器接口，支持多种LLM提供商
"""

import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from ..core.config import get_settings
from ..core.logger import get_logger
from ..core.prompt_manager import get_system_prompt
from .amap_client import AmapMCPClient


class BaseLLMHandler(ABC):
    """LLM处理器抽象基类"""
    
    def __init__(self, amap_client: AmapMCPClient):
        self.settings = get_settings()
        self.logger = get_logger(self.__class__.__name__.lower())
        self.amap_client = amap_client
        
        # 工具缓存
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def test_api_connection(self) -> Dict[str, Any]:
        """
        测试LLM API连接
        
        Returns:
            测试结果
        """
        pass
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        return await self._prepare_tools()
    
    def clear_tools_cache(self) -> None:
        """清除工具缓存"""
        self._tools_cache = None
        self.logger.info("工具缓存已清除")
    
    async def _prepare_tools(self) -> List[Dict[str, Any]]:
        """准备工具列表（通用实现）"""
        if self._tools_cache is None:
            try:
                # 获取MCP工具列表
                mcp_tools = await self.amap_client.list_available_tools()
                
                # 转换为标准工具格式
                self._tools_cache = [
                    {
                        "name": tool["name"],
                        "description": tool["description"],
                        "input_schema": tool["input_schema"]
                    }
                    for tool in mcp_tools
                ]
                
                self.logger.info("工具列表准备完成", tools_count=len(self._tools_cache))
                
            except Exception as e:
                self.logger.error("准备工具列表失败", error=str(e))
                self._tools_cache = []
        
        return self._tools_cache
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词（通用实现）"""
        return get_system_prompt()
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """格式化上下文信息（通用实现）"""
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
    
    async def _execute_tool_call(
        self, 
        tool_name: str,
        tool_arguments: Dict[str, Any], 
        request_id: str
    ) -> Dict[str, Any]:
        """执行工具调用（通用实现）"""
        tool_result = {
            "tool_name": tool_name,
            "arguments": tool_arguments,
            "success": False,
            "result": None,
            "error": None
        }
        
        try:
            self.logger.info("执行工具调用", 
                           request_id=request_id,
                           tool_name=tool_name,
                           arguments=tool_arguments)
            
            # 调用MCP工具
            result = await self.amap_client.call_tool(
                tool_name, 
                tool_arguments
            )
            
            # 对结果进行更严格的处理
            # 1. 先尝试将结果转换为可序列化的格式
            serializable_result = self._make_serializable(result)
            
            # 2. 如果结果是列表且只包含一个字符串元素（通常是JSON字符串）
            if isinstance(serializable_result, list) and len(serializable_result) == 1 and isinstance(serializable_result[0], str):
                try:
                    # 尝试解析JSON字符串
                    parsed_json = json.loads(serializable_result[0])
                    serializable_result = parsed_json
                    self.logger.info("成功解析工具调用返回的JSON字符串", 
                                    request_id=request_id, 
                                    tool_name=tool_name)
                except json.JSONDecodeError as e:
                    self.logger.warning("无法解析工具调用返回的JSON字符串", 
                                      request_id=request_id, 
                                      tool_name=tool_name,
                                      error=str(e))
            
            tool_result["success"] = True
            tool_result["result"] = serializable_result
            
            self.logger.info("工具调用成功", 
                           request_id=request_id,
                           tool_name=tool_name)
            
        except Exception as e:
            self.logger.error("工具调用失败", 
                            request_id=request_id,
                            tool_name=tool_name,
                            error=str(e))
            tool_result["error"] = str(e)
            tool_result["result"] = f"工具调用失败: {e}"
        
        return tool_result
    
    def _make_serializable(self, obj: Any) -> Any:
        """将对象转换为可JSON序列化的格式"""
        if hasattr(obj, '__dict__'):
            # 如果是对象，尝试获取其属性
            if hasattr(obj, 'text'):
                # TextContent对象
                return obj.text
            elif hasattr(obj, 'content'):
                # 其他内容对象
                return obj.content
            else:
                # 通用对象，转换为字典
                return {k: self._make_serializable(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, list):
            # 处理列表
            serialized_list = [self._make_serializable(item) for item in obj]
            
            # 如果列表中只有一个元素，并且是字符串，尝试解析JSON
            if len(serialized_list) == 1 and isinstance(serialized_list[0], str):
                try:
                    json_obj = json.loads(serialized_list[0])
                    return json_obj
                except json.JSONDecodeError:
                    # 解析失败，返回原列表
                    pass
            
            return serialized_list
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, str):
            # 尝试解析可能的JSON字符串
            try:
                if obj.strip().startswith('{') or obj.strip().startswith('['):
                    return json.loads(obj)
                return obj
            except json.JSONDecodeError:
                return obj
        else:
            # 基本类型或已经可序列化的对象
            return obj 
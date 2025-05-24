"""
API数据模型定义
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime


class AddressQuery(BaseModel):
    """地址查询请求模型"""
    
    address: str = Field(..., description="待解析的地址或查询内容", min_length=1, max_length=500)
    context: Optional[Dict[str, Any]] = Field(None, description="额外的上下文信息")
    system_prompt: Optional[str] = Field(None, description="自定义系统提示词", max_length=2000)
    
    @validator("address")
    def validate_address(cls, v):
        """验证地址字段"""
        if not v or not v.strip():
            raise ValueError("地址不能为空")
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "address": "北京市朝阳区三里屯太古里",
                "context": {
                    "city": "北京",
                    "preferences": "详细地址信息"
                },
                "system_prompt": "请提供详细的地址解析结果"
            }
        }


class ToolCall(BaseModel):
    """工具调用信息模型"""
    
    tool_name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(..., description="工具参数")
    success: bool = Field(..., description="调用是否成功")
    result: Optional[Any] = Field(None, description="调用结果")
    error: Optional[str] = Field(None, description="错误信息")
    
    class Config:
        schema_extra = {
            "example": {
                "tool_name": "geocode",
                "arguments": {"address": "北京市朝阳区三里屯"},
                "success": True,
                "result": {"location": "116.397428,39.90923"},
                "error": None
            }
        }


class AddressResponse(BaseModel):
    """地址解析响应模型"""
    
    success: bool = Field(..., description="请求是否成功")
    request_id: str = Field(..., description="请求唯一标识")
    data: Optional[Dict[str, Any]] = Field(None, description="解析结果数据")
    response: str = Field("", description="Claude的文本响应")
    tool_calls: List[ToolCall] = Field(default_factory=list, description="工具调用详情")
    error: Optional[str] = Field(None, description="错误信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")
    processing_time: Optional[float] = Field(None, description="处理时间（秒）")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "request_id": "1642123456789_abc12345",
                "data": {
                    "formatted_address": "北京市朝阳区三里屯太古里",
                    "location": "116.397428,39.90923",
                    "province": "北京市",
                    "city": "北京市",
                    "district": "朝阳区"
                },
                "response": "根据您提供的地址，我已经成功解析出详细信息...",
                "tool_calls": [
                    {
                        "tool_name": "geocode",
                        "arguments": {"address": "北京市朝阳区三里屯太古里"},
                        "success": True,
                        "result": {"location": "116.397428,39.90923"},
                        "error": None
                    }
                ],
                "error": None,
                "timestamp": "2024-01-13T10:30:00",
                "processing_time": 2.5
            }
        }


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    
    status: str = Field(..., description="服务状态")
    timestamp: datetime = Field(default_factory=datetime.now, description="检查时间")
    version: str = Field("0.1.0", description="服务版本")
    mcp_connected: bool = Field(..., description="MCP连接状态")
    claude_available: bool = Field(..., description="Claude API可用性")
    tools_count: int = Field(0, description="可用工具数量")
    uptime: Optional[float] = Field(None, description="运行时间（秒）")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-13T10:30:00",
                "version": "0.1.0",
                "mcp_connected": True,
                "claude_available": True,
                "tools_count": 5,
                "uptime": 3600.0
            }
        }


class ToolInfo(BaseModel):
    """工具信息模型"""
    
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    input_schema: Dict[str, Any] = Field(..., description="输入参数模式")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "geocode",
                "description": "地理编码，将地址转换为坐标",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "待编码的地址"
                        }
                    },
                    "required": ["address"]
                }
            }
        }


class ToolsResponse(BaseModel):
    """工具列表响应模型"""
    
    success: bool = Field(..., description="请求是否成功")
    tools: List[ToolInfo] = Field(..., description="可用工具列表")
    count: int = Field(..., description="工具数量")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "tools": [
                    {
                        "name": "geocode",
                        "description": "地理编码，将地址转换为坐标",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "address": {"type": "string"}
                            }
                        }
                    }
                ],
                "count": 1,
                "timestamp": "2024-01-13T10:30:00"
            }
        }


class ErrorResponse(BaseModel):
    """错误响应模型"""
    
    success: bool = Field(False, description="请求是否成功")
    error_code: str = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误信息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
    request_id: Optional[str] = Field(None, description="请求ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="错误时间戳")
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error_message": "地址参数不能为空",
                "details": {
                    "field": "address",
                    "value": ""
                },
                "request_id": "1642123456789_abc12345",
                "timestamp": "2024-01-13T10:30:00"
            }
        }
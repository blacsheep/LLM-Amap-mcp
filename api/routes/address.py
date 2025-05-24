"""
地址解析API路由
"""

import time
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse

from ..schemas.models import (
    AddressQuery, 
    AddressResponse, 
    HealthResponse, 
    ToolsResponse,
    ErrorResponse
)
from ...src.mcp_client import AmapMCPClient, ClaudeHandler
from ...src.core.logger import get_logger
from ...src.core.exceptions import (
    MCPConnectionError,
    ClaudeAPIError,
    ValidationError,
    TimeoutError
)
from ...src.utils.helpers import generate_request_id


# 创建路由器
router = APIRouter(prefix="/api/v1", tags=["地址解析"])

# 全局变量存储客户端实例
_amap_client: AmapMCPClient = None
_claude_handler: ClaudeHandler = None
_service_start_time = time.time()

# 日志记录器
logger = get_logger("api_routes")


async def get_amap_client() -> AmapMCPClient:
    """获取高德MCP客户端实例"""
    global _amap_client
    
    if _amap_client is None:
        _amap_client = AmapMCPClient()
        await _amap_client.connect()
        logger.info("高德MCP客户端已初始化")
    
    # 检查连接健康状态
    if not await _amap_client.health_check():
        logger.warning("MCP连接不健康，尝试重连")
        await _amap_client.disconnect()
        await _amap_client.connect()
    
    return _amap_client


async def get_claude_handler() -> ClaudeHandler:
    """获取Claude处理器实例"""
    global _claude_handler
    
    if _claude_handler is None:
        amap_client = await get_amap_client()
        _claude_handler = ClaudeHandler(amap_client)
        logger.info("Claude处理器已初始化")
    
    return _claude_handler


@router.post(
    "/address/parse",
    response_model=AddressResponse,
    summary="地址解析",
    description="使用Claude AI和高德地图API解析地址信息"
)
async def parse_address(
    query: AddressQuery,
    claude_handler: ClaudeHandler = Depends(get_claude_handler)
) -> AddressResponse:
    """
    地址解析接口
    
    Args:
        query: 地址查询请求
        claude_handler: Claude处理器实例
        
    Returns:
        地址解析结果
    """
    request_id = generate_request_id()
    start_time = time.time()
    
    try:
        logger.info("收到地址解析请求", 
                   request_id=request_id,
                   address=query.address)
        
        # 处理查询
        result = await claude_handler.process_query(
            query=query.address,
            context=query.context,
            system_prompt=query.system_prompt
        )
        
        # 计算处理时间
        processing_time = time.time() - start_time
        
        # 构建响应
        response = AddressResponse(
            success=result["success"],
            request_id=request_id,
            data=result.get("data"),
            response=result.get("final_answer", ""),
            tool_calls=result.get("tool_calls", []),
            error=result.get("error"),
            processing_time=processing_time
        )
        
        logger.info("地址解析完成", 
                   request_id=request_id,
                   success=result["success"],
                   processing_time=processing_time)
        
        return response
        
    except ValidationError as e:
        logger.warning("请求验证失败", request_id=request_id, error=str(e))
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "VALIDATION_ERROR",
                "error_message": str(e),
                "request_id": request_id
            }
        )
    
    except (MCPConnectionError, ClaudeAPIError) as e:
        logger.error("服务错误", request_id=request_id, error=str(e))
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "SERVICE_ERROR",
                "error_message": "服务暂时不可用，请稍后重试",
                "request_id": request_id
            }
        )
    
    except TimeoutError as e:
        logger.error("请求超时", request_id=request_id, error=str(e))
        raise HTTPException(
            status_code=408,
            detail={
                "error_code": "TIMEOUT_ERROR",
                "error_message": "请求处理超时",
                "request_id": request_id
            }
        )
    
    except Exception as e:
        logger.error("未知错误", request_id=request_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_message": "内部服务器错误",
                "request_id": request_id
            }
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="检查服务健康状态"
)
async def health_check() -> HealthResponse:
    """
    健康检查接口
    
    Returns:
        服务健康状态
    """
    try:
        # 检查MCP连接
        mcp_connected = False
        tools_count = 0
        
        try:
            amap_client = await get_amap_client()
            mcp_connected = await amap_client.health_check()
            if mcp_connected:
                tools = await amap_client.list_available_tools()
                tools_count = len(tools)
        except Exception as e:
            logger.warning("MCP健康检查失败", error=str(e))
        
        # 检查Claude API
        claude_available = False
        try:
            claude_handler = await get_claude_handler()
            # 简单测试Claude可用性
            claude_available = True
        except Exception as e:
            logger.warning("Claude健康检查失败", error=str(e))
        
        # 计算运行时间
        uptime = time.time() - _service_start_time
        
        # 确定整体状态
        status = "healthy" if (mcp_connected and claude_available) else "unhealthy"
        
        return HealthResponse(
            status=status,
            mcp_connected=mcp_connected,
            claude_available=claude_available,
            tools_count=tools_count,
            uptime=uptime
        )
        
    except Exception as e:
        logger.error("健康检查失败", error=str(e))
        return HealthResponse(
            status="error",
            mcp_connected=False,
            claude_available=False,
            tools_count=0
        )


@router.get(
    "/tools",
    response_model=ToolsResponse,
    summary="获取可用工具",
    description="获取高德地图MCP服务器提供的可用工具列表"
)
async def get_tools(
    amap_client: AmapMCPClient = Depends(get_amap_client)
) -> ToolsResponse:
    """
    获取可用工具列表
    
    Args:
        amap_client: 高德MCP客户端实例
        
    Returns:
        工具列表
    """
    try:
        logger.info("获取工具列表请求")
        
        # 获取工具列表
        tools = await amap_client.list_available_tools()
        
        logger.info("工具列表获取成功", tools_count=len(tools))
        
        return ToolsResponse(
            success=True,
            tools=tools,
            count=len(tools)
        )
        
    except MCPConnectionError as e:
        logger.error("MCP连接错误", error=str(e))
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "MCP_CONNECTION_ERROR",
                "error_message": "无法连接到高德地图服务"
            }
        )
    
    except Exception as e:
        logger.error("获取工具列表失败", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_message": "获取工具列表失败"
            }
        )


@router.post(
    "/address/batch",
    summary="批量地址解析",
    description="批量处理多个地址解析请求"
)
async def batch_parse_addresses(
    queries: list[AddressQuery],
    background_tasks: BackgroundTasks,
    claude_handler: ClaudeHandler = Depends(get_claude_handler)
) -> Dict[str, Any]:
    """
    批量地址解析接口
    
    Args:
        queries: 地址查询请求列表
        background_tasks: 后台任务
        claude_handler: Claude处理器实例
        
    Returns:
        批量处理结果
    """
    if len(queries) > 10:  # 限制批量大小
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "BATCH_SIZE_LIMIT",
                "error_message": "批量请求数量不能超过10个"
            }
        )
    
    batch_id = generate_request_id()
    logger.info("收到批量地址解析请求", 
               batch_id=batch_id,
               count=len(queries))
    
    results = []
    
    for i, query in enumerate(queries):
        try:
            result = await claude_handler.process_query(
                query=query.address,
                context=query.context,
                system_prompt=query.system_prompt
            )
            
            results.append({
                "index": i,
                "success": result["success"],
                "data": result.get("data"),
                "response": result.get("final_answer", ""),
                "error": result.get("error")
            })
            
        except Exception as e:
            logger.error("批量处理项失败", 
                        batch_id=batch_id,
                        index=i,
                        error=str(e))
            results.append({
                "index": i,
                "success": False,
                "data": None,
                "response": "",
                "error": str(e)
            })
    
    return {
        "batch_id": batch_id,
        "total": len(queries),
        "results": results,
        "success_count": sum(1 for r in results if r["success"]),
        "error_count": sum(1 for r in results if not r["success"])
    }


# 应用启动时的初始化
async def startup_event():
    """应用启动事件"""
    global _service_start_time
    _service_start_time = time.time()
    logger.info("地址解析API服务启动")


# 应用关闭时的清理
async def shutdown_event():
    """应用关闭事件"""
    global _amap_client, _claude_handler
    
    if _amap_client:
        await _amap_client.disconnect()
        _amap_client = None
    
    _claude_handler = None
    logger.info("地址解析API服务关闭")
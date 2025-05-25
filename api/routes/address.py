"""
地址解析API路由
"""

import time
import asyncio
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse

from src.core.config import get_settings
from src.core.logger import setup_logger
from src.core.exceptions import AddressParserBaseException
from src.mcp_client import AmapMCPClient, create_llm_handler, get_current_provider
from ..schemas.models import (
    AddressQuery,
    AddressResponse,
    HealthResponse,
    ToolsResponse
)


# 创建路由器
router = APIRouter(prefix="/api/v1", tags=["地址解析"])

# 全局变量存储客户端实例
_amap_client: AmapMCPClient = None
_llm_handler = None
_service_start_time = time.time()

# 日志记录器
logger = setup_logger("api_routes")


def generate_request_id() -> str:
    """生成请求ID"""
    import time
    import random
    import string
    
    timestamp = str(int(time.time() * 1000))
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{timestamp}_{random_str}"


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


async def get_llm_handler():
    """获取LLM处理器实例"""
    global _llm_handler
    
    if _llm_handler is None:
        amap_client = await get_amap_client()
        _llm_handler = create_llm_handler(amap_client)
        current_provider = get_current_provider()
        logger.info("LLM处理器已初始化", provider=current_provider)
    
    return _llm_handler


@router.post(
    "/address/parse",
    response_model=AddressResponse,
    summary="地址解析",
    description="使用AI和高德地图API解析地址信息"
)
async def parse_address(
    query: AddressQuery,
    llm_handler = Depends(get_llm_handler)
) -> AddressResponse:
    """
    地址解析接口
    
    Args:
        query: 地址查询请求
        llm_handler: LLM处理器实例
        
    Returns:
        地址解析结果
    """
    request_id = generate_request_id()
    start_time = time.time()
    
    try:
        logger.info("收到地址解析请求", 
                   request_id=request_id,
                   address=query.address,
                   provider=get_current_provider())
        
        # 处理查询
        result = await llm_handler.process_query(
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
                   processing_time=processing_time,
                   provider=get_current_provider())
        
        return response
        
    except AddressParserBaseException as e:
        logger.warning("业务异常", request_id=request_id, error=str(e))
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": e.error_code,
                "error_message": e.message,
                "request_id": request_id
            }
        )
    
    except Exception as e:
        # 检查是否是连接相关错误
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['connection', 'timeout', 'network']):
            logger.error("连接错误", request_id=request_id, error=str(e))
            raise HTTPException(
                status_code=503,
                detail={
                    "error_code": "SERVICE_ERROR",
                    "error_message": "服务暂时不可用，请稍后重试",
                    "request_id": request_id
                }
            )
        elif 'timeout' in error_str:
            logger.error("请求超时", request_id=request_id, error=str(e))
            raise HTTPException(
                status_code=408,
                detail={
                    "error_code": "TIMEOUT_ERROR",
                    "error_message": "请求处理超时",
                    "request_id": request_id
                }
            )
        else:
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
            # 只有在全局客户端已初始化时才检查MCP
            global _amap_client
            if _amap_client is not None:
                mcp_connected = await _amap_client.health_check()
                if mcp_connected:
                    tools = await _amap_client.list_available_tools()
                    tools_count = len(tools)
            else:
                # 如果客户端未初始化，尝试快速测试连接
                test_client = AmapMCPClient()
                await test_client.connect()
                mcp_connected = await test_client.health_check()
                if mcp_connected:
                    tools = await test_client.list_available_tools()
                    tools_count = len(tools)
                await test_client.disconnect()
        except Exception as e:
            logger.warning("MCP健康检查失败", error=str(e))
        
        # 检查LLM API
        llm_available = False
        current_provider = get_current_provider()
        try:
            # 只有在全局处理器已初始化时才检查LLM
            global _llm_handler
            if _llm_handler is not None:
                llm_available = True
            else:
                # 简单检查配置是否正确
                settings = get_settings()
                if current_provider == "claude" and settings.anthropic_api_key:
                    llm_available = True
                elif current_provider == "openai" and settings.openai_api_key:
                    llm_available = True
        except Exception as e:
            logger.warning("LLM健康检查失败", provider=current_provider, error=str(e))
        
        # 计算运行时间
        uptime = time.time() - _service_start_time
        
        # 确定整体状态
        status = "healthy" if (mcp_connected and llm_available) else "partial"
        if not mcp_connected and not llm_available:
            status = "unhealthy"
        
        return HealthResponse(
            status=status,
            mcp_connected=mcp_connected,
            claude_available=llm_available,  # 保持向后兼容的字段名
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
    description="获取当前可用的MCP工具列表"
)
async def get_tools() -> ToolsResponse:
    """
    获取可用工具接口
    
    Returns:
        工具列表
    """
    try:
        llm_handler = await get_llm_handler()
        tools = await llm_handler.get_available_tools()
        
        return ToolsResponse(
            success=True,
            tools=tools,
            count=len(tools)
        )
        
    except Exception as e:
        logger.error("获取工具列表失败", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_message": "获取工具列表失败",
                "error": str(e)
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
    llm_handler = Depends(get_llm_handler)
) -> Dict[str, Any]:
    """
    批量地址解析接口
    
    Args:
        queries: 地址查询请求列表
        background_tasks: 后台任务
        llm_handler: LLM处理器实例
        
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
    
    try:
        logger.info("收到批量地址解析请求", 
                   batch_id=batch_id,
                   count=len(queries),
                   provider=get_current_provider())
        
        results = []
        
        for i, query in enumerate(queries):
            try:
                result = await llm_handler.process_query(
                    query=query.address,
                    context=query.context,
                    system_prompt=query.system_prompt
                )
                
                results.append({
                    "index": i,
                    "address": query.address,
                    "success": result["success"],
                    "data": result.get("data"),
                    "response": result.get("final_answer", ""),
                    "error": result.get("error")
                })
                
            except Exception as e:
                logger.error("批量处理中单个请求失败", 
                           batch_id=batch_id,
                           index=i,
                           address=query.address,
                           error=str(e))
                
                results.append({
                    "index": i,
                    "address": query.address,
                    "success": False,
                    "data": None,
                    "response": "",
                    "error": str(e)
                })
        
        # 统计结果
        success_count = sum(1 for r in results if r["success"])
        
        logger.info("批量地址解析完成", 
                   batch_id=batch_id,
                   total=len(queries),
                   success=success_count,
                   failed=len(queries) - success_count,
                   provider=get_current_provider())
        
        return {
            "batch_id": batch_id,
            "total": len(queries),
            "success_count": success_count,
            "failed_count": len(queries) - success_count,
            "results": results
        }
        
    except Exception as e:
        logger.error("批量地址解析失败", batch_id=batch_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "BATCH_PROCESSING_ERROR",
                "error_message": "批量处理失败",
                "batch_id": batch_id,
                "error": str(e)
            }
        )


# 应用启动时的初始化
async def startup_event():
    """应用启动事件"""
    global _service_start_time
    _service_start_time = time.time()
    current_provider = get_current_provider()
    logger.info("地址解析API服务启动", provider=current_provider)


# 应用关闭时的清理
async def shutdown_event():
    """应用关闭事件"""
    global _amap_client, _llm_handler
    
    if _amap_client:
        await _amap_client.disconnect()
        _amap_client = None
    
    _llm_handler = None
    logger.info("地址解析API服务关闭")
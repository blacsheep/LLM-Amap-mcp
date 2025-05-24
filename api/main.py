"""
FastAPI主应用
地址解析服务的API入口
"""

import sys
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_settings
from src.core.logger import setup_logger
from src.core.exceptions import AddressParserBaseException
from .routes.address import router as address_router, startup_event, shutdown_event


# 应用生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    await startup_event()
    yield
    # 关闭时执行
    await shutdown_event()


# 创建FastAPI应用
def create_app() -> FastAPI:
    """创建并配置FastAPI应用"""
    
    settings = get_settings()
    logger = setup_logger("fastapi_app")
    
    # 创建应用实例
    app = FastAPI(
        title="高德地址解析服务",
        description="基于Claude AI和高德地图MCP的智能地址解析服务",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 配置受信任主机中间件
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # 生产环境应该限制具体主机
    )
    
    # 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """记录请求日志"""
        start_time = time.time()
        
        # 记录请求开始
        logger.info("收到HTTP请求",
                   method=request.method,
                   url=str(request.url),
                   client_ip=request.client.host if request.client else "unknown")
        
        # 处理请求
        try:
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录响应
            logger.info("HTTP请求完成",
                       method=request.method,
                       url=str(request.url),
                       status_code=response.status_code,
                       process_time=process_time)
            
            # 添加处理时间到响应头
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # 记录异常
            process_time = time.time() - start_time
            logger.error("HTTP请求处理异常",
                        method=request.method,
                        url=str(request.url),
                        error=str(e),
                        process_time=process_time)
            raise
    
    # 注册路由
    app.include_router(address_router)
    
    # 根路径
    @app.get("/", summary="服务信息", tags=["基础"])
    async def root():
        """服务根路径"""
        return {
            "service": "高德地址解析服务",
            "version": "0.1.0",
            "description": "基于Claude AI和高德地图MCP的智能地址解析服务",
            "docs": "/docs",
            "health": "/api/v1/health",
            "tools": "/api/v1/tools"
        }
    
    # 全局异常处理器
    @app.exception_handler(AddressParserBaseException)
    async def address_parser_exception_handler(request: Request, exc: AddressParserBaseException):
        """处理自定义异常"""
        logger.error("业务异常",
                    url=str(request.url),
                    error_code=exc.error_code,
                    error_message=exc.message,
                    details=exc.details)
        
        return JSONResponse(
            status_code=400,
            content=exc.to_dict()
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证异常"""
        logger.warning("请求验证失败",
                      url=str(request.url),
                      errors=exc.errors())
        
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "VALIDATION_ERROR",
                "error_message": "请求参数验证失败",
                "details": exc.errors()
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理HTTP异常"""
        logger.warning("HTTP异常",
                      url=str(request.url),
                      status_code=exc.status_code,
                      detail=exc.detail)
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": f"HTTP_{exc.status_code}",
                "error_message": exc.detail
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理通用异常"""
        logger.error("未处理异常",
                    url=str(request.url),
                    error_type=type(exc).__name__,
                    error_message=str(exc))
        
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "error_message": "内部服务器错误"
            }
        )
    
    logger.info("FastAPI应用创建完成")
    return app


# 创建应用实例
app = create_app()


# 开发服务器启动函数
def start_dev_server():
    """启动开发服务器"""
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
        log_level="info"
    )


if __name__ == "__main__":
    start_dev_server()
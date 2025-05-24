"""
日志配置模块
使用structlog进行结构化日志记录
"""

import sys
import logging
import structlog
from typing import Optional
from pathlib import Path

from .config import get_settings


def setup_logger(
    name: Optional[str] = None,
    level: Optional[str] = None,
    log_file: Optional[str] = None
) -> structlog.stdlib.BoundLogger:
    """
    配置并返回结构化日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径
        
    Returns:
        配置好的结构化日志记录器
    """
    settings = get_settings()
    
    # 使用配置中的默认值
    level = level or settings.log_level
    log_file = log_file or settings.log_file
    
    # 确保日志目录存在
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 配置structlog
    structlog.configure(
        processors=[
            # 添加时间戳
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            # 处理异常堆栈
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # JSON格式输出
            structlog.processors.JSONRenderer(ensure_ascii=False)
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # 配置标准库日志记录器
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level),
        handlers=_get_handlers(log_file, level)
    )
    
    # 创建日志记录器
    logger = structlog.get_logger(name or "address_parser")
    
    return logger


def _get_handlers(log_file: Optional[str], level: str) -> list:
    """获取日志处理器列表"""
    handlers = []
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))
    handlers.append(console_handler)
    
    # 文件处理器
    if log_file:
        try:
            file_handler = logging.FileHandler(
                log_file, 
                encoding="utf-8",
                mode="a"
            )
            file_handler.setLevel(getattr(logging, level))
            handlers.append(file_handler)
        except Exception as e:
            # 如果无法创建文件处理器，只使用控制台输出
            print(f"警告：无法创建文件日志处理器 {log_file}: {e}")
    
    return handlers


def get_logger(name: str = "address_parser") -> structlog.stdlib.BoundLogger:
    """
    获取已配置的日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        日志记录器实例
    """
    return structlog.get_logger(name)
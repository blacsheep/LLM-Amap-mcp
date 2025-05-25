"""
LLM处理器工厂类
根据配置创建相应的LLM处理器实例
"""

from typing import Type, Dict, Any
from ..core.config import get_settings
from ..core.logger import get_logger
from ..core.exceptions import ValidationError
from .amap_client import AmapMCPClient
from .base_llm_handler import BaseLLMHandler
from .claude_handler import ClaudeHandler
from .openai_handler import OpenAIHandler


class LLMHandlerFactory:
    """LLM处理器工厂类"""
    
    # 注册的处理器类型
    _handlers: Dict[str, Type[BaseLLMHandler]] = {
        "claude": ClaudeHandler,
        "openai": OpenAIHandler,
    }
    
    @classmethod
    def create_handler(cls, amap_client: AmapMCPClient) -> BaseLLMHandler:
        """
        根据配置创建LLM处理器实例
        
        Args:
            amap_client: 高德MCP客户端实例
            
        Returns:
            LLM处理器实例
            
        Raises:
            ValidationError: 当LLM提供商配置无效时
        """
        settings = get_settings()
        logger = get_logger("llm_factory")
        
        provider = settings.llm_provider.lower()
        
        if provider not in cls._handlers:
            available_providers = list(cls._handlers.keys())
            raise ValidationError(
                f"不支持的LLM提供商: {provider}。"
                f"支持的提供商: {available_providers}"
            )
        
        handler_class = cls._handlers[provider]
        
        try:
            # 验证必要的配置
            cls._validate_provider_config(provider, settings)
            
            # 创建处理器实例
            handler = handler_class(amap_client)
            
            logger.info(f"成功创建{provider.upper()}处理器", 
                       provider=provider,
                       handler_class=handler_class.__name__)
            
            return handler
            
        except Exception as e:
            logger.error(f"创建{provider.upper()}处理器失败", 
                        provider=provider,
                        error=str(e))
            raise ValidationError(f"创建{provider.upper()}处理器失败: {e}")
    
    @classmethod
    def _validate_provider_config(cls, provider: str, settings) -> None:
        """
        验证特定提供商的配置
        
        Args:
            provider: LLM提供商名称
            settings: 配置实例
            
        Raises:
            ValidationError: 当配置无效时
        """
        if provider == "claude":
            if not settings.anthropic_api_key:
                raise ValidationError("使用Claude时，ANTHROPIC_API_KEY是必需的")
        
        elif provider == "openai":
            if not settings.openai_api_key:
                raise ValidationError("使用OpenAI时，OPENAI_API_KEY是必需的")
            
            # 验证模型名称格式（可选）
            if not settings.openai_model:
                raise ValidationError("使用OpenAI时，OPENAI_MODEL是必需的")
    
    @classmethod
    def register_handler(cls, provider: str, handler_class: Type[BaseLLMHandler]) -> None:
        """
        注册新的LLM处理器类型
        
        Args:
            provider: 提供商名称
            handler_class: 处理器类
        """
        if not issubclass(handler_class, BaseLLMHandler):
            raise ValueError(f"处理器类必须继承自BaseLLMHandler")
        
        cls._handlers[provider.lower()] = handler_class
        
        logger = get_logger("llm_factory")
        logger.info(f"注册新的LLM处理器", 
                   provider=provider,
                   handler_class=handler_class.__name__)
    
    @classmethod
    def get_available_providers(cls) -> list[str]:
        """
        获取所有可用的LLM提供商列表
        
        Returns:
            提供商名称列表
        """
        return list(cls._handlers.keys())
    
    @classmethod
    async def test_provider_connection(cls, provider: str, amap_client: AmapMCPClient) -> Dict[str, Any]:
        """
        测试特定提供商的连接
        
        Args:
            provider: 提供商名称
            amap_client: 高德MCP客户端实例
            
        Returns:
            测试结果
        """
        logger = get_logger("llm_factory")
        
        try:
            # 临时创建处理器进行测试
            original_provider = get_settings().llm_provider
            
            # 临时修改配置（仅用于测试）
            settings = get_settings()
            settings.llm_provider = provider
            
            handler = cls.create_handler(amap_client)
            result = await handler.test_api_connection()
            
            # 恢复原始配置
            settings.llm_provider = original_provider
            
            logger.info(f"{provider.upper()}连接测试完成", 
                       provider=provider,
                       success=result.get("success", False))
            
            return result
            
        except Exception as e:
            logger.error(f"{provider.upper()}连接测试失败", 
                        provider=provider,
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "provider": provider
            }


# 便捷函数
def create_llm_handler(amap_client: AmapMCPClient) -> BaseLLMHandler:
    """
    便捷函数：创建LLM处理器
    
    Args:
        amap_client: 高德MCP客户端实例
        
    Returns:
        LLM处理器实例
    """
    return LLMHandlerFactory.create_handler(amap_client)


def get_current_provider() -> str:
    """
    便捷函数：获取当前配置的LLM提供商
    
    Returns:
        当前提供商名称
    """
    return get_settings().llm_provider 
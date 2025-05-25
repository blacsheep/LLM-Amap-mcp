"""
配置管理模块
使用pydantic-settings管理环境变量和应用配置
"""

import os
from typing import List, Optional, Literal
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_parse_none_str="None"
    )
    
    # LLM提供商选择
    llm_provider: Literal["claude", "openai"] = Field(default="claude", env="LLM_PROVIDER")
    
    # Claude API配置
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-3-7-sonnet-20250219", env="CLAUDE_MODEL")
    claude_max_tokens: int = Field(default=1000, env="CLAUDE_MAX_TOKENS")
    
    # OpenAI兼容API配置
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, env="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=1000, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.7, env="OPENAI_TEMPERATURE")
    
    # 代理配置
    proxy_enabled: bool = Field(default=False, env="PROXY_ENABLED")
    http_proxy: Optional[str] = Field(default=None, env="HTTP_PROXY")
    https_proxy: Optional[str] = Field(default=None, env="HTTPS_PROXY")
    all_proxy: Optional[str] = Field(default=None, env="ALL_PROXY")
    
    # 高德地图API配置
    amap_maps_api_key: str = Field(..., env="AMAP_MAPS_API_KEY")
    
    # MCP服务器配置
    mcp_server_timeout: int = Field(default=30, env="MCP_SERVER_TIMEOUT")
    mcp_retry_count: int = Field(default=3, env="MCP_RETRY_COUNT") 
    mcp_retry_delay: float = Field(default=1.0, env="MCP_RETRY_DELAY")
    
    # 高德MCP服务器配置
    amap_server_command: str = Field(default="npx", env="AMAP_SERVER_COMMAND")
    amap_server_args: str = Field(
        default="-y,@amap/amap-maps-mcp-server",
        env="AMAP_SERVER_ARGS"
    )
    
    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/app.log", env="LOG_FILE")
    
    # API服务配置
    api_host: str = Field(default="127.0.0.1", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_debug: bool = Field(default=True, env="API_DEBUG")
    
    def get_amap_server_args_list(self) -> List[str]:
        """获取解析后的amap_server_args列表"""
        return [arg.strip() for arg in self.amap_server_args.split(",")]
    
    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v):
        """验证LLM提供商配置"""
        if v not in ["claude", "openai"]:
            raise ValueError("LLM提供商必须是 'claude' 或 'openai'")
        return v.lower()
    
    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, v, info):
        """验证OpenAI API密钥（当使用OpenAI时必需）"""
        if info.data.get("llm_provider") == "openai" and not v:
            raise ValueError("使用OpenAI提供商时，OPENAI_API_KEY是必需的")
        return v
    
    @field_validator("anthropic_api_key")
    @classmethod
    def validate_anthropic_api_key(cls, v, info):
        """验证Anthropic API密钥（当使用Claude时必需）"""
        if info.data.get("llm_provider") == "claude" and not v:
            raise ValueError("使用Claude提供商时，ANTHROPIC_API_KEY是必需的")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"日志级别必须是 {valid_levels} 中的一个")
        return v.upper()
    
    @field_validator("log_file")
    @classmethod
    def validate_log_file(cls, v):
        """确保日志目录存在"""
        log_dir = os.path.dirname(v)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        return v


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings
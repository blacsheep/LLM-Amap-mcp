"""
自定义异常类定义
"""


class AddressParserBaseException(Exception):
    """地址解析服务基础异常类"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


class MCPConnectionError(AddressParserBaseException):
    """MCP连接相关异常"""
    pass


class AmapAPIError(AddressParserBaseException):
    """高德地图API相关异常"""
    pass


class ClaudeAPIError(AddressParserBaseException):
    """Claude API相关异常"""
    pass


class ConfigurationError(AddressParserBaseException):
    """配置相关异常"""
    pass


class ServerProcessError(AddressParserBaseException):
    """服务器进程相关异常"""
    pass


class ToolCallError(AddressParserBaseException):
    """工具调用相关异常"""
    pass


class ValidationError(AddressParserBaseException):
    """数据验证相关异常"""
    pass


class TimeoutError(AddressParserBaseException):
    """超时相关异常"""
    pass
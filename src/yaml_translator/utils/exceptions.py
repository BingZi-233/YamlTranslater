"""
YAML翻译器异常模块
"""
from typing import Any, Optional


class YAMLTranslatorError(Exception):
    """YAML翻译器基础异常类"""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.details = details


class ConfigError(YAMLTranslatorError):
    """配置相关错误"""
    pass


class FileError(YAMLTranslatorError):
    """文件操作相关错误"""
    pass


class YAMLError(YAMLTranslatorError):
    """YAML解析相关错误"""
    pass


class TranslationError(YAMLTranslatorError):
    """翻译相关错误"""
    pass


class APIError(YAMLTranslatorError):
    """API调用相关错误"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RateLimitError(APIError):
    """API速率限制错误"""
    pass


class AuthenticationError(APIError):
    """API认证错误"""
    pass


class NetworkError(APIError):
    """网络连接错误"""
    pass


class PromptError(YAMLTranslatorError):
    """提示词相关错误"""
    pass


class BlacklistError(YAMLTranslatorError):
    """黑名单处理相关错误"""
    pass


class ChunkError(YAMLTranslatorError):
    """分块处理相关错误"""
    pass


class ProgressError(YAMLTranslatorError):
    """进度管理相关错误"""
    pass


class ValidationError(YAMLTranslatorError):
    """数据验证相关错误"""
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        super().__init__(message)
        self.field = field
        self.value = value


class RetryError(YAMLTranslatorError):
    """重试机制相关错误"""
    def __init__(self, message: str, attempts: int, max_attempts: int):
        super().__init__(message)
        self.attempts = attempts
        self.max_attempts = max_attempts


class ConcurrencyError(YAMLTranslatorError):
    """并发处理相关错误"""
    pass


class TimeoutError(YAMLTranslatorError):
    """超时相关错误"""
    def __init__(self, message: str, timeout: float):
        super().__init__(message)
        self.timeout = timeout


class BackupError(FileError):
    """文件备份相关错误"""
    pass


class LoggingError(YAMLTranslatorError):
    """日志相关错误"""
    pass


class DisplayError(YAMLTranslatorError):
    """显示相关错误"""
    def __init__(self, message: str, component: Optional[str] = None):
        super().__init__(message)
        self.component = component 
"""
错误处理管理模块
"""
import sys
import traceback
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Type, Union

from ..config import ErrorConfig
from ..utils import log


class ErrorSeverity(Enum):
    """错误严重程度"""
    FATAL = auto()  # 致命错误，需要立即终止
    ERROR = auto()  # 普通错误，可以继续但需要处理
    WARNING = auto()  # 警告，可以继续但需要注意
    INFO = auto()  # 信息，仅作记录


class ErrorCategory(Enum):
    """错误类别"""
    SYSTEM = auto()  # 系统错误
    CONFIG = auto()  # 配置错误
    FILE = auto()  # 文件操作错误
    NETWORK = auto()  # 网络错误
    API = auto()  # API错误
    VALIDATION = auto()  # 验证错误
    TRANSLATION = auto()  # 翻译错误
    PROGRESS = auto()  # 进度错误
    RECOVERY = auto()  # 恢复错误
    UNKNOWN = auto()  # 未知错误


@dataclass
class ErrorContext:
    """错误上下文"""
    error: Exception  # 原始错误
    category: ErrorCategory  # 错误类别
    severity: ErrorSeverity  # 严重程度
    message: str  # 错误消息
    details: Optional[str] = None  # 详细信息
    source: Optional[str] = None  # 错误来源
    traceback: Optional[str] = None  # 堆栈跟踪
    data: Optional[Dict[str, Any]] = None  # 额外数据


class ErrorHandler:
    """错误处理器"""

    def __init__(self, config: ErrorConfig):
        """初始化错误处理器
        
        Args:
            config: 错误处理配置
        """
        self.config = config
        self._error_handlers: Dict[ErrorCategory, List[Callable]] = {}
        self._error_history: List[ErrorContext] = []
        
        # 注册默认处理器
        self._register_default_handlers()

    def handle_error(
        self,
        error: Exception,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None,
        source: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """处理错误
        
        Args:
            error: 异常对象
            category: 错误类别，如果不指定则自动判断
            severity: 严重程度，如果不指定则自动判断
            source: 错误来源
            data: 额外数据
            
        Returns:
            bool: 是否成功处理
        """
        try:
            # 获取错误类别
            if category is None:
                category = self._categorize_error(error)
            
            # 获取严重程度
            if severity is None:
                severity = self._determine_severity(error, category)
            
            # 创建错误上下文
            context = ErrorContext(
                error=error,
                category=category,
                severity=severity,
                message=str(error),
                details=self._get_error_details(error),
                source=source,
                traceback=traceback.format_exc(),
                data=data,
            )
            
            # 记录错误历史
            if self.config.keep_history:
                self._error_history.append(context)
                if len(self._error_history) > self.config.max_history:
                    self._error_history.pop(0)
            
            # 记录日志
            self._log_error(context)
            
            # 调用对应的处理器
            handled = False
            for handler in self._error_handlers.get(category, []):
                try:
                    if handler(context):
                        handled = True
                except Exception as e:
                    log.error(f"错误处理器执行失败: {str(e)}")
            
            # 如果是致命错误且配置要求，则终止程序
            if severity == ErrorSeverity.FATAL and self.config.exit_on_fatal:
                log.critical("遇到致命错误，程序终止")
                sys.exit(1)
            
            return handled
            
        except Exception as e:
            log.error(f"处理错误时发生异常: {str(e)}")
            return False

    def register_handler(
        self,
        category: ErrorCategory,
        handler: Callable[[ErrorContext], bool],
    ) -> None:
        """注册错误处理器
        
        Args:
            category: 错误类别
            handler: 处理函数，接收ErrorContext参数，返回是否处理成功
        """
        if category not in self._error_handlers:
            self._error_handlers[category] = []
        self._error_handlers[category].append(handler)

    def get_error_history(
        self,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None,
        limit: Optional[int] = None,
    ) -> List[ErrorContext]:
        """获取错误历史
        
        Args:
            category: 过滤的错误类别
            severity: 过滤的严重程度
            limit: 返回的最大数量
            
        Returns:
            List[ErrorContext]: 错误历史列表
        """
        result = self._error_history
        
        if category:
            result = [e for e in result if e.category == category]
        
        if severity:
            result = [e for e in result if e.severity == severity]
        
        if limit:
            result = result[-limit:]
        
        return result

    def clear_history(self) -> None:
        """清除错误历史"""
        self._error_history.clear()

    def _register_default_handlers(self) -> None:
        """注册默认的错误处理器"""
        # 系统错误处理器
        def handle_system_error(ctx: ErrorContext) -> bool:
            log.error(f"系统错误: {ctx.message}")
            if ctx.details:
                log.debug(f"详细信息: {ctx.details}")
            return True
        
        # 配置错误处理器
        def handle_config_error(ctx: ErrorContext) -> bool:
            log.error(f"配置错误: {ctx.message}")
            if ctx.source:
                log.debug(f"配置源: {ctx.source}")
            return True
        
        # 文件错误处理器
        def handle_file_error(ctx: ErrorContext) -> bool:
            log.error(f"文件操作错误: {ctx.message}")
            if ctx.data and "path" in ctx.data:
                log.debug(f"文件路径: {ctx.data['path']}")
            return True
        
        # 网络错误处理器
        def handle_network_error(ctx: ErrorContext) -> bool:
            log.error(f"网络错误: {ctx.message}")
            if ctx.data and "url" in ctx.data:
                log.debug(f"请求URL: {ctx.data['url']}")
            return True
        
        # API错误处理器
        def handle_api_error(ctx: ErrorContext) -> bool:
            log.error(f"API错误: {ctx.message}")
            if ctx.data and "response" in ctx.data:
                log.debug(f"响应内容: {ctx.data['response']}")
            return True
        
        # 验证错误处理器
        def handle_validation_error(ctx: ErrorContext) -> bool:
            log.error(f"验证错误: {ctx.message}")
            if ctx.details:
                log.debug(f"验证详情: {ctx.details}")
            return True
        
        # 翻译错误处理器
        def handle_translation_error(ctx: ErrorContext) -> bool:
            log.error(f"翻译错误: {ctx.message}")
            if ctx.data and "text" in ctx.data:
                log.debug(f"原文: {ctx.data['text']}")
            return True
        
        # 进度错误处理器
        def handle_progress_error(ctx: ErrorContext) -> bool:
            log.error(f"进度错误: {ctx.message}")
            if ctx.data and "task_id" in ctx.data:
                log.debug(f"任务ID: {ctx.data['task_id']}")
            return True
        
        # 恢复错误处理器
        def handle_recovery_error(ctx: ErrorContext) -> bool:
            log.error(f"恢复错误: {ctx.message}")
            if ctx.data and "session_id" in ctx.data:
                log.debug(f"会话ID: {ctx.data['session_id']}")
            return True
        
        # 注册处理器
        self.register_handler(ErrorCategory.SYSTEM, handle_system_error)
        self.register_handler(ErrorCategory.CONFIG, handle_config_error)
        self.register_handler(ErrorCategory.FILE, handle_file_error)
        self.register_handler(ErrorCategory.NETWORK, handle_network_error)
        self.register_handler(ErrorCategory.API, handle_api_error)
        self.register_handler(ErrorCategory.VALIDATION, handle_validation_error)
        self.register_handler(ErrorCategory.TRANSLATION, handle_translation_error)
        self.register_handler(ErrorCategory.PROGRESS, handle_progress_error)
        self.register_handler(ErrorCategory.RECOVERY, handle_recovery_error)

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """对错误进行分类
        
        Args:
            error: 错误对象
            
        Returns:
            ErrorCategory: 错误类别
        """
        error_type = type(error).__name__.lower()
        error_str = str(error).lower()
        
        # 系统错误
        if isinstance(error, (OSError, SystemError)):
            return ErrorCategory.SYSTEM
        
        # 配置错误
        if "config" in error_type or "配置" in error_str:
            return ErrorCategory.CONFIG
        
        # 文件错误
        if isinstance(error, (IOError, FileNotFoundError)):
            return ErrorCategory.FILE
        
        # 网络错误
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorCategory.NETWORK
        
        # API错误
        if "api" in error_type or "请求" in error_str:
            return ErrorCategory.API
        
        # 验证错误
        if "validation" in error_type or "验证" in error_str:
            return ErrorCategory.VALIDATION
        
        # 翻译错误
        if "translation" in error_type or "翻译" in error_str:
            return ErrorCategory.TRANSLATION
        
        # 进度错误
        if "progress" in error_type or "进度" in error_str:
            return ErrorCategory.PROGRESS
        
        # 恢复错误
        if "recovery" in error_type or "恢复" in error_str:
            return ErrorCategory.RECOVERY
        
        return ErrorCategory.UNKNOWN

    def _determine_severity(
        self,
        error: Exception,
        category: ErrorCategory,
    ) -> ErrorSeverity:
        """判断错误的严重程度
        
        Args:
            error: 错误对象
            category: 错误类别
            
        Returns:
            ErrorSeverity: 错误严重程度
        """
        # 系统错误通常是致命的
        if category == ErrorCategory.SYSTEM:
            return ErrorSeverity.FATAL
        
        # 配置错误通常是致命的
        if category == ErrorCategory.CONFIG:
            return ErrorSeverity.FATAL
        
        # 网络错误通常可以重试
        if category == ErrorCategory.NETWORK:
            return ErrorSeverity.ERROR
        
        # API错误可能是临时的
        if category == ErrorCategory.API:
            return ErrorSeverity.ERROR
        
        # 验证错误需要修复
        if category == ErrorCategory.VALIDATION:
            return ErrorSeverity.ERROR
        
        # 翻译错误可以重试
        if category == ErrorCategory.TRANSLATION:
            return ErrorSeverity.ERROR
        
        # 进度错误通常不致命
        if category == ErrorCategory.PROGRESS:
            return ErrorSeverity.WARNING
        
        # 恢复错误可能影响功能
        if category == ErrorCategory.RECOVERY:
            return ErrorSeverity.ERROR
        
        return ErrorSeverity.ERROR

    def _get_error_details(self, error: Exception) -> Optional[str]:
        """获取错误的详细信息
        
        Args:
            error: 错误对象
            
        Returns:
            Optional[str]: 详细信息
        """
        if hasattr(error, "__cause__") and error.__cause__:
            return f"Caused by: {str(error.__cause__)}"
        
        if hasattr(error, "details"):
            return str(error.details)
        
        return None

    def _log_error(self, context: ErrorContext) -> None:
        """记录错误日志
        
        Args:
            context: 错误上下文
        """
        # 根据严重程度选择日志级别
        if context.severity == ErrorSeverity.FATAL:
            log_func = log.critical
        elif context.severity == ErrorSeverity.ERROR:
            log_func = log.error
        elif context.severity == ErrorSeverity.WARNING:
            log_func = log.warning
        else:
            log_func = log.info
        
        # 记录基本信息
        log_func(f"[{context.category.name}] {context.message}")
        
        # 记录详细信息
        if context.details and self.config.log_details:
            log.debug(f"详细信息: {context.details}")
        
        # 记录来源
        if context.source and self.config.log_source:
            log.debug(f"错误来源: {context.source}")
        
        # 记录堆栈跟踪
        if context.traceback and self.config.log_traceback:
            log.debug(f"堆栈跟踪:\n{context.traceback}")
        
        # 记录额外数据
        if context.data and self.config.log_data:
            log.debug(f"相关数据: {context.data}") 
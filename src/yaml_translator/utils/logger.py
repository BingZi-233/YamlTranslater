"""
YAML翻译器日志模块
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Union

from rich.console import Console
from rich.logging import RichHandler

from ..config import LoggingConfig
from .exceptions import LoggingError


class Logger:
    """日志管理器"""
    
    _instance: Optional["Logger"] = None
    _initialized: bool = False
    
    def __new__(cls) -> "Logger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._logger = logging.getLogger("yaml_translator")
            self._console = Console()
            self._config: Optional[LoggingConfig] = None
            self._file_handler: Optional[logging.Handler] = None
            self._console_handler: Optional[logging.Handler] = None
            self._initialized = True
    
    def setup(self, config: LoggingConfig, log_dir: Optional[Union[str, Path]] = None) -> None:
        """设置日志配置
        
        Args:
            config: 日志配置对象
            log_dir: 日志文件目录，如果不指定则使用当前目录
        """
        try:
            self._config = config
            
            # 设置日志级别
            self._logger.setLevel(config.level)
            
            # 移除现有的处理器
            if self._file_handler:
                self._logger.removeHandler(self._file_handler)
            if self._console_handler:
                self._logger.removeHandler(self._console_handler)
            
            # 创建日志目录
            log_path = Path(log_dir) if log_dir else Path.cwd()
            log_path.mkdir(parents=True, exist_ok=True)
            log_file = log_path / config.file
            
            # 设置文件处理器
            self._file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=config.max_size,
                backupCount=config.backup_count,
                encoding="utf-8"
            )
            file_formatter = logging.Formatter(config.format)
            self._file_handler.setFormatter(file_formatter)
            self._logger.addHandler(self._file_handler)
            
            # 设置控制台处理器
            self._console_handler = RichHandler(
                console=self._console,
                show_time=True,
                show_path=True,
                rich_tracebacks=True,
                tracebacks_show_locals=True
            )
            self._console_handler.setLevel(config.level)
            self._logger.addHandler(self._console_handler)
            
        except Exception as e:
            raise LoggingError(f"Failed to setup logger: {str(e)}")
    
    @property
    def logger(self) -> logging.Logger:
        """获取日志记录器"""
        if not self._config:
            raise LoggingError("Logger not configured. Call setup() first.")
        return self._logger
    
    @property
    def console(self) -> Console:
        """获取控制台对象"""
        return self._console
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """记录调试级别日志"""
        self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """记录信息级别日志"""
        self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """记录警告级别日志"""
        self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """记录错误级别日志"""
        self.logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """记录严重错误级别日志"""
        self.logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, exc_info: bool = True, **kwargs) -> None:
        """记录异常信息"""
        self.logger.exception(msg, *args, exc_info=exc_info, **kwargs)
    
    def progress(self, msg: str, style: str = "bold green") -> None:
        """打印进度信息到控制台
        
        Args:
            msg: 进度信息
            style: 样式字符串，参考rich文档
        """
        self._console.print(f"[{style}]{msg}[/{style}]")
    
    def status(self, msg: str, style: str = "bold blue") -> None:
        """打印状态信息到控制台
        
        Args:
            msg: 状态信息
            style: 样式字符串，参考rich文档
        """
        self._console.print(f"[{style}]{msg}[/{style}]")
    
    def error_console(self, msg: str, style: str = "bold red") -> None:
        """打印错误信息到控制台
        
        Args:
            msg: 错误信息
            style: 样式字符串，参考rich文档
        """
        self._console.print(f"[{style}]{msg}[/{style}]", file=sys.stderr)


# 全局日志实例
log = Logger() 
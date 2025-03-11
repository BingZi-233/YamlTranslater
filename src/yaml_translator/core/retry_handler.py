"""
错误处理和重试机制模块
"""
import json
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Type, Union

from ..config import RetryConfig
from ..utils import RetryError, log
from ..utils.exceptions import APIError, RateLimitError


class ErrorCategory(str, Enum):
    """错误类别"""
    NETWORK = "network"  # 网络错误
    RATE_LIMIT = "rate_limit"  # 速率限制
    API = "api"  # API错误
    TIMEOUT = "timeout"  # 超时
    UNKNOWN = "unknown"  # 未知错误


class RetryStrategy(str, Enum):
    """重试策略"""
    IMMEDIATE = "immediate"  # 立即重试
    LINEAR = "linear"  # 线性退避
    EXPONENTIAL = "exponential"  # 指数退避
    NONE = "none"  # 不重试


@dataclass
class ErrorInfo:
    """错误信息"""
    category: ErrorCategory  # 错误类别
    message: str  # 错误消息
    details: Optional[str] = None  # 详细信息
    timestamp: float = 0.0  # 发生时间戳
    retry_count: int = 0  # 重试次数


@dataclass
class RetryState:
    """重试状态"""
    task_id: str  # 任务ID
    error_history: List[ErrorInfo]  # 错误历史
    next_retry_time: float  # 下次重试时间
    strategy: RetryStrategy  # 当前重试策略
    max_retries: int  # 最大重试次数


class RetryHandler:
    """重试处理器"""

    def __init__(self, config: RetryConfig):
        """初始化重试处理器
        
        Args:
            config: 重试配置
        """
        self.config = config
        self._retry_states: Dict[str, RetryState] = {}
        self._error_patterns: Dict[str, ErrorCategory] = self._init_error_patterns()
        self._save_path = Path(config.save_path)
        self._save_path.mkdir(parents=True, exist_ok=True)
        
        # 加载保存的重试状态
        if config.auto_resume:
            self._load_states()

    def should_retry(self, task_id: str, error: Exception) -> Tuple[bool, float]:
        """检查是否应该重试
        
        Args:
            task_id: 任务ID
            error: 发生的错误
            
        Returns:
            Tuple[bool, float]: (是否重试, 等待时间)
        """
        try:
            # 获取或创建重试状态
            state = self._get_or_create_state(task_id)
            
            # 分类错误
            error_info = self._categorize_error(error)
            error_info.timestamp = time.time()
            
            # 更新错误历史
            state.error_history.append(error_info)
            
            # 如果超过最大重试次数，不再重试
            if len(state.error_history) >= state.max_retries:
                return False, 0
            
            # 更新重试策略
            self._update_retry_strategy(state)
            
            # 计算等待时间
            wait_time = self._calculate_wait_time(state)
            state.next_retry_time = time.time() + wait_time
            
            # 保存状态
            self._save_states()
            
            return True, wait_time
            
        except Exception as e:
            log.error(f"Error in should_retry for task {task_id}: {str(e)}")
            return False, 0

    def get_retry_info(self, task_id: str) -> Optional[RetryState]:
        """获取重试信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[RetryState]: 重试状态
        """
        return self._retry_states.get(task_id)

    def clear_retry_info(self, task_id: str) -> None:
        """清除重试信息
        
        Args:
            task_id: 任务ID
        """
        self._retry_states.pop(task_id, None)
        self._save_states()

    def get_failed_tasks(self) -> List[str]:
        """获取所有失败的任务ID
        
        Returns:
            List[str]: 失败任务ID列表
        """
        return list(self._retry_states.keys())

    def _get_or_create_state(self, task_id: str) -> RetryState:
        """获取或创建重试状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            RetryState: 重试状态
        """
        if task_id not in self._retry_states:
            self._retry_states[task_id] = RetryState(
                task_id=task_id,
                error_history=[],
                next_retry_time=0.0,
                strategy=RetryStrategy.IMMEDIATE,
                max_retries=self.config.max_retries,
            )
        return self._retry_states[task_id]

    def _categorize_error(self, error: Exception) -> ErrorInfo:
        """对错误进行分类
        
        Args:
            error: 发生的错误
            
        Returns:
            ErrorInfo: 错误信息
        """
        # 检查已知的错误类型
        if isinstance(error, RateLimitError):
            return ErrorInfo(
                category=ErrorCategory.RATE_LIMIT,
                message="API rate limit exceeded",
                details=str(error),
            )
        elif isinstance(error, APIError):
            return ErrorInfo(
                category=ErrorCategory.API,
                message="API error occurred",
                details=str(error),
            )
        elif isinstance(error, TimeoutError):
            return ErrorInfo(
                category=ErrorCategory.TIMEOUT,
                message="Operation timed out",
                details=str(error),
            )
        
        # 使用错误模式匹配
        error_str = str(error).lower()
        for pattern, category in self._error_patterns.items():
            if pattern in error_str:
                return ErrorInfo(
                    category=category,
                    message=str(error),
                )
        
        # 未知错误
        return ErrorInfo(
            category=ErrorCategory.UNKNOWN,
            message=str(error),
        )

    def _update_retry_strategy(self, state: RetryState) -> None:
        """更新重试策略
        
        Args:
            state: 重试状态
        """
        # 获取最近的错误
        if not state.error_history:
            return
        
        latest_error = state.error_history[-1]
        
        # 根据错误类别和历史选择策略
        if latest_error.category == ErrorCategory.RATE_LIMIT:
            # 速率限制使用指数退避
            state.strategy = RetryStrategy.EXPONENTIAL
        elif latest_error.category == ErrorCategory.NETWORK:
            # 网络错误使用线性退避
            state.strategy = RetryStrategy.LINEAR
        elif latest_error.category == ErrorCategory.API:
            # API错误根据重试次数决定
            if len(state.error_history) > 2:
                state.strategy = RetryStrategy.EXPONENTIAL
            else:
                state.strategy = RetryStrategy.LINEAR
        elif latest_error.category == ErrorCategory.TIMEOUT:
            # 超时错误使用线性退避
            state.strategy = RetryStrategy.LINEAR
        else:
            # 未知错误使用保守策略
            state.strategy = RetryStrategy.EXPONENTIAL

    def _calculate_wait_time(self, state: RetryState) -> float:
        """计算等待时间
        
        Args:
            state: 重试状态
            
        Returns:
            float: 等待时间（秒）
        """
        retry_count = len(state.error_history)
        base_delay = self.config.base_delay
        
        if state.strategy == RetryStrategy.IMMEDIATE:
            return 0.0
        elif state.strategy == RetryStrategy.LINEAR:
            return base_delay * retry_count
        elif state.strategy == RetryStrategy.EXPONENTIAL:
            return base_delay * (2 ** (retry_count - 1))
        else:
            return float('inf')  # 不重试

    def _save_states(self) -> None:
        """保存重试状态"""
        try:
            # 准备保存数据
            data = {
                task_id: {
                    "error_history": [asdict(e) for e in state.error_history],
                    "next_retry_time": state.next_retry_time,
                    "strategy": state.strategy.value,
                    "max_retries": state.max_retries,
                }
                for task_id, state in self._retry_states.items()
            }
            
            # 保存到文件
            save_file = self._save_path / "retry_states.json"
            with save_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            log.debug("Saved retry states")
            
        except Exception as e:
            log.error(f"Failed to save retry states: {str(e)}")

    def _load_states(self) -> None:
        """加载重试状态"""
        try:
            save_file = self._save_path / "retry_states.json"
            if not save_file.exists():
                return
            
            # 读取保存的数据
            with save_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 恢复状态
            for task_id, state_data in data.items():
                error_history = [
                    ErrorInfo(**e) for e in state_data["error_history"]
                ]
                self._retry_states[task_id] = RetryState(
                    task_id=task_id,
                    error_history=error_history,
                    next_retry_time=state_data["next_retry_time"],
                    strategy=RetryStrategy(state_data["strategy"]),
                    max_retries=state_data["max_retries"],
                )
            
            log.debug("Loaded retry states")
            
        except Exception as e:
            log.error(f"Failed to load retry states: {str(e)}")

    @staticmethod
    def _init_error_patterns() -> Dict[str, ErrorCategory]:
        """初始化错误模式匹配字典
        
        Returns:
            Dict[str, ErrorCategory]: 错误模式和类别的映射
        """
        return {
            "connection": ErrorCategory.NETWORK,
            "timeout": ErrorCategory.TIMEOUT,
            "network": ErrorCategory.NETWORK,
            "dns": ErrorCategory.NETWORK,
            "socket": ErrorCategory.NETWORK,
            "rate limit": ErrorCategory.RATE_LIMIT,
            "too many requests": ErrorCategory.RATE_LIMIT,
            "api": ErrorCategory.API,
            "invalid": ErrorCategory.API,
            "unauthorized": ErrorCategory.API,
        } 
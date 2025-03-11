"""
错误重试管理模块
"""
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple, Union

from ..config import RetryConfig
from ..utils import RetryError, log


class ErrorCategory(Enum):
    """错误类别"""
    NETWORK = "network"  # 网络错误
    RATE_LIMIT = "rate_limit"  # 速率限制
    API = "api"  # API错误
    VALIDATION = "validation"  # 验证错误
    TIMEOUT = "timeout"  # 超时
    UNKNOWN = "unknown"  # 未知错误


@dataclass
class RetryState:
    """重试状态"""
    task_id: str  # 任务ID
    error_category: ErrorCategory  # 错误类别
    attempt_count: int  # 尝试次数
    last_attempt: float  # 上次尝试时间
    next_attempt: float  # 下次尝试时间
    error_message: str  # 错误信息
    backoff_factor: float  # 退避因子


class RetryManager:
    """重试管理器"""

    def __init__(self, config: RetryConfig):
        """初始化重试管理器
        
        Args:
            config: 重试配置
        """
        self.config = config
        self._states: Dict[str, RetryState] = {}
        self._error_patterns = {
            ErrorCategory.NETWORK: [
                "ConnectionError",
                "TimeoutError",
                "NetworkError",
            ],
            ErrorCategory.RATE_LIMIT: [
                "RateLimitError",
                "TooManyRequests",
                "429",
            ],
            ErrorCategory.API: [
                "APIError",
                "InvalidRequest",
                "AuthenticationError",
            ],
            ErrorCategory.VALIDATION: [
                "ValidationError",
                "InvalidFormat",
                "SchemaError",
            ],
            ErrorCategory.TIMEOUT: [
                "Timeout",
                "DeadlineExceeded",
            ],
        }

    def should_retry(self, task_id: str, error: Exception) -> Tuple[bool, float]:
        """检查是否应该重试
        
        Args:
            task_id: 任务ID
            error: 发生的错误
            
        Returns:
            Tuple[bool, float]: (是否重试, 等待时间)
        """
        try:
            # 获取错误类别
            category = self._categorize_error(error)
            
            # 获取或创建重试状态
            state = self._states.get(task_id)
            if not state:
                state = RetryState(
                    task_id=task_id,
                    error_category=category,
                    attempt_count=0,
                    last_attempt=0,
                    next_attempt=0,
                    error_message=str(error),
                    backoff_factor=1.0,
                )
                self._states[task_id] = state
            
            # 检查重试次数
            if state.attempt_count >= self._get_max_retries(category):
                log.warning(f"任务 {task_id} 达到最大重试次数")
                return False, 0
            
            # 计算等待时间
            wait_time = self._calculate_wait_time(state)
            
            # 更新状态
            state.attempt_count += 1
            state.last_attempt = time.time()
            state.next_attempt = state.last_attempt + wait_time
            state.error_message = str(error)
            
            # 根据错误类别调整退避因子
            state.backoff_factor = self._adjust_backoff_factor(state)
            
            return True, wait_time
            
        except Exception as e:
            log.error(f"检查重试状态失败: {str(e)}")
            return False, 0

    def reset(self, task_id: str) -> None:
        """重置任务的重试状态
        
        Args:
            task_id: 任务ID
        """
        self._states.pop(task_id, None)

    def get_state(self, task_id: str) -> Optional[RetryState]:
        """获取任务的重试状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[RetryState]: 重试状态
        """
        return self._states.get(task_id)

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """对错误进行分类
        
        Args:
            error: 错误对象
            
        Returns:
            ErrorCategory: 错误类别
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        for category, patterns in self._error_patterns.items():
            if any(pattern.lower() in error_str or pattern.lower() in error_type.lower() 
                  for pattern in patterns):
                return category
        
        return ErrorCategory.UNKNOWN

    def _get_max_retries(self, category: ErrorCategory) -> int:
        """获取最大重试次数
        
        Args:
            category: 错误类别
            
        Returns:
            int: 最大重试次数
        """
        # 根据错误类别返回不同的最大重试次数
        return {
            ErrorCategory.NETWORK: self.config.max_network_retries,
            ErrorCategory.RATE_LIMIT: self.config.max_rate_limit_retries,
            ErrorCategory.API: self.config.max_api_retries,
            ErrorCategory.VALIDATION: self.config.max_validation_retries,
            ErrorCategory.TIMEOUT: self.config.max_timeout_retries,
            ErrorCategory.UNKNOWN: self.config.max_unknown_retries,
        }.get(category, self.config.max_unknown_retries)

    def _calculate_wait_time(self, state: RetryState) -> float:
        """计算等待时间
        
        Args:
            state: 重试状态
            
        Returns:
            float: 等待时间（秒）
        """
        # 基础等待时间
        base_wait = self.config.base_wait_time
        
        # 根据错误类别调整
        category_multiplier = {
            ErrorCategory.NETWORK: 1.0,
            ErrorCategory.RATE_LIMIT: 2.0,
            ErrorCategory.API: 1.5,
            ErrorCategory.VALIDATION: 1.0,
            ErrorCategory.TIMEOUT: 1.2,
            ErrorCategory.UNKNOWN: 1.0,
        }.get(state.error_category, 1.0)
        
        # 计算指数退避时间
        wait_time = base_wait * (state.backoff_factor ** state.attempt_count)
        wait_time *= category_multiplier
        
        # 添加随机抖动
        jitter = self.config.jitter_factor * wait_time * (0.5 - time.time() % 1)
        wait_time += jitter
        
        # 确保在最小和最大等待时间之间
        return max(
            self.config.min_wait_time,
            min(wait_time, self.config.max_wait_time),
        )

    def _adjust_backoff_factor(self, state: RetryState) -> float:
        """调整退避因子
        
        Args:
            state: 重试状态
            
        Returns:
            float: 新的退避因子
        """
        # 根据错误类别和重试次数调整退避因子
        if state.error_category == ErrorCategory.RATE_LIMIT:
            # 速率限制错误使用更激进的退避
            return min(state.backoff_factor * 2.0, 4.0)
        elif state.error_category == ErrorCategory.NETWORK:
            # 网络错误使用温和的退避
            return min(state.backoff_factor * 1.5, 3.0)
        elif state.attempt_count > 3:
            # 多次重试后增加退避
            return min(state.backoff_factor * 1.2, 2.0)
        
        return state.backoff_factor 
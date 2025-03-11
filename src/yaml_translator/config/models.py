"""
配置模型模块
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class ChunkConfig(BaseModel):
    """分块配置"""
    max_chunk_size: int = Field(
        default=4000,
        description="每个块的最大字符数",
    )
    min_chunk_size: int = Field(
        default=100,
        description="每个块的最小字符数",
    )
    split_keywords: List[str] = Field(
        default=["---", "===", "###"],
        description="触发分块的关键字",
    )
    context_lines: int = Field(
        default=2,
        description="每个块保留的上下文行数",
    )
    merge_threshold: float = Field(
        default=0.8,
        description="块合并阈值",
    )


class RetryConfig(BaseModel):
    """重试配置"""
    max_network_retries: int = Field(
        default=3,
        description="网络错误最大重试次数",
    )
    max_rate_limit_retries: int = Field(
        default=5,
        description="速率限制最大重试次数",
    )
    max_api_retries: int = Field(
        default=3,
        description="API错误最大重试次数",
    )
    max_validation_retries: int = Field(
        default=2,
        description="验证错误最大重试次数",
    )
    max_timeout_retries: int = Field(
        default=3,
        description="超时最大重试次数",
    )
    max_unknown_retries: int = Field(
        default=2,
        description="未知错误最大重试次数",
    )
    base_wait_time: float = Field(
        default=1.0,
        description="基础等待时间（秒）",
    )
    min_wait_time: float = Field(
        default=0.1,
        description="最小等待时间（秒）",
    )
    max_wait_time: float = Field(
        default=300.0,
        description="最大等待时间（秒）",
    )
    jitter_factor: float = Field(
        default=0.1,
        description="随机抖动因子",
    )


class RecoveryConfig(BaseModel):
    """恢复配置"""
    save_path: str = Field(
        default=".progress",
        description="进度保存路径",
    )
    save_interval: int = Field(
        default=30,
        description="保存间隔（秒）",
    )
    auto_resume: bool = Field(
        default=True,
        description="是否自动恢复",
    )
    max_checkpoint_age: int = Field(
        default=86400 * 7,  # 7天
        description="检查点最大保留时间（秒）",
    )
    keep_failed_tasks: bool = Field(
        default=True,
        description="是否保留失败任务",
    )


class ErrorConfig(BaseModel):
    """错误处理配置"""
    exit_on_fatal: bool = Field(
        default=True,
        description="遇到致命错误时是否退出程序",
    )
    keep_history: bool = Field(
        default=True,
        description="是否保留错误历史",
    )
    max_history: int = Field(
        default=100,
        description="最大保留的错误历史数量",
    )
    log_details: bool = Field(
        default=True,
        description="是否记录错误详细信息",
    )
    log_source: bool = Field(
        default=True,
        description="是否记录错误来源",
    )
    log_traceback: bool = Field(
        default=True,
        description="是否记录堆栈跟踪",
    )
    log_data: bool = Field(
        default=True,
        description="是否记录相关数据",
    ) 
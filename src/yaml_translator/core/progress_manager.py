"""
进度管理模块
"""
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

import pytz

from ..config import ProgressConfig
from ..utils import ProgressError, log


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"  # 等待处理
    RUNNING = "running"  # 正在处理
    PAUSED = "paused"   # 已暂停
    FAILED = "failed"   # 处理失败
    SUCCESS = "success" # 处理成功


@dataclass
class FileProgress:
    """文件处理进度"""
    path: str  # 文件路径
    size: int  # 文件大小（字节）
    total_chunks: int  # 总块数
    completed_chunks: int  # 已完成块数
    tokens_used: int  # 已使用的token数
    start_time: float  # 开始时间戳
    last_update: float  # 最后更新时间戳
    status: TaskStatus  # 当前状态
    error: Optional[str] = None  # 错误信息


@dataclass
class SessionInfo:
    """会话信息"""
    start_time: float  # 会话开始时间戳
    last_update: float  # 最后更新时间戳
    total_files: int  # 总文件数
    completed_files: int  # 已完成文件数
    total_tokens: int  # 总token数
    total_cost: float  # 总费用（美元）
    elapsed_time: float  # 已用时间（秒）


class ProgressManager:
    """进度管理器"""

    def __init__(self, config: ProgressConfig):
        """初始化进度管理器
        
        Args:
            config: 进度配置
        """
        self.config = config
        self._save_path = Path(config.save_path)
        self._save_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化会话信息
        self._session = SessionInfo(
            start_time=time.time(),
            last_update=time.time(),
            total_files=0,
            completed_files=0,
            total_tokens=0,
            total_cost=0.0,
            elapsed_time=0.0,
        )
        
        # 初始化文件进度字典
        self._files: Dict[str, FileProgress] = {}
        
        # 加载保存的进度
        if config.auto_resume:
            self._load_progress()

    def add_file(self, file_path: Union[str, Path], size: int, total_chunks: int) -> None:
        """添加文件到进度管理器
        
        Args:
            file_path: 文件路径
            size: 文件大小（字节）
            total_chunks: 总块数
            
        Raises:
            ProgressError: 添加文件失败
        """
        try:
            path_str = str(file_path)
            if path_str in self._files:
                raise ProgressError(f"File already exists: {path_str}")
            
            self._files[path_str] = FileProgress(
                path=path_str,
                size=size,
                total_chunks=total_chunks,
                completed_chunks=0,
                tokens_used=0,
                start_time=time.time(),
                last_update=time.time(),
                status=TaskStatus.PENDING,
            )
            
            self._session.total_files += 1
            self._save_progress()
            
            log.debug(f"Added file to progress manager: {path_str}")
            
        except Exception as e:
            log.error(f"Failed to add file {file_path}: {str(e)}")
            raise ProgressError(f"Failed to add file {file_path}", details=str(e))

    def update_file_progress(
        self,
        file_path: Union[str, Path],
        completed_chunks: int,
        tokens_used: int,
        status: TaskStatus,
        error: Optional[str] = None,
    ) -> None:
        """更新文件进度
        
        Args:
            file_path: 文件路径
            completed_chunks: 已完成块数
            tokens_used: 已使用的token数
            status: 当前状态
            error: 错误信息
            
        Raises:
            ProgressError: 更新进度失败
        """
        try:
            path_str = str(file_path)
            if path_str not in self._files:
                raise ProgressError(f"File not found: {path_str}")
            
            progress = self._files[path_str]
            
            # 更新进度信息
            progress.completed_chunks = completed_chunks
            progress.tokens_used = tokens_used
            progress.last_update = time.time()
            progress.status = status
            progress.error = error
            
            # 如果状态变为完成或失败，更新会话信息
            if status in (TaskStatus.SUCCESS, TaskStatus.FAILED):
                self._session.completed_files += 1
                self._session.total_tokens += tokens_used
                self._session.total_cost += self._calculate_cost(tokens_used)
            
            # 更新会话时间
            self._update_session_time()
            
            # 保存进度
            if self._should_save_progress():
                self._save_progress()
            
            log.debug(f"Updated file progress: {path_str}, status: {status.value}")
            
        except Exception as e:
            log.error(f"Failed to update file progress {file_path}: {str(e)}")
            raise ProgressError(f"Failed to update file progress {file_path}", details=str(e))

    def get_file_progress(self, file_path: Union[str, Path]) -> Optional[FileProgress]:
        """获取文件进度
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[FileProgress]: 文件进度信息，如果不存在则返回None
        """
        return self._files.get(str(file_path))

    def get_session_info(self) -> SessionInfo:
        """获取会话信息
        
        Returns:
            SessionInfo: 会话信息
        """
        self._update_session_time()
        return self._session

    def get_all_files(self) -> List[FileProgress]:
        """获取所有文件的进度
        
        Returns:
            List[FileProgress]: 文件进度列表
        """
        return list(self._files.values())

    def get_pending_files(self) -> List[FileProgress]:
        """获取待处理的文件
        
        Returns:
            List[FileProgress]: 待处理文件列表
        """
        return [
            f for f in self._files.values()
            if f.status in (TaskStatus.PENDING, TaskStatus.PAUSED)
        ]

    def get_failed_files(self) -> List[FileProgress]:
        """获取处理失败的文件
        
        Returns:
            List[FileProgress]: 失败文件列表
        """
        return [f for f in self._files.values() if f.status == TaskStatus.FAILED]

    def clear_progress(self) -> None:
        """清除所有进度信息"""
        self._files.clear()
        self._session = SessionInfo(
            start_time=time.time(),
            last_update=time.time(),
            total_files=0,
            completed_files=0,
            total_tokens=0,
            total_cost=0.0,
            elapsed_time=0.0,
        )
        self._save_progress()
        log.debug("Cleared all progress information")

    def _save_progress(self) -> None:
        """保存进度信息到文件"""
        try:
            # 准备保存数据
            data = {
                "session": asdict(self._session),
                "files": {
                    path: asdict(progress)
                    for path, progress in self._files.items()
                },
                "timestamp": datetime.now(pytz.UTC).isoformat(),
            }
            
            # 保存到文件
            save_file = self._save_path / "progress.json"
            with save_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # 如果需要保留历史记录
            if self.config.keep_history:
                history_file = self._save_path / f"progress_{int(time.time())}.json"
                with history_file.open("w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            
            log.debug("Saved progress information")
            
        except Exception as e:
            log.error(f"Failed to save progress: {str(e)}")
            raise ProgressError("Failed to save progress", details=str(e))

    def _load_progress(self) -> None:
        """从文件加载进度信息"""
        try:
            save_file = self._save_path / "progress.json"
            if not save_file.exists():
                return
            
            # 读取保存的数据
            with save_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 恢复会话信息
            session_data = data["session"]
            self._session = SessionInfo(**session_data)
            
            # 恢复文件进度
            for path, file_data in data["files"].items():
                self._files[path] = FileProgress(**file_data)
            
            log.debug("Loaded progress information")
            
        except Exception as e:
            log.error(f"Failed to load progress: {str(e)}")
            raise ProgressError("Failed to load progress", details=str(e))

    def _update_session_time(self) -> None:
        """更新会话时间信息"""
        current_time = time.time()
        self._session.last_update = current_time
        self._session.elapsed_time = current_time - self._session.start_time

    def _should_save_progress(self) -> bool:
        """检查是否应该保存进度
        
        Returns:
            bool: 是否应该保存
        """
        # 如果距离上次保存时间超过配置的间隔，则保存
        return (time.time() - self._session.last_update) >= self.config.save_interval

    @staticmethod
    def _calculate_cost(tokens: int) -> float:
        """计算token使用成本
        
        Args:
            tokens: 使用的token数
            
        Returns:
            float: 成本（美元）
        """
        # 使用GPT-3.5-turbo的价格：$0.002 per 1K tokens
        return (tokens / 1000) * 0.002 
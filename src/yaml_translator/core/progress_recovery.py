"""
进度恢复管理模块
"""
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..config import RecoveryConfig
from ..utils import RecoveryError, log


@dataclass
class TaskState:
    """任务状态"""
    task_id: str  # 任务ID
    file_path: str  # 文件路径
    total_chunks: int  # 总块数
    completed_chunks: int  # 已完成块数
    failed_chunks: Set[int]  # 失败的块索引
    start_time: float  # 开始时间
    last_update: float  # 最后更新时间
    is_completed: bool  # 是否完成
    error_message: Optional[str] = None  # 错误信息


@dataclass
class SessionState:
    """会话状态"""
    session_id: str  # 会话ID
    start_time: float  # 开始时间
    last_update: float  # 最后更新时间
    total_files: int  # 总文件数
    completed_files: int  # 已完成文件数
    failed_files: Set[str]  # 失败的文件
    total_tokens: int  # 总token数
    total_cost: float  # 总成本


class ProgressRecoveryManager:
    """进度恢复管理器"""

    def __init__(self, config: RecoveryConfig):
        """初始化进度恢复管理器
        
        Args:
            config: 恢复配置
        """
        self.config = config
        self._session: Optional[SessionState] = None
        self._tasks: Dict[str, TaskState] = {}
        self._save_path = Path(config.save_path)
        
        # 创建保存目录
        self._save_path.mkdir(parents=True, exist_ok=True)
        
        # 如果启用自动恢复，尝试加载最新的进度
        if config.auto_resume:
            self._try_auto_resume()

    def start_session(self, total_files: int) -> str:
        """开始新会话
        
        Args:
            total_files: 总文件数
            
        Returns:
            str: 会话ID
        """
        session_id = str(int(time.time()))
        self._session = SessionState(
            session_id=session_id,
            start_time=time.time(),
            last_update=time.time(),
            total_files=total_files,
            completed_files=0,
            failed_files=set(),
            total_tokens=0,
            total_cost=0.0,
        )
        
        # 保存初始状态
        self._save_state()
        
        return session_id

    def add_task(
        self,
        task_id: str,
        file_path: str,
        total_chunks: int,
    ) -> None:
        """添加任务
        
        Args:
            task_id: 任务ID
            file_path: 文件路径
            total_chunks: 总块数
        """
        if not self._session:
            raise RecoveryError("No active session")
        
        self._tasks[task_id] = TaskState(
            task_id=task_id,
            file_path=file_path,
            total_chunks=total_chunks,
            completed_chunks=0,
            failed_chunks=set(),
            start_time=time.time(),
            last_update=time.time(),
            is_completed=False,
        )
        
        # 如果达到保存间隔，保存状态
        if self._should_save():
            self._save_state()

    def update_task(
        self,
        task_id: str,
        completed_chunks: Optional[int] = None,
        failed_chunk: Optional[int] = None,
        error_message: Optional[str] = None,
        tokens: Optional[int] = None,
        cost: Optional[float] = None,
    ) -> None:
        """更新任务状态
        
        Args:
            task_id: 任务ID
            completed_chunks: 已完成块数
            failed_chunk: 失败的块索引
            error_message: 错误信息
            tokens: token数
            cost: 成本
        """
        if not self._session:
            raise RecoveryError("No active session")
        
        task = self._tasks.get(task_id)
        if not task:
            raise RecoveryError(f"Task not found: {task_id}")
        
        # 更新任务状态
        if completed_chunks is not None:
            task.completed_chunks = completed_chunks
        
        if failed_chunk is not None:
            task.failed_chunks.add(failed_chunk)
        
        if error_message:
            task.error_message = error_message
        
        task.last_update = time.time()
        
        # 检查是否完成
        if task.completed_chunks == task.total_chunks:
            task.is_completed = True
            self._session.completed_files += 1
        
        # 更新会话状态
        if tokens:
            self._session.total_tokens += tokens
        
        if cost:
            self._session.total_cost += cost
        
        self._session.last_update = time.time()
        
        # 如果达到保存间隔，保存状态
        if self._should_save():
            self._save_state()

    def mark_task_failed(self, task_id: str, error: Exception) -> None:
        """标记任务失败
        
        Args:
            task_id: 任务ID
            error: 错误信息
        """
        if not self._session:
            raise RecoveryError("No active session")
        
        task = self._tasks.get(task_id)
        if not task:
            raise RecoveryError(f"Task not found: {task_id}")
        
        # 更新任务状态
        task.error_message = str(error)
        task.last_update = time.time()
        
        # 更新会话状态
        self._session.failed_files.add(task.file_path)
        self._session.last_update = time.time()
        
        # 保存状态
        self._save_state()

    def get_failed_tasks(self) -> List[TaskState]:
        """获取失败的任务
        
        Returns:
            List[TaskState]: 失败的任务列表
        """
        return [
            task for task in self._tasks.values()
            if task.error_message or task.failed_chunks
        ]

    def get_session_stats(self) -> Tuple[int, int, int, float]:
        """获取会话统计信息
        
        Returns:
            Tuple[int, int, int, float]: (完成文件数, 总文件数, 总token数, 总成本)
        """
        if not self._session:
            raise RecoveryError("No active session")
        
        return (
            self._session.completed_files,
            self._session.total_files,
            self._session.total_tokens,
            self._session.total_cost,
        )

    def save_checkpoint(self) -> None:
        """保存检查点"""
        if not self._session:
            raise RecoveryError("No active session")
        
        self._save_state()

    def load_checkpoint(self, session_id: str) -> None:
        """加载检查点
        
        Args:
            session_id: 会话ID
        """
        checkpoint_file = self._save_path / f"{session_id}.json"
        if not checkpoint_file.exists():
            raise RecoveryError(f"Checkpoint not found: {session_id}")
        
        try:
            # 加载状态
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 恢复会话状态
            self._session = SessionState(**data["session"])
            self._session.failed_files = set(data["session"]["failed_files"])
            
            # 恢复任务状态
            self._tasks.clear()
            for task_data in data["tasks"]:
                task = TaskState(**task_data)
                task.failed_chunks = set(task_data["failed_chunks"])
                self._tasks[task.task_id] = task
            
            log.info(f"已加载检查点: {session_id}")
            
        except Exception as e:
            raise RecoveryError(f"Failed to load checkpoint: {str(e)}")

    def cleanup_old_checkpoints(self, max_age: Optional[int] = None) -> None:
        """清理旧的检查点
        
        Args:
            max_age: 最大保留时间（秒），默认使用配置值
        """
        if not max_age:
            max_age = self.config.max_checkpoint_age
        
        try:
            current_time = time.time()
            
            # 遍历检查点文件
            for checkpoint_file in self._save_path.glob("*.json"):
                # 检查文件年龄
                file_age = current_time - checkpoint_file.stat().st_mtime
                if file_age > max_age:
                    checkpoint_file.unlink()
                    log.debug(f"已删除旧检查点: {checkpoint_file.name}")
            
        except Exception as e:
            log.error(f"清理检查点失败: {str(e)}")

    def _should_save(self) -> bool:
        """检查是否应该保存状态"""
        if not self._session:
            return False
        
        # 检查距离上次保存的时间
        time_since_save = time.time() - self._session.last_update
        return time_since_save >= self.config.save_interval

    def _save_state(self) -> None:
        """保存当前状态"""
        if not self._session:
            return
        
        try:
            # 准备保存数据
            data = {
                "session": {
                    **asdict(self._session),
                    "failed_files": list(self._session.failed_files),
                },
                "tasks": [
                    {
                        **asdict(task),
                        "failed_chunks": list(task.failed_chunks),
                    }
                    for task in self._tasks.values()
                ],
            }
            
            # 保存到文件
            checkpoint_file = self._save_path / f"{self._session.session_id}.json"
            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            log.debug(f"已保存进度到: {checkpoint_file}")
            
        except Exception as e:
            log.error(f"保存进度失败: {str(e)}")

    def _try_auto_resume(self) -> None:
        """尝试自动恢复最新的进度"""
        try:
            # 查找最新的检查点
            checkpoints = list(self._save_path.glob("*.json"))
            if not checkpoints:
                return
            
            # 按修改时间排序
            latest_checkpoint = max(
                checkpoints,
                key=lambda p: p.stat().st_mtime,
            )
            
            # 加载检查点
            session_id = latest_checkpoint.stem
            self.load_checkpoint(session_id)
            
            log.info("已自动恢复最新进度")
            
        except Exception as e:
            log.error(f"自动恢复失败: {str(e)}") 
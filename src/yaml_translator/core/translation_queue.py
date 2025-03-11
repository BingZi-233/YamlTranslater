"""
翻译队列管理模块
"""
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from ..config import TranslationConfig
from ..utils import QueueError, log
from .openai_client import OpenAIClient


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"  # 等待处理
    RUNNING = "running"  # 正在处理
    COMPLETED = "completed"  # 处理完成
    FAILED = "failed"  # 处理失败


@dataclass
class TranslationTask:
    """翻译任务"""
    id: str  # 任务ID
    content: str  # 要翻译的内容
    system_prompt: str  # 系统提示词
    context: Optional[str] = None  # 上下文信息
    result: Optional[str] = None  # 翻译结果
    error: Optional[str] = None  # 错误信息
    status: TaskStatus = TaskStatus.PENDING  # 任务状态
    retries: int = 0  # 重试次数
    priority: int = 0  # 优先级（数字越大优先级越高）


class TranslationQueue:
    """翻译队列管理器"""

    def __init__(self, config: TranslationConfig, client: OpenAIClient):
        """初始化翻译队列管理器
        
        Args:
            config: 翻译配置
            client: OpenAI API客户端
        """
        self.config = config
        self.client = client
        
        # 任务队列（按优先级排序）
        self._tasks: List[TranslationTask] = []
        
        # 正在处理的任务ID集合
        self._processing: Set[str] = set()
        
        # 并发控制
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        
        # 任务完成事件字典
        self._task_events: Dict[str, asyncio.Event] = {}

    async def add_task(
        self,
        content: str,
        system_prompt: str,
        task_id: str,
        context: Optional[str] = None,
        priority: int = 0,
    ) -> None:
        """添加翻译任务
        
        Args:
            content: 要翻译的内容
            system_prompt: 系统提示词
            task_id: 任务ID
            context: 上下文信息
            priority: 优先级
            
        Raises:
            QueueError: 队列错误
        """
        try:
            # 检查任务ID是否已存在
            if task_id in self._processing or any(t.id == task_id for t in self._tasks):
                raise QueueError(f"Task ID already exists: {task_id}")
            
            # 创建任务
            task = TranslationTask(
                id=task_id,
                content=content,
                system_prompt=system_prompt,
                context=context,
                priority=priority,
            )
            
            # 创建任务完成事件
            self._task_events[task_id] = asyncio.Event()
            
            # 按优先级插入任务
            self._insert_task(task)
            
            log.debug(f"Added translation task: {task_id}")
            
        except Exception as e:
            log.error(f"Failed to add task {task_id}: {str(e)}")
            raise QueueError(f"Failed to add task {task_id}", details=str(e))

    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> str:
        """获取任务结果
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒），None表示永不超时
            
        Returns:
            str: 翻译结果
            
        Raises:
            QueueError: 队列错误
            TimeoutError: 等待超时
        """
        try:
            # 获取任务完成事件
            event = self._task_events.get(task_id)
            if not event:
                raise QueueError(f"Task not found: {task_id}")
            
            # 等待任务完成
            try:
                await asyncio.wait_for(event.wait(), timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Timeout waiting for task {task_id}")
            
            # 查找任务结果
            task = self._find_task(task_id)
            if not task:
                raise QueueError(f"Task result not found: {task_id}")
            
            # 检查任务状态
            if task.status == TaskStatus.FAILED:
                raise QueueError(f"Task failed: {task_id}", details=task.error)
            
            if not task.result:
                raise QueueError(f"Task has no result: {task_id}")
            
            return task.result
            
        except TimeoutError:
            raise
        except Exception as e:
            log.error(f"Failed to get result for task {task_id}: {str(e)}")
            raise QueueError(f"Failed to get result for task {task_id}", details=str(e))

    async def process_queue(self) -> None:
        """处理翻译队列
        
        持续处理队列中的任务，直到队列为空
        """
        try:
            while True:
                # 获取待处理的任务
                task = self._get_next_task()
                if not task:
                    # 如果没有待处理的任务，等待一会再检查
                    await asyncio.sleep(0.1)
                    continue
                
                # 启动任务处理
                asyncio.create_task(self._process_task(task))
                
        except Exception as e:
            log.error(f"Queue processing error: {str(e)}")
            raise QueueError("Queue processing error", details=str(e))

    def get_queue_status(self) -> Dict[str, int]:
        """获取队列状态
        
        Returns:
            Dict[str, int]: 各状态的任务数量
        """
        status_count = {status: 0 for status in TaskStatus}
        
        # 统计队列中的任务
        for task in self._tasks:
            status_count[task.status] += 1
        
        # 统计正在处理的任务
        status_count[TaskStatus.RUNNING] = len(self._processing)
        
        return status_count

    def _insert_task(self, task: TranslationTask) -> None:
        """按优先级插入任务
        
        Args:
            task: 要插入的任务
        """
        # 找到合适的插入位置（优先级高的排在前面）
        for i, t in enumerate(self._tasks):
            if task.priority > t.priority:
                self._tasks.insert(i, task)
                return
        
        # 如果没找到合适的位置，追加到末尾
        self._tasks.append(task)

    def _get_next_task(self) -> Optional[TranslationTask]:
        """获取下一个要处理的任务
        
        Returns:
            Optional[TranslationTask]: 下一个任务，如果没有则返回None
        """
        # 检查是否达到最大并发数
        if len(self._processing) >= self.config.max_concurrent:
            return None
        
        # 查找第一个待处理的任务
        for i, task in enumerate(self._tasks):
            if task.status == TaskStatus.PENDING:
                # 从队列中移除任务
                self._tasks.pop(i)
                return task
        
        return None

    def _find_task(self, task_id: str) -> Optional[TranslationTask]:
        """查找任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[TranslationTask]: 找到的任务，如果不存在则返回None
        """
        # 在队列中查找
        for task in self._tasks:
            if task.id == task_id:
                return task
        
        return None

    async def _process_task(self, task: TranslationTask) -> None:
        """处理单个任务
        
        Args:
            task: 要处理的任务
        """
        # 添加到处理集合
        self._processing.add(task.id)
        task.status = TaskStatus.RUNNING
        
        try:
            # 获取信号量
            async with self._semaphore:
                # 调用API进行翻译
                task.result = await self.client.translate(
                    text=task.content,
                    system_prompt=task.system_prompt,
                )
                
                # 更新任务状态
                task.status = TaskStatus.COMPLETED
                
        except Exception as e:
            # 更新错误信息
            task.error = str(e)
            task.status = TaskStatus.FAILED
            log.error(f"Task {task.id} failed: {str(e)}")
            
        finally:
            # 从处理集合中移除
            self._processing.remove(task.id)
            
            # 将任务放回队列（用于结果查询）
            self._tasks.append(task)
            
            # 设置任务完成事件
            event = self._task_events.get(task.id)
            if event:
                event.set()
                
            log.debug(f"Task {task.id} completed with status: {task.status.value}") 
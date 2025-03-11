"""
显示管理模块
"""
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from ..config import DisplayConfig
from ..utils import DisplayError, log


@dataclass
class TaskInfo:
    """任务信息"""
    id: str  # 任务ID
    name: str  # 任务名称
    status: str  # 任务状态
    progress: float  # 进度(0-1)
    start_time: float  # 开始时间戳
    end_time: Optional[float] = None  # 结束时间戳
    error: Optional[str] = None  # 错误信息
    tokens: int = 0  # 使用的token数
    cost: float = 0.0  # 花费


@dataclass
class SessionStats:
    """会话统计"""
    total_files: int = 0  # 总文件数
    completed_files: int = 0  # 完成文件数
    total_tokens: int = 0  # 总token数
    total_cost: float = 0.0  # 总花费
    start_time: float = 0.0  # 开始时间戳
    errors: int = 0  # 错误数


class DisplayManager:
    """显示管理器"""

    def __init__(self, config: DisplayConfig):
        """初始化显示管理器
        
        Args:
            config: 显示配置
        """
        self.config = config
        self.console = Console()
        
        # 创建布局
        self.layout = Layout()
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        
        # 创建进度条
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        )
        
        # 任务信息
        self._tasks: Dict[str, TaskInfo] = {}
        self._current_task: Optional[str] = None
        
        # 会话统计
        self._stats = SessionStats(start_time=time.time())
        
        # 显示控制
        self._live: Optional[Live] = None
        self._is_running = False

    def start(self) -> None:
        """启动显示"""
        if self._is_running:
            return
        
        self._is_running = True
        self._live = Live(
            self.layout,
            console=self.console,
            refresh_per_second=self.config.refresh_rate,
            transient=True,
        )
        self._live.start()
        self._update_display()

    def stop(self) -> None:
        """停止显示"""
        if not self._is_running:
            return
        
        self._is_running = False
        if self._live:
            self._live.stop()
            self._live = None

    def add_task(self, task_id: str, name: str) -> None:
        """添加任务
        
        Args:
            task_id: 任务ID
            name: 任务名称
        """
        if task_id in self._tasks:
            raise DisplayError(f"Task already exists: {task_id}")
        
        self._tasks[task_id] = TaskInfo(
            id=task_id,
            name=name,
            status="等待中",
            progress=0.0,
            start_time=time.time(),
        )
        self._stats.total_files += 1
        self._update_display()

    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        error: Optional[str] = None,
        tokens: Optional[int] = None,
        cost: Optional[float] = None,
    ) -> None:
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 进度
            error: 错误信息
            tokens: token数
            cost: 花费
        """
        task = self._tasks.get(task_id)
        if not task:
            raise DisplayError(f"Task not found: {task_id}")
        
        if status:
            task.status = status
        if progress is not None:
            task.progress = progress
        if error:
            task.error = error
            self._stats.errors += 1
        if tokens:
            task.tokens = tokens
            self._stats.total_tokens += tokens
        if cost:
            task.cost = cost
            self._stats.total_cost += cost
        
        # 如果任务完成，更新统计
        if progress == 1.0 and not task.end_time:
            task.end_time = time.time()
            self._stats.completed_files += 1
        
        self._update_display()

    def set_current_task(self, task_id: Optional[str]) -> None:
        """设置当前任务
        
        Args:
            task_id: 任务ID
        """
        if task_id and task_id not in self._tasks:
            raise DisplayError(f"Task not found: {task_id}")
        
        self._current_task = task_id
        self._update_display()

    def _update_display(self) -> None:
        """更新显示"""
        if not self._is_running or not self._live:
            return
        
        # 更新头部
        self.layout["header"].update(self._render_header())
        
        # 更新主体
        self.layout["body"].update(self._render_body())
        
        # 更新底部
        self.layout["footer"].update(self._render_footer())

    def _render_header(self) -> Panel:
        """渲染头部
        
        Returns:
            Panel: 头部面板
        """
        # 计算运行时间
        elapsed = time.time() - self._stats.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        # 创建统计信息
        stats = Table.grid(padding=(0, 1))
        stats.add_column(style="bold")
        stats.add_column()
        stats.add_row(
            "运行时间:",
            f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        )
        stats.add_row(
            "处理进度:",
            f"{self._stats.completed_files}/{self._stats.total_files}",
        )
        stats.add_row(
            "Token用量:",
            f"{self._stats.total_tokens:,}",
        )
        stats.add_row(
            "花费(USD):",
            f"${self._stats.total_cost:.4f}",
        )
        
        return Panel(stats, title="会话信息", border_style="blue")

    def _render_body(self) -> Panel:
        """渲染主体
        
        Returns:
            Panel: 主体面板
        """
        # 创建任务表格
        table = Table(
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
        )
        table.add_column("任务", style="cyan")
        table.add_column("状态", style="green")
        table.add_column("进度", justify="right")
        table.add_column("Token", justify="right")
        table.add_column("花费(USD)", justify="right")
        table.add_column("用时", justify="right")
        
        # 添加任务行
        for task in self._tasks.values():
            # 计算用时
            duration = (task.end_time or time.time()) - task.start_time
            duration_str = f"{int(duration)}s"
            
            # 设置行样式
            style = None
            if task.id == self._current_task:
                style = "bold"
            elif task.error:
                style = "red"
            
            # 添加行
            table.add_row(
                task.name,
                task.status,
                f"{task.progress:.1%}",
                f"{task.tokens:,}",
                f"${task.cost:.4f}",
                duration_str,
                style=style,
            )
        
        return Panel(table, title="任务队列", border_style="blue")

    def _render_footer(self) -> Panel:
        """渲染底部
        
        Returns:
            Panel: 底部面板
        """
        # 获取当前任务
        if not self._current_task:
            status = Text("空闲中", style="green")
        else:
            task = self._tasks[self._current_task]
            if task.error:
                status = Text(f"错误: {task.error}", style="red")
            else:
                status = Text(
                    f"正在处理: {task.name} ({task.status})",
                    style="yellow",
                )
        
        return Panel(status, title="状态", border_style="blue") 
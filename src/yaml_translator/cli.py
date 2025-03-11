"""
命令行界面模块
"""
import os
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table

from .config import ConfigManager
from .core import (
    BackupManager,
    BlacklistManager,
    ChunkManager,
    DisplayManager,
    FileMatcher,
    PromptManager,
    RetryHandler,
    Translator,
    YAMLHandler,
)
from .utils import log


console = Console()


@click.group()
@click.version_option()
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True, dir_okay=False),
    help="配置文件路径",
)
@click.option("-v", "--verbose", is_flag=True, help="显示详细日志")
@click.option("-q", "--quiet", is_flag=True, help="只显示错误日志")
@click.pass_context
def cli(ctx: click.Context, config: Optional[str], verbose: bool, quiet: bool) -> None:
    """YAML文件翻译工具

    支持批量翻译YAML文件，保持原有格式和注释，支持黑名单词汇保护。
    """
    # 设置日志级别
    if verbose:
        log.set_level("DEBUG")
    elif quiet:
        log.set_level("ERROR")
    else:
        log.set_level("INFO")
    
    # 加载配置
    ctx.ensure_object(dict)
    ctx.obj["config"] = ConfigManager(config_file=config if config else None)


@cli.command()
@click.argument(
    "path",
    type=click.Path(exists=True),
)
@click.option(
    "-p",
    "--pattern",
    multiple=True,
    help="文件匹配模式（可多次指定）",
)
@click.option(
    "-e",
    "--exclude",
    multiple=True,
    help="排除模式（可多次指定）",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="递归处理子目录",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="仅显示要处理的文件，不实际翻译",
)
@click.pass_context
def translate(
    ctx: click.Context,
    path: str,
    pattern: List[str],
    exclude: List[str],
    recursive: bool,
    dry_run: bool,
) -> None:
    """翻译YAML文件

    PATH可以是单个文件或目录。如果是目录，将处理目录下所有匹配的YAML文件。
    """
    config = ctx.obj["config"]
    
    try:
        # 创建文件匹配器
        matcher = FileMatcher(
            patterns=list(pattern) or config.file_matching.include_patterns,
            exclude_patterns=list(exclude) or config.file_matching.exclude_patterns,
            recursive=recursive,
        )
        
        # 查找要处理的文件
        files = matcher.find_files(path)
        if not files:
            console.print("[yellow]未找到匹配的文件[/]")
            return
        
        # 显示要处理的文件
        console.print(f"\n找到 [cyan]{len(files)}[/] 个文件:")
        for file in files:
            console.print(f"  [green]•[/] {file}")
        
        if dry_run:
            return
        
        # 创建必要的组件
        yaml_handler = YAMLHandler(config.yaml)
        chunk_manager = ChunkManager(config.chunk)
        prompt_manager = PromptManager(config.prompt)
        translator = Translator(config.translation)
        retry_handler = RetryHandler(config.retry)
        display = DisplayManager(config.display)
        
        # 启动显示
        display.start()
        
        try:
            # 处理每个文件
            for file_path in files:
                # 添加任务
                task_id = str(file_path)
                display.add_task(task_id, file_path.name)
                display.set_current_task(task_id)
                
                try:
                    # 读取文件
                    content = yaml_handler.read_file(file_path)
                    
                    # 分块处理
                    chunks = chunk_manager.split_content(content)
                    
                    # 翻译每个块
                    translated_chunks = []
                    for i, chunk in enumerate(chunks):
                        # 更新进度
                        progress = (i + 1) / len(chunks)
                        display.update_task(
                            task_id,
                            status=f"翻译中 ({i + 1}/{len(chunks)})",
                            progress=progress,
                        )
                        
                        # 准备提示词
                        prompt = prompt_manager.render_template(
                            "default",
                            {
                                "text": chunk,
                                "context": chunk_manager.get_context(i),
                            },
                        )
                        
                        # 翻译
                        result = translator.translate(prompt)
                        translated_chunks.append(result)
                    
                    # 合并结果
                    final_content = chunk_manager.merge_chunks(translated_chunks)
                    
                    # 保存文件
                    yaml_handler.write_file(file_path, final_content)
                    
                    # 更新任务状态
                    display.update_task(
                        task_id,
                        status="已完成",
                        progress=1.0,
                    )
                    
                except Exception as e:
                    log.error(f"处理文件 {file_path} 时出错: {str(e)}")
                    display.update_task(
                        task_id,
                        status="失败",
                        error=str(e),
                    )
                    
                    # 尝试重试
                    should_retry, wait_time = retry_handler.should_retry(task_id, e)
                    if should_retry:
                        display.update_task(
                            task_id,
                            status=f"等待重试 ({int(wait_time)}s)",
                        )
                        # TODO: 实现重试逻辑
        
        finally:
            # 停止显示
            display.stop()
        
    except Exception as e:
        log.error(f"执行失败: {str(e)}")
        ctx.exit(1)


@cli.command()
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False),
    help="输出配置文件路径",
)
@click.pass_context
def init(ctx: click.Context, output: Optional[str]) -> None:
    """初始化配置文件

    生成默认配置文件，可以指定输出路径。
    """
    try:
        config = ctx.obj["config"]
        
        # 确定输出路径
        if not output:
            output = "config.yaml"
        
        # 导出配置
        config.export_config(output)
        console.print(f"[green]配置文件已生成: {output}[/]")
        
    except Exception as e:
        log.error(f"初始化失败: {str(e)}")
        ctx.exit(1)


@cli.command()
@click.argument("template_name")
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False),
)
@click.pass_context
def add_template(ctx: click.Context, template_name: str, file: str) -> None:
    """添加提示词模板

    从文件添加提示词模板。

    TEMPLATE_NAME: 模板名称
    FILE: 模板文件路径（JSON格式）
    """
    try:
        config = ctx.obj["config"]
        prompt_manager = PromptManager(config.prompt)
        
        # 读取模板文件
        with open(file, "r", encoding="utf-8") as f:
            template_data = json.load(f)
        
        # 添加模板
        template = PromptTemplate(name=template_name, **template_data)
        prompt_manager.add_template(template)
        
        console.print(f"[green]模板已添加: {template_name}[/]")
        
    except Exception as e:
        log.error(f"添加模板失败: {str(e)}")
        ctx.exit(1)


@cli.command()
@click.pass_context
def list_templates(ctx: click.Context) -> None:
    """列出所有提示词模板"""
    try:
        config = ctx.obj["config"]
        prompt_manager = PromptManager(config.prompt)
        
        # 获取所有模板
        templates = prompt_manager.list_templates()
        
        if not templates:
            console.print("[yellow]没有可用的模板[/]")
            return
        
        # 显示模板信息
        console.print("\n可用的模板:")
        for name in templates:
            info = prompt_manager.get_template_info(name)
            console.print(f"\n[cyan]{name}[/]")
            if info["description"]:
                console.print(f"  描述: {info['description']}")
            if info["variables"]:
                console.print("  变量:")
                for var_name, var_desc in info["variables"].items():
                    console.print(f"    [green]•[/] {var_name}: {var_desc}")
        
    except Exception as e:
        log.error(f"列出模板失败: {str(e)}")
        ctx.exit(1)


@cli.group()
def backup() -> None:
    """备份管理命令组"""
    pass


@backup.command()
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False),
)
@click.pass_context
def create(ctx: click.Context, file: str) -> None:
    """创建文件备份
    
    FILE: 要备份的文件路径
    """
    try:
        config = ctx.obj["config"]
        backup_manager = BackupManager(config.backup)
        
        # 创建备份
        backup_path = backup_manager.backup_file(file)
        console.print(f"[green]已创建备份: {backup_path}[/]")
        
    except Exception as e:
        log.error(f"创建备份失败: {str(e)}")
        ctx.exit(1)


@backup.command()
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "-i",
    "--index",
    type=int,
    default=-1,
    help="备份索引，默认使用最新的备份",
)
@click.pass_context
def restore(ctx: click.Context, file: str, index: int) -> None:
    """从备份恢复文件
    
    FILE: 要恢复的文件路径
    """
    try:
        config = ctx.obj["config"]
        backup_manager = BackupManager(config.backup)
        
        # 恢复文件
        backup_manager.restore_file(file, index)
        console.print(f"[green]已恢复文件: {file}[/]")
        
    except Exception as e:
        log.error(f"恢复文件失败: {str(e)}")
        ctx.exit(1)


@backup.command()
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False),
)
@click.pass_context
def list(ctx: click.Context, file: str) -> None:
    """列出文件的所有备份
    
    FILE: 文件路径
    """
    try:
        config = ctx.obj["config"]
        backup_manager = BackupManager(config.backup)
        
        # 获取备份列表
        backups = backup_manager.list_backups(file)
        
        if not backups:
            console.print(f"[yellow]文件 {file} 没有备份[/]")
            return
        
        # 创建表格
        table = Table(
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
        )
        table.add_column("索引", style="cyan", justify="right")
        table.add_column("备份文件", style="green")
        table.add_column("时间", style="yellow")
        table.add_column("大小", justify="right")
        
        # 添加备份信息
        for i, backup in enumerate(backups):
            size = backup["size"]
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f}KB"
            else:
                size_str = f"{size/1024/1024:.1f}MB"
            
            table.add_row(
                str(i),
                Path(backup["path"]).name,
                backup["timestamp"],
                size_str,
            )
        
        console.print(table)
        
    except Exception as e:
        log.error(f"列出备份失败: {str(e)}")
        ctx.exit(1)


@backup.command()
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False),
    required=False,
)
@click.pass_context
def cleanup(ctx: click.Context, file: Optional[str]) -> None:
    """清理备份文件
    
    FILE: 要清理的文件路径，如果不指定则清理所有备份
    """
    try:
        config = ctx.obj["config"]
        backup_manager = BackupManager(config.backup)
        
        # 清理备份
        backup_manager.cleanup(file)
        if file:
            console.print(f"[green]已清理文件 {file} 的备份[/]")
        else:
            console.print("[green]已清理所有备份[/]")
        
    except Exception as e:
        log.error(f"清理备份失败: {str(e)}")
        ctx.exit(1)


@cli.group()
def blacklist() -> None:
    """黑名单管理命令组"""
    pass


@blacklist.command()
@click.argument("word")
@click.pass_context
def add_word(ctx: click.Context, word: str) -> None:
    """添加黑名单词汇
    
    WORD: 要添加的词汇
    """
    try:
        config = ctx.obj["config"]
        blacklist_manager = BlacklistManager(config.blacklist)
        
        # 添加词汇
        blacklist_manager.add_word(word)
        console.print(f"[green]已添加黑名单词汇: {word}[/]")
        
        # 导出更新后的黑名单
        if config.blacklist.blacklist_file:
            blacklist_manager.export_blacklist(config.blacklist.blacklist_file)
        
    except Exception as e:
        log.error(f"添加黑名单词汇失败: {str(e)}")
        ctx.exit(1)


@blacklist.command()
@click.argument("pattern")
@click.pass_context
def add_pattern(ctx: click.Context, pattern: str) -> None:
    """添加黑名单正则表达式
    
    PATTERN: 正则表达式
    """
    try:
        config = ctx.obj["config"]
        blacklist_manager = BlacklistManager(config.blacklist)
        
        # 添加正则
        blacklist_manager.add_pattern(pattern)
        console.print(f"[green]已添加黑名单正则: {pattern}[/]")
        
        # 导出更新后的黑名单
        if config.blacklist.blacklist_file:
            blacklist_manager.export_blacklist(config.blacklist.blacklist_file)
        
    except Exception as e:
        log.error(f"添加黑名单正则失败: {str(e)}")
        ctx.exit(1)


@blacklist.command()
@click.argument("word")
@click.pass_context
def remove_word(ctx: click.Context, word: str) -> None:
    """移除黑名单词汇
    
    WORD: 要移除的词汇
    """
    try:
        config = ctx.obj["config"]
        blacklist_manager = BlacklistManager(config.blacklist)
        
        # 移除词汇
        blacklist_manager.remove_word(word)
        console.print(f"[green]已移除黑名单词汇: {word}[/]")
        
        # 导出更新后的黑名单
        if config.blacklist.blacklist_file:
            blacklist_manager.export_blacklist(config.blacklist.blacklist_file)
        
    except Exception as e:
        log.error(f"移除黑名单词汇失败: {str(e)}")
        ctx.exit(1)


@blacklist.command()
@click.argument("pattern")
@click.pass_context
def remove_pattern(ctx: click.Context, pattern: str) -> None:
    """移除黑名单正则表达式
    
    PATTERN: 正则表达式
    """
    try:
        config = ctx.obj["config"]
        blacklist_manager = BlacklistManager(config.blacklist)
        
        # 移除正则
        blacklist_manager.remove_pattern(pattern)
        console.print(f"[green]已移除黑名单正则: {pattern}[/]")
        
        # 导出更新后的黑名单
        if config.blacklist.blacklist_file:
            blacklist_manager.export_blacklist(config.blacklist.blacklist_file)
        
    except Exception as e:
        log.error(f"移除黑名单正则失败: {str(e)}")
        ctx.exit(1)


@blacklist.command()
@click.pass_context
def list(ctx: click.Context) -> None:
    """列出所有黑名单内容"""
    try:
        config = ctx.obj["config"]
        blacklist_manager = BlacklistManager(config.blacklist)
        
        # 创建表格
        table = Table(
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
        )
        table.add_column("类型", style="cyan")
        table.add_column("内容", style="green")
        
        # 添加词汇
        for word in sorted(blacklist_manager._words):
            table.add_row("词汇", word)
        
        # 添加正则
        for pattern in sorted(p.pattern for p in blacklist_manager._patterns):
            table.add_row("正则", pattern)
        
        # 显示配置信息
        console.print("\n黑名单配置:")
        console.print(f"  大小写敏感: {'是' if blacklist_manager._case_sensitive else '否'}")
        if config.blacklist.blacklist_file:
            console.print(f"  配置文件: {config.blacklist.blacklist_file}")
        
        # 显示黑名单内容
        if table.row_count > 0:
            console.print("\n黑名单内容:")
            console.print(table)
        else:
            console.print("\n[yellow]黑名单为空[/]")
        
    except Exception as e:
        log.error(f"列出黑名单失败: {str(e)}")
        ctx.exit(1)


@blacklist.command()
@click.argument(
    "file",
    type=click.Path(dir_okay=False),
)
@click.pass_context
def export(ctx: click.Context, file: str) -> None:
    """导出黑名单到文件
    
    FILE: 导出文件路径
    """
    try:
        config = ctx.obj["config"]
        blacklist_manager = BlacklistManager(config.blacklist)
        
        # 导出黑名单
        blacklist_manager.export_blacklist(file)
        console.print(f"[green]已导出黑名单到: {file}[/]")
        
    except Exception as e:
        log.error(f"导出黑名单失败: {str(e)}")
        ctx.exit(1)


@blacklist.command()
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False),
)
@click.pass_context
def load(ctx: click.Context, file: str) -> None:
    """从文件加载黑名单
    
    FILE: 黑名单文件路径
    """
    try:
        config = ctx.obj["config"]
        blacklist_manager = BlacklistManager(config.blacklist)
        
        # 加载黑名单
        blacklist_manager.load_blacklist_file(file)
        console.print(f"[green]已从 {file} 加载黑名单[/]")
        
        # 如果配置了黑名单文件，同时更新它
        if config.blacklist.blacklist_file:
            blacklist_manager.export_blacklist(config.blacklist.blacklist_file)
        
    except Exception as e:
        log.error(f"加载黑名单失败: {str(e)}")
        ctx.exit(1)


if __name__ == "__main__":
    cli() 
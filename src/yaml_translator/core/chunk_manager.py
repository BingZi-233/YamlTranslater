"""
分块管理模块
"""
import re
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Tuple, Union

from pydantic import BaseModel

from ..config import TranslationConfig, ChunkConfig
from ..utils import ChunkError, log


@dataclass
class ChunkInfo:
    """分块信息"""
    index: int  # 块索引
    start_line: int  # 起始行号（从1开始）
    end_line: int  # 结束行号（包含）
    content: str  # 块内容
    context: Optional[str] = None  # 上下文信息
    level: int = 0  # 缩进级别
    is_complete: bool = True  # 是否完整块


class ChunkResult(BaseModel):
    """分块处理结果"""
    index: int
    content: str
    success: bool
    error: Optional[str] = None


class ChunkManager:
    """分块管理器"""

    def __init__(self, config: TranslationConfig):
        """初始化分块管理器
        
        Args:
            config: 翻译配置
        """
        self.config = config
        self._chunk_size = config.chunk_size
        self._context_lines = 2  # 每个块保留的上下文行数
        self._chunks: List[ChunkInfo] = []
        self._context_cache: Dict[int, str] = {}

    def split_text(self, text: str) -> List[ChunkInfo]:
        """将文本分块
        
        Args:
            text: 要分块的文本
            
        Returns:
            List[ChunkInfo]: 分块信息列表
            
        Raises:
            ChunkError: 分块错误
        """
        try:
            # 按行分割文本
            lines = text.splitlines()
            total_lines = len(lines)
            
            # 如果总行数小于块大小，直接返回一个块
            if total_lines <= self._chunk_size:
                return [
                    ChunkInfo(
                        index=0,
                        start_line=1,
                        end_line=total_lines,
                        content=text,
                    )
                ]
            
            chunks: List[ChunkInfo] = []
            current_index = 0
            current_line = 0
            
            while current_line < total_lines:
                # 计算当前块的范围
                chunk_start = current_line
                chunk_end = min(chunk_start + self._chunk_size, total_lines)
                
                # 调整块的边界到合适的分割点
                chunk_end = self._find_chunk_boundary(lines, chunk_end)
                
                # 提取块内容
                chunk_content = "\n".join(lines[chunk_start:chunk_end])
                
                # 获取上下文
                context = self._get_context(lines, chunk_start, chunk_end, total_lines)
                
                # 创建分块信息
                chunk = ChunkInfo(
                    index=current_index,
                    start_line=chunk_start + 1,  # 转换为1-based行号
                    end_line=chunk_end,
                    content=chunk_content,
                    context=context,
                )
                chunks.append(chunk)
                
                # 更新索引和行号
                current_index += 1
                current_line = chunk_end
            
            return chunks
            
        except Exception as e:
            log.error(f"Failed to split text: {str(e)}")
            raise ChunkError("Failed to split text", details=str(e))

    def merge_results(
        self,
        original_text: str,
        results: List[ChunkResult],
        chunks: List[ChunkInfo],
    ) -> str:
        """合并处理结果
        
        Args:
            original_text: 原始文本
            results: 块处理结果列表
            chunks: 原始分块信息列表
            
        Returns:
            str: 合并后的文本
            
        Raises:
            ChunkError: 合并错误
        """
        try:
            # 验证结果完整性
            if len(results) != len(chunks):
                raise ChunkError(
                    "Results count does not match chunks count",
                    details=f"Results: {len(results)}, Chunks: {len(chunks)}",
                )
            
            # 按索引排序结果
            sorted_results = sorted(results, key=lambda x: x.index)
            sorted_chunks = sorted(chunks, key=lambda x: x.index)
            
            # 检查是否所有块都处理成功
            failed_chunks = [r for r in sorted_results if not r.success]
            if failed_chunks:
                chunk_errors = "\n".join(f"Chunk {r.index}: {r.error}" for r in failed_chunks)
                raise ChunkError("Some chunks failed to process", details=chunk_errors)
            
            # 合并结果
            lines = original_text.splitlines()
            for result, chunk in zip(sorted_results, sorted_chunks):
                # 将结果内容按行分割
                result_lines = result.content.splitlines()
                
                # 替换原文中对应的行
                start_idx = chunk.start_line - 1  # 转换为0-based索引
                end_idx = chunk.end_line
                lines[start_idx:end_idx] = result_lines
            
            return "\n".join(lines)
            
        except ChunkError:
            raise
        except Exception as e:
            log.error(f"Failed to merge results: {str(e)}")
            raise ChunkError("Failed to merge results", details=str(e))

    def _find_chunk_boundary(self, lines: List[str], end: int) -> int:
        """查找合适的块边界
        
        Args:
            lines: 文本行列表
            end: 当前的结束位置
            
        Returns:
            int: 调整后的结束位置
        """
        # 如果已经到达文件末尾，直接返回
        if end >= len(lines):
            return end
            
        # 向后查找，直到找到一个合适的分割点（空行或缩进减少的行）
        max_look_ahead = 10  # 最大向后查找行数
        for i in range(end, min(end + max_look_ahead, len(lines))):
            current_line = lines[i]
            
            # 如果是空行，可以作为分割点
            if not current_line.strip():
                return i + 1
            
            # 如果缩进减少，可以作为分割点
            if i > 0 and self._get_indent_level(current_line) < self._get_indent_level(lines[i - 1]):
                return i
        
        # 如果没找到合适的分割点，就使用原始位置
        return end

    def _get_indent_level(self, line: str) -> int:
        """获取行的缩进级别
        
        Args:
            line: 文本行
            
        Returns:
            int: 缩进空格数
        """
        return len(line) - len(line.lstrip())

    def _get_context(
        self,
        lines: List[str],
        start: int,
        end: int,
        total_lines: int,
    ) -> Optional[str]:
        """获取块的上下文
        
        Args:
            lines: 文本行列表
            start: 块的起始位置
            end: 块的结束位置
            total_lines: 总行数
            
        Returns:
            Optional[str]: 上下文信息，如果不需要则返回None
        """
        context_lines = []
        
        # 添加前置上下文
        if start > 0:
            context_start = max(0, start - self._context_lines)
            context_lines.extend(lines[context_start:start])
        
        # 添加后置上下文
        if end < total_lines:
            context_end = min(total_lines, end + self._context_lines)
            context_lines.extend(lines[end:context_end])
        
        return "\n".join(context_lines) if context_lines else None

    def estimate_chunks(self, text: str) -> Tuple[int, int]:
        """估算文本的分块数量和每块的大致大小
        
        Args:
            text: 要分析的文本
            
        Returns:
            Tuple[int, int]: (预计分块数, 每块的大致行数)
        """
        lines = text.splitlines()
        total_lines = len(lines)
        
        if total_lines <= self._chunk_size:
            return 1, total_lines
            
        # 估算分块数（考虑到边界调整可能会略有不同）
        estimated_chunks = (total_lines + self._chunk_size - 1) // self._chunk_size
        avg_chunk_size = total_lines // estimated_chunks
        
        return estimated_chunks, avg_chunk_size

    def validate_chunk_size(self, size: int) -> bool:
        """验证块大小是否合理
        
        Args:
            size: 要验证的块大小
            
        Returns:
            bool: 是否合理
        """
        # 块大小应该在合理范围内（例如：10-5000行）
        return 10 <= size <= 5000

    def split_content(self, content: str) -> List[str]:
        """分割内容为多个块
        
        Args:
            content: 要分割的内容
            
        Returns:
            List[str]: 分块列表
            
        Raises:
            ChunkError: 分块失败
        """
        try:
            # 清除缓存
            self._chunks.clear()
            self._context_cache.clear()
            
            # 按行分割
            lines = content.splitlines()
            
            # 分析结构
            structure = self._analyze_structure(lines)
            
            # 智能分块
            chunks = self._smart_split(lines, structure)
            
            # 优化块边界
            chunks = self._optimize_boundaries(chunks)
            
            # 添加上下文
            chunks = self._add_context(chunks)
            
            # 返回块内容
            return [chunk.content for chunk in chunks]
            
        except Exception as e:
            log.error(f"分块失败: {str(e)}")
            raise ChunkError(f"分块失败: {str(e)}")

    def merge_chunks(self, chunks: List[str]) -> str:
        """合并多个块
        
        Args:
            chunks: 要合并的块列表
            
        Returns:
            str: 合并后的内容
            
        Raises:
            ChunkError: 合并失败
        """
        try:
            if not chunks:
                return ""
            
            # 验证块数量
            if len(chunks) != len(self._chunks):
                raise ChunkError("块数量不匹配")
            
            # 按行号重建内容
            result_lines = []
            current_line = 0
            
            for chunk, info in zip(chunks, self._chunks):
                # 添加缺失的行
                if info.start_line > current_line:
                    result_lines.extend([""] * (info.start_line - current_line))
                
                # 添加块内容
                chunk_lines = chunk.splitlines()
                result_lines.extend(chunk_lines)
                current_line = info.end_line
            
            return "\n".join(result_lines)
            
        except Exception as e:
            log.error(f"合并块失败: {str(e)}")
            raise ChunkError(f"合并块失败: {str(e)}")

    def get_context(self, chunk_index: int) -> Optional[str]:
        """获取块的上下文信息
        
        Args:
            chunk_index: 块索引
            
        Returns:
            Optional[str]: 上下文信息
        """
        return self._context_cache.get(chunk_index)

    def _analyze_structure(self, lines: List[str]) -> List[Tuple[int, int]]:
        """分析内容结构
        
        Args:
            lines: 内容行列表
            
        Returns:
            List[Tuple[int, int]]: 结构信息列表，每项为(行号, 缩进级别)
        """
        structure = []
        current_level = 0
        level_stack = []
        
        for i, line in enumerate(lines):
            # 计算缩进级别
            indent = len(line) - len(line.lstrip())
            level = indent // 2  # 假设使用2个空格作为缩进
            
            # 跳过空行
            if not line.strip():
                continue
            
            # 处理缩进变化
            if level > current_level:
                level_stack.append(current_level)
                current_level = level
            elif level < current_level:
                while level_stack and level <= level_stack[-1]:
                    current_level = level_stack.pop()
            
            structure.append((i, level))
        
        return structure

    def _smart_split(
        self,
        lines: List[str],
        structure: List[Tuple[int, int]],
    ) -> List[ChunkInfo]:
        """智能分块
        
        Args:
            lines: 内容行列表
            structure: 结构信息列表
            
        Returns:
            List[ChunkInfo]: 分块信息列表
        """
        chunks = []
        current_chunk = []
        current_start = 0
        current_level = 0
        chunk_size = 0
        
        for i, (line_num, level) in enumerate(structure):
            line = lines[line_num]
            line_size = len(line)
            
            # 检查是否需要分块
            need_split = False
            
            # 大小超限
            if chunk_size + line_size > self.config.max_chunk_size:
                need_split = True
            
            # 缩进级别变化
            if level < current_level:
                need_split = True
            
            # 关键字触发
            if any(kw in line for kw in self.config.split_keywords):
                need_split = True
            
            # 创建新块
            if need_split and current_chunk:
                chunk_content = "\n".join(current_chunk)
                chunks.append(ChunkInfo(
                    index=i,
                    start_line=current_start,
                    end_line=line_num,
                    content=chunk_content,
                    level=current_level,
                ))
                
                current_chunk = []
                current_start = line_num
                chunk_size = 0
            
            # 添加当前行
            current_chunk.append(line)
            chunk_size += line_size
            current_level = level
        
        # 添加最后一个块
        if current_chunk:
            chunk_content = "\n".join(current_chunk)
            chunks.append(ChunkInfo(
                index=len(structure),
                start_line=current_start,
                end_line=len(lines),
                content=chunk_content,
                level=current_level,
            ))
        
        return chunks

    def _optimize_boundaries(self, chunks: List[ChunkInfo]) -> List[ChunkInfo]:
        """优化块边界
        
        Args:
            chunks: 分块信息列表
            
        Returns:
            List[ChunkInfo]: 优化后的分块信息列表
        """
        if not chunks:
            return chunks
        
        optimized = []
        
        for i, chunk in enumerate(chunks):
            # 检查是否需要合并
            if i > 0 and self._should_merge(optimized[-1], chunk):
                # 合并块
                prev = optimized[-1]
                merged = ChunkInfo(
                    index=i,
                    start_line=prev.start_line,
                    end_line=chunk.end_line,
                    content=prev.content + "\n" + chunk.content,
                    level=min(prev.level, chunk.level),
                )
                optimized[-1] = merged
            else:
                optimized.append(chunk)
        
        return optimized

    def _should_merge(self, chunk1: ChunkInfo, chunk2: ChunkInfo) -> bool:
        """检查是否应该合并两个块
        
        Args:
            chunk1: 第一个块
            chunk2: 第二个块
            
        Returns:
            bool: 是否应该合并
        """
        # 检查大小限制
        total_size = len(chunk1.content) + len(chunk2.content) + 1
        if total_size > self.config.max_chunk_size:
            return False
        
        # 检查缩进级别
        if abs(chunk1.level - chunk2.level) > 1:
            return False
        
        # 检查是否有完整性标记
        if not chunk1.is_complete or not chunk2.is_complete:
            return True
        
        return False

    def _add_context(self, chunks: List[ChunkInfo]) -> List[ChunkInfo]:
        """添加上下文信息
        
        Args:
            chunks: 分块信息列表
            
        Returns:
            List[ChunkInfo]: 添加上下文后的分块信息列表
        """
        if not chunks:
            return chunks
        
        # 清除上下文缓存
        self._context_cache.clear()
        
        # 为每个块添加上下文
        for i, chunk in enumerate(chunks):
            context_lines = []
            
            # 添加前文上下文
            if i > 0:
                prev_chunk = chunks[i - 1]
                context_lines.append(f"前文：\n{prev_chunk.content}")
            
            # 添加后文上下文
            if i < len(chunks) - 1:
                next_chunk = chunks[i + 1]
                context_lines.append(f"后文：\n{next_chunk.content}")
            
            # 设置上下文
            if context_lines:
                context = "\n\n".join(context_lines)
                chunk.context = context
                self._context_cache[i] = context
        
        # 保存块信息
        self._chunks = chunks
        
        return chunks 
"""
文件匹配模块
"""
import os
from pathlib import Path
from typing import Generator, List, Optional, Set, Union

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from ..config import FileMatchingConfig
from ..utils import FileError, log
from .yaml_handler import YAMLHandler


class FileMatcher:
    """文件匹配器"""

    def __init__(self, config: FileMatchingConfig, yaml_handler: YAMLHandler):
        """初始化文件匹配器
        
        Args:
            config: 文件匹配配置
            yaml_handler: YAML处理器实例
        """
        self.config = config
        self.yaml_handler = yaml_handler
        
        # 创建PathSpec对象用于文件匹配
        self._include_spec = PathSpec.from_lines(GitWildMatchPattern, config.include_patterns)
        self._exclude_spec = PathSpec.from_lines(GitWildMatchPattern, config.exclude_patterns)
        
        # 转换排除目录为集合，提高查找效率
        self._exclude_dirs = set(config.exclude_dirs)

    def find_yaml_files(self, path: Union[str, Path], recursive: bool = True) -> Generator[Path, None, None]:
        """查找YAML文件
        
        Args:
            path: 要搜索的路径
            recursive: 是否递归搜索子目录
            
        Yields:
            Path: 匹配的YAML文件路径
            
        Raises:
            FileError: 路径不存在或无法访问
        """
        try:
            root_path = Path(path).resolve()
            if not root_path.exists():
                raise FileError(f"Path does not exist: {path}")

            if root_path.is_file():
                if self._is_valid_file(root_path):
                    yield root_path
                return

            # 遍历目录
            for current_path, dirs, files in os.walk(root_path):
                # 从dirs列表中移除被排除的目录，这样os.walk就不会进入这些目录
                dirs[:] = [d for d in dirs if d not in self._exclude_dirs]
                
                # 如果不递归，清空dirs列表
                if not recursive:
                    dirs.clear()
                
                current = Path(current_path)
                
                # 检查并生成匹配的文件
                for file in files:
                    file_path = current / file
                    if self._is_valid_file(file_path):
                        yield file_path

        except Exception as e:
            log.error(f"Error while finding YAML files in {path}: {str(e)}")
            raise FileError(f"Error while finding YAML files in {path}", details=str(e))

    def _is_valid_file(self, file_path: Path) -> bool:
        """检查文件是否是有效的YAML文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否是有效的YAML文件
        """
        try:
            # 获取相对路径用于模式匹配
            rel_path = str(file_path.relative_to(file_path.parent))
            
            # 检查文件是否满足所有条件：
            # 1. 是YAML文件（通过yaml_handler检查）
            # 2. 匹配包含模式
            # 3. 不匹配排除模式
            # 4. 父目录不在排除列表中
            return (
                self.yaml_handler.is_yaml_file(file_path) and
                self._include_spec.match_file(rel_path) and
                not self._exclude_spec.match_file(rel_path) and
                not any(part in self._exclude_dirs for part in file_path.parts)
            )
            
        except Exception as e:
            log.warning(f"Error checking file {file_path}: {str(e)}")
            return False

    def filter_files(self, files: List[Union[str, Path]]) -> List[Path]:
        """过滤文件列表，只保留匹配的YAML文件
        
        Args:
            files: 要过滤的文件路径列表
            
        Returns:
            List[Path]: 匹配的YAML文件路径列表
        """
        result = []
        for file in files:
            path = Path(file)
            if self._is_valid_file(path):
                result.append(path)
        return result

    def get_excluded_patterns(self) -> Set[str]:
        """获取排除模式集合
        
        Returns:
            Set[str]: 排除模式集合
        """
        return set(self.config.exclude_patterns)

    def get_included_patterns(self) -> Set[str]:
        """获取包含模式集合
        
        Returns:
            Set[str]: 包含模式集合
        """
        return set(self.config.include_patterns)

    def is_excluded_dir(self, dir_name: str) -> bool:
        """检查目录是否被排除
        
        Args:
            dir_name: 目录名
            
        Returns:
            bool: 是否被排除
        """
        return dir_name in self._exclude_dirs 
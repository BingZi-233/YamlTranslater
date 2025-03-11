"""
黑名单管理模块
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Set, Union

from ..config import BlacklistConfig
from ..utils import BlacklistError, log


class BlacklistManager:
    """黑名单管理器"""

    def __init__(self, config: BlacklistConfig):
        """初始化黑名单管理器
        
        Args:
            config: 黑名单配置
        """
        self.config = config
        self._words: Set[str] = set()
        self._patterns: List[Pattern] = []
        self._case_sensitive = config.case_sensitive
        
        # 加载内置黑名单
        self._load_builtin_blacklist()
        
        # 加载自定义黑名单
        if config.blacklist_file:
            self.load_blacklist_file(config.blacklist_file)

    def add_word(self, word: str) -> None:
        """添加黑名单词汇
        
        Args:
            word: 要添加的词汇
            
        Raises:
            BlacklistError: 添加失败
        """
        if not word:
            raise BlacklistError("词汇不能为空")
        
        if not self._case_sensitive:
            word = word.lower()
        
        self._words.add(word)
        log.debug(f"添加黑名单词汇: {word}")

    def add_pattern(self, pattern: str) -> None:
        """添加黑名单正则表达式
        
        Args:
            pattern: 正则表达式
            
        Raises:
            BlacklistError: 添加失败
        """
        try:
            if not pattern:
                raise BlacklistError("正则表达式不能为空")
            
            # 编译正则表达式
            flags = 0 if self._case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
            
            self._patterns.append(regex)
            log.debug(f"添加黑名单正则: {pattern}")
            
        except re.error as e:
            raise BlacklistError(f"无效的正则表达式: {str(e)}")

    def remove_word(self, word: str) -> None:
        """移除黑名单词汇
        
        Args:
            word: 要移除的词汇
            
        Raises:
            BlacklistError: 移除失败
        """
        if not self._case_sensitive:
            word = word.lower()
        
        try:
            self._words.remove(word)
            log.debug(f"移除黑名单词汇: {word}")
        except KeyError:
            raise BlacklistError(f"词汇不存在: {word}")

    def remove_pattern(self, pattern: str) -> None:
        """移除黑名单正则表达式
        
        Args:
            pattern: 正则表达式
            
        Raises:
            BlacklistError: 移除失败
        """
        flags = 0 if self._case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
            self._patterns = [p for p in self._patterns if p.pattern != regex.pattern]
            log.debug(f"移除黑名单正则: {pattern}")
        except re.error:
            raise BlacklistError(f"无效的正则表达式: {pattern}")

    def is_protected(self, text: str) -> bool:
        """检查文本是否包含黑名单内容
        
        Args:
            text: 要检查的文本
            
        Returns:
            bool: 是否包含黑名单内容
        """
        # 检查词汇
        check_text = text if self._case_sensitive else text.lower()
        if any(word in check_text for word in self._words):
            return True
        
        # 检查正则
        return any(pattern.search(text) for pattern in self._patterns)

    def get_matches(self, text: str) -> Dict[str, List[str]]:
        """获取文本中的黑名单匹配
        
        Args:
            text: 要检查的文本
            
        Returns:
            Dict[str, List[str]]: 匹配结果，格式为 {"words": [...], "patterns": [...]}
        """
        result = {
            "words": [],
            "patterns": [],
        }
        
        # 检查词汇
        check_text = text if self._case_sensitive else text.lower()
        for word in self._words:
            if word in check_text:
                result["words"].append(word)
        
        # 检查正则
        for pattern in self._patterns:
            matches = pattern.findall(text)
            if matches:
                result["patterns"].extend(matches)
        
        return result

    def export_blacklist(self, file_path: Union[str, Path]) -> None:
        """导出黑名单
        
        Args:
            file_path: 导出文件路径
            
        Raises:
            BlacklistError: 导出失败
        """
        try:
            data = {
                "case_sensitive": self._case_sensitive,
                "words": list(self._words),
                "patterns": [p.pattern for p in self._patterns],
            }
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            log.debug(f"已导出黑名单到: {file_path}")
            
        except Exception as e:
            log.error(f"导出黑名单失败: {str(e)}")
            raise BlacklistError(f"导出失败: {str(e)}")

    def load_blacklist_file(self, file_path: Union[str, Path]) -> None:
        """从文件加载黑名单
        
        Args:
            file_path: 黑名单文件路径
            
        Raises:
            BlacklistError: 加载失败
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 清除现有黑名单
            self._words.clear()
            self._patterns.clear()
            
            # 设置大小写敏感
            self._case_sensitive = data.get("case_sensitive", self.config.case_sensitive)
            
            # 加载词汇
            for word in data.get("words", []):
                self.add_word(word)
            
            # 加载正则
            for pattern in data.get("patterns", []):
                self.add_pattern(pattern)
            
            log.debug(f"已从 {file_path} 加载黑名单")
            
        except Exception as e:
            log.error(f"加载黑名单失败: {str(e)}")
            raise BlacklistError(f"加载失败: {str(e)}")

    def _load_builtin_blacklist(self) -> None:
        """加载内置黑名单"""
        try:
            # 加载内置词汇
            for word in self.config.words:
                self.add_word(word)
            
            # 加载内置正则
            for pattern in self.config.patterns:
                self.add_pattern(pattern)
            
            log.debug("已加载内置黑名单")
            
        except Exception as e:
            log.error(f"加载内置黑名单失败: {str(e)}")
            raise BlacklistError(f"加载内置黑名单失败: {str(e)}") 
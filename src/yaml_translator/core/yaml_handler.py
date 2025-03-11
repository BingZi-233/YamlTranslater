"""
YAML文件处理模块
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pkvpm
from deepdiff import DeepDiff

from ..config import FileMatchingConfig
from ..utils import YAMLError, log
from ..utils.exceptions import BackupError


class YAMLHandler:
    """YAML文件处理器"""

    def __init__(self, config: FileMatchingConfig):
        """初始化YAML处理器
        
        Args:
            config: 文件匹配配置
        """
        self.config = config
        self._backup_suffix = ".bak"

    def read_file(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """读取YAML文件
        
        Args:
            file_path: YAML文件路径
            
        Returns:
            List[Dict[str, Any]]: YAML文档列表，每个文档是一个字典
            
        Raises:
            YAMLError: YAML解析错误
            FileNotFoundError: 文件不存在
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            log.debug(f"Reading YAML file: {file_path}")
            with path.open("r", encoding="utf-8") as f:
                # 使用pkvpm加载YAML，保持注释和格式
                documents = list(pkvpm.load_all(f))
                log.debug(f"Successfully read {len(documents)} YAML documents from {file_path}")
                return documents

        except pkvpm.YAMLError as e:
            log.error(f"Failed to parse YAML file {file_path}: {str(e)}")
            raise YAMLError(f"Failed to parse YAML file {file_path}", details=str(e))
        except Exception as e:
            log.error(f"Error reading file {file_path}: {str(e)}")
            raise YAMLError(f"Error reading file {file_path}", details=str(e))

    def write_file(self, file_path: Union[str, Path], documents: List[Dict[str, Any]], backup: bool = True) -> None:
        """写入YAML文件
        
        Args:
            file_path: YAML文件路径
            documents: YAML文档列表
            backup: 是否备份原文件
            
        Raises:
            YAMLError: YAML写入错误
            BackupError: 备份失败
        """
        path = Path(file_path)
        
        try:
            # 如果需要备份且文件存在
            if backup and path.exists():
                self._backup_file(path)

            log.debug(f"Writing YAML file: {file_path}")
            with path.open("w", encoding="utf-8") as f:
                # 使用pkvpm保存YAML，保持注释和格式
                pkvpm.dump_all(documents, f)
            log.debug(f"Successfully wrote {len(documents)} YAML documents to {file_path}")

        except Exception as e:
            log.error(f"Error writing file {file_path}: {str(e)}")
            raise YAMLError(f"Error writing file {file_path}", details=str(e))

    def update_file(self, file_path: Union[str, Path], updates: Dict[str, Any], backup: bool = True) -> None:
        """更新YAML文件中的值
        
        Args:
            file_path: YAML文件路径
            updates: 要更新的键值对
            backup: 是否备份原文件
            
        Raises:
            YAMLError: YAML处理错误
            BackupError: 备份失败
        """
        try:
            # 读取原文件
            documents = self.read_file(file_path)
            
            # 更新每个文档
            for doc in documents:
                self._update_dict(doc, updates)
            
            # 写回文件
            self.write_file(file_path, documents, backup)
            
        except Exception as e:
            log.error(f"Error updating file {file_path}: {str(e)}")
            raise YAMLError(f"Error updating file {file_path}", details=str(e))

    def get_document(self, file_path: Union[str, Path], index: int = 0) -> Dict[str, Any]:
        """获取指定索引的YAML文档
        
        Args:
            file_path: YAML文件路径
            index: 文档索引（从0开始）
            
        Returns:
            Dict[str, Any]: YAML文档
            
        Raises:
            YAMLError: YAML处理错误
            IndexError: 索引超出范围
        """
        try:
            documents = self.read_file(file_path)
            if not 0 <= index < len(documents):
                raise IndexError(f"Document index {index} out of range")
            return documents[index]
        except IndexError as e:
            log.error(f"Invalid document index for {file_path}: {str(e)}")
            raise YAMLError(f"Invalid document index for {file_path}", details=str(e))
        except Exception as e:
            log.error(f"Error getting document from {file_path}: {str(e)}")
            raise YAMLError(f"Error getting document from {file_path}", details=str(e))

    def get_value(self, file_path: Union[str, Path], path: str, doc_index: int = 0) -> Any:
        """获取YAML文档中指定路径的值
        
        Args:
            file_path: YAML文件路径
            path: 值的路径（使用点号分隔，如 'a.b.c'）
            doc_index: 文档索引（从0开始）
            
        Returns:
            Any: 路径对应的值
            
        Raises:
            YAMLError: YAML处理错误
            KeyError: 路径不存在
        """
        try:
            document = self.get_document(file_path, doc_index)
            return self._get_value_by_path(document, path)
        except Exception as e:
            log.error(f"Error getting value from {file_path}: {str(e)}")
            raise YAMLError(f"Error getting value from {file_path}", details=str(e))

    def set_value(
        self,
        file_path: Union[str, Path],
        path: str,
        value: Any,
        doc_index: int = 0,
        backup: bool = True,
    ) -> None:
        """设置YAML文档中指定路径的值
        
        Args:
            file_path: YAML文件路径
            path: 值的路径（使用点号分隔，如 'a.b.c'）
            value: 要设置的值
            doc_index: 文档索引（从0开始）
            backup: 是否备份原文件
            
        Raises:
            YAMLError: YAML处理错误
        """
        try:
            documents = self.read_file(file_path)
            if not 0 <= doc_index < len(documents):
                raise IndexError(f"Document index {doc_index} out of range")
            
            # 更新指定路径的值
            self._set_value_by_path(documents[doc_index], path, value)
            
            # 写回文件
            self.write_file(file_path, documents, backup)
            
        except Exception as e:
            log.error(f"Error setting value in {file_path}: {str(e)}")
            raise YAMLError(f"Error setting value in {file_path}", details=str(e))

    def compare_files(self, file1: Union[str, Path], file2: Union[str, Path]) -> Dict[str, Any]:
        """比较两个YAML文件的差异
        
        Args:
            file1: 第一个文件路径
            file2: 第二个文件路径
            
        Returns:
            Dict[str, Any]: 差异信息
            
        Raises:
            YAMLError: YAML处理错误
        """
        try:
            # 读取两个文件
            docs1 = self.read_file(file1)
            docs2 = self.read_file(file2)
            
            # 比较文档数量
            if len(docs1) != len(docs2):
                return {
                    "document_count_diff": {
                        "file1": len(docs1),
                        "file2": len(docs2),
                    }
                }
            
            # 比较每个文档
            differences = {}
            for i, (doc1, doc2) in enumerate(zip(docs1, docs2)):
                diff = DeepDiff(doc1, doc2, ignore_order=True)
                if diff:
                    differences[f"document_{i}"] = diff
            
            return differences
            
        except Exception as e:
            log.error(f"Error comparing files {file1} and {file2}: {str(e)}")
            raise YAMLError(f"Error comparing files", details=str(e))

    def validate_structure(
        self,
        file_path: Union[str, Path],
        schema: Dict[str, Any],
        doc_index: int = 0,
    ) -> Tuple[bool, Optional[str]]:
        """验证YAML文档的结构
        
        Args:
            file_path: YAML文件路径
            schema: 结构模式
            doc_index: 文档索引（从0开始）
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        try:
            document = self.get_document(file_path, doc_index)
            return self._validate_dict_structure(document, schema)
        except Exception as e:
            log.error(f"Error validating structure of {file_path}: {str(e)}")
            return False, str(e)

    def merge_documents(
        self,
        file_path: Union[str, Path],
        target_index: int = 0,
        source_indices: Optional[List[int]] = None,
    ) -> None:
        """合并多个YAML文档
        
        Args:
            file_path: YAML文件路径
            target_index: 目标文档索引
            source_indices: 要合并的源文档索引列表，如果为None则合并所有其他文档
            
        Raises:
            YAMLError: YAML处理错误
        """
        try:
            documents = self.read_file(file_path)
            if not documents:
                return
                
            if not 0 <= target_index < len(documents):
                raise IndexError(f"Target index {target_index} out of range")
            
            # 如果没有指定源索引，则使用除目标索引外的所有索引
            if source_indices is None:
                source_indices = [i for i in range(len(documents)) if i != target_index]
            
            # 验证源索引
            for idx in source_indices:
                if not 0 <= idx < len(documents):
                    raise IndexError(f"Source index {idx} out of range")
            
            # 合并文档
            target_doc = documents[target_index]
            for idx in source_indices:
                self._merge_dict(target_doc, documents[idx])
            
            # 移除已合并的文档
            new_documents = [doc for i, doc in enumerate(documents) if i not in source_indices or i == target_index]
            
            # 写回文件
            self.write_file(file_path, new_documents)
            
        except Exception as e:
            log.error(f"Error merging documents in {file_path}: {str(e)}")
            raise YAMLError(f"Error merging documents", details=str(e))

    def _update_dict(self, target: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """递归更新字典的值
        
        Args:
            target: 目标字典
            updates: 更新的键值对
        """
        for key, value in updates.items():
            if key in target:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    self._update_dict(target[key], value)
                else:
                    target[key] = value

    def _merge_dict(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """递归合并字典
        
        Args:
            target: 目标字典
            source: 源字典
        """
        for key, value in source.items():
            if key in target:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    self._merge_dict(target[key], value)
                elif isinstance(target[key], list) and isinstance(value, list):
                    target[key].extend(value)
                else:
                    target[key] = value
            else:
                target[key] = value

    def _backup_file(self, file_path: Path) -> None:
        """备份文件
        
        Args:
            file_path: 要备份的文件路径
            
        Raises:
            BackupError: 备份失败
        """
        try:
            backup_path = file_path.with_suffix(file_path.suffix + self._backup_suffix)
            log.debug(f"Creating backup: {backup_path}")
            file_path.rename(backup_path)
        except Exception as e:
            log.error(f"Failed to create backup for {file_path}: {str(e)}")
            raise BackupError(f"Failed to create backup for {file_path}", details=str(e))

    def _get_value_by_path(self, data: Dict[str, Any], path: str) -> Any:
        """通过路径获取值
        
        Args:
            data: 数据字典
            path: 值的路径（使用点号分隔）
            
        Returns:
            Any: 路径对应的值
            
        Raises:
            KeyError: 路径不存在
        """
        current = data
        for key in path.split('.'):
            if not isinstance(current, dict):
                raise KeyError(f"Cannot access '{key}' in path '{path}'")
            if key not in current:
                raise KeyError(f"Key '{key}' not found in path '{path}'")
            current = current[key]
        return current

    def _set_value_by_path(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """通过路径设置值
        
        Args:
            data: 数据字典
            path: 值的路径（使用点号分隔）
            value: 要设置的值
            
        Raises:
            KeyError: 路径不存在
        """
        keys = path.split('.')
        current = data
        
        # 遍历到最后一个键之前
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                raise KeyError(f"Cannot set value at '{path}': '{key}' is not a dictionary")
            current = current[key]
        
        # 设置最后一个键的值
        current[keys[-1]] = value

    def _validate_dict_structure(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """验证字典结构
        
        Args:
            data: 要验证的数据
            schema: 结构模式
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        try:
            for key, value_type in schema.items():
                # 检查必需的键是否存在
                if key not in data:
                    return False, f"Missing required key: {key}"
                
                # 如果值类型是字典，递归验证
                if isinstance(value_type, dict):
                    if not isinstance(data[key], dict):
                        return False, f"Expected dictionary for key {key}"
                    valid, error = self._validate_dict_structure(data[key], value_type)
                    if not valid:
                        return False, f"In {key}: {error}"
                
                # 如果值类型是类型列表，验证值的类型
                elif isinstance(value_type, (type, tuple)):
                    if not isinstance(data[key], value_type):
                        return False, f"Invalid type for {key}: expected {value_type}, got {type(data[key])}"
            
            return True, None
            
        except Exception as e:
            return False, str(e)

    def is_yaml_file(self, file_path: Union[str, Path]) -> bool:
        """检查文件是否是YAML文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否是YAML文件
        """
        path = Path(file_path)
        return (
            path.suffix.lower() in [".yml", ".yaml"] and
            path.is_file() and
            path.stat().st_size <= self.config.max_file_size
        )

    def validate_yaml(self, content: str) -> bool:
        """验证YAML内容是否有效
        
        Args:
            content: YAML内容字符串
            
        Returns:
            bool: 是否是有效的YAML
        """
        try:
            list(pkvpm.load_all(content))
            return True
        except:
            return False 
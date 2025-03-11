"""
备份管理模块
"""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from ..config import BackupConfig
from ..utils import BackupError, log


class BackupManager:
    """备份管理器"""

    def __init__(self, config: BackupConfig):
        """初始化备份管理器
        
        Args:
            config: 备份配置
        """
        self.config = config
        self._backup_dir = Path(config.backup_dir)
        self._backup_info_file = self._backup_dir / "backup_info.json"
        self._backup_info: Dict[str, List[Dict]] = {}
        
        # 创建备份目录
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载备份信息
        self._load_backup_info()

    def backup_file(self, file_path: Union[str, Path]) -> Path:
        """备份文件
        
        Args:
            file_path: 要备份的文件路径
            
        Returns:
            Path: 备份文件路径
            
        Raises:
            BackupError: 备份失败
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise BackupError(f"文件不存在: {file_path}")
            
            # 生成备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            backup_path = self._backup_dir / backup_name
            
            # 复制文件
            shutil.copy2(file_path, backup_path)
            
            # 更新备份信息
            self._add_backup_info(file_path, backup_path)
            
            # 清理旧备份
            self._cleanup_old_backups(file_path)
            
            log.debug(f"已备份文件 {file_path} 到 {backup_path}")
            return backup_path
            
        except Exception as e:
            log.error(f"备份文件 {file_path} 失败: {str(e)}")
            raise BackupError(f"备份失败: {str(e)}")

    def restore_file(
        self,
        file_path: Union[str, Path],
        backup_index: int = -1,
    ) -> None:
        """从备份恢复文件
        
        Args:
            file_path: 要恢复的文件路径
            backup_index: 备份索引，默认为最新的备份
            
        Raises:
            BackupError: 恢复失败
        """
        try:
            file_path = Path(file_path)
            backups = self._backup_info.get(str(file_path), [])
            
            if not backups:
                raise BackupError(f"没有找到文件 {file_path} 的备份")
            
            # 获取指定的备份
            try:
                backup = backups[backup_index]
            except IndexError:
                raise BackupError(f"无效的备份索引: {backup_index}")
            
            backup_path = Path(backup["path"])
            if not backup_path.exists():
                raise BackupError(f"备份文件不存在: {backup_path}")
            
            # 恢复文件
            shutil.copy2(backup_path, file_path)
            log.debug(f"已从 {backup_path} 恢复文件 {file_path}")
            
        except Exception as e:
            log.error(f"恢复文件 {file_path} 失败: {str(e)}")
            raise BackupError(f"恢复失败: {str(e)}")

    def list_backups(self, file_path: Union[str, Path]) -> List[Dict]:
        """列出文件的所有备份
        
        Args:
            file_path: 文件路径
            
        Returns:
            List[Dict]: 备份信息列表
        """
        return self._backup_info.get(str(Path(file_path)), [])

    def cleanup(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """清理备份文件
        
        Args:
            file_path: 要清理的文件路径，如果为None则清理所有备份
        """
        try:
            if file_path:
                # 清理指定文件的备份
                self._cleanup_old_backups(Path(file_path), keep_count=0)
            else:
                # 清理所有备份
                for path in list(self._backup_info.keys()):
                    self._cleanup_old_backups(Path(path), keep_count=0)
            
            log.debug("已清理备份文件")
            
        except Exception as e:
            log.error(f"清理备份失败: {str(e)}")
            raise BackupError(f"清理失败: {str(e)}")

    def _add_backup_info(self, original_path: Path, backup_path: Path) -> None:
        """添加备份信息
        
        Args:
            original_path: 原始文件路径
            backup_path: 备份文件路径
        """
        # 获取文件信息
        stat = backup_path.stat()
        
        # 创建备份记录
        backup_info = {
            "path": str(backup_path),
            "timestamp": datetime.now().isoformat(),
            "size": stat.st_size,
            "original_path": str(original_path),
        }
        
        # 添加到备份信息
        key = str(original_path)
        if key not in self._backup_info:
            self._backup_info[key] = []
        self._backup_info[key].append(backup_info)
        
        # 保存备份信息
        self._save_backup_info()

    def _cleanup_old_backups(
        self,
        file_path: Path,
        keep_count: Optional[int] = None,
    ) -> None:
        """清理旧的备份文件
        
        Args:
            file_path: 文件路径
            keep_count: 保留的备份数量，如果为None则使用配置值
        """
        if keep_count is None:
            keep_count = self.config.keep_backups
        
        key = str(file_path)
        backups = self._backup_info.get(key, [])
        
        if not backups or len(backups) <= keep_count:
            return
        
        # 按时间戳排序
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # 删除多余的备份
        for backup in backups[keep_count:]:
            try:
                backup_path = Path(backup["path"])
                if backup_path.exists():
                    backup_path.unlink()
            except Exception as e:
                log.warning(f"删除备份文件 {backup['path']} 失败: {str(e)}")
        
        # 更新备份信息
        self._backup_info[key] = backups[:keep_count]
        self._save_backup_info()

    def _load_backup_info(self) -> None:
        """加载备份信息"""
        try:
            if self._backup_info_file.exists():
                with self._backup_info_file.open("r", encoding="utf-8") as f:
                    self._backup_info = json.load(f)
            
            # 验证备份文件是否存在
            for file_path, backups in list(self._backup_info.items()):
                valid_backups = []
                for backup in backups:
                    if Path(backup["path"]).exists():
                        valid_backups.append(backup)
                
                if valid_backups:
                    self._backup_info[file_path] = valid_backups
                else:
                    del self._backup_info[file_path]
            
            # 保存清理后的信息
            self._save_backup_info()
            
        except Exception as e:
            log.error(f"加载备份信息失败: {str(e)}")
            self._backup_info = {}

    def _save_backup_info(self) -> None:
        """保存备份信息"""
        try:
            with self._backup_info_file.open("w", encoding="utf-8") as f:
                json.dump(self._backup_info, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"保存备份信息失败: {str(e)}") 
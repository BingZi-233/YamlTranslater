"""
提示词管理模块
"""
import json
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, Union

from ..config import PromptConfig
from ..utils import PromptError, log


@dataclass
class PromptTemplate:
    """提示词模板"""
    name: str  # 模板名称
    content: str  # 模板内容
    description: Optional[str] = None  # 模板描述
    variables: Dict[str, str] = None  # 变量说明
    category: Optional[str] = None  # 模板分类
    version: str = "1.0"  # 模板版本


class PromptManager:
    """提示词管理器"""

    def __init__(self, config: PromptConfig):
        """初始化提示词管理器
        
        Args:
            config: 提示词配置
        """
        self.config = config
        self._templates: Dict[str, PromptTemplate] = {}
        self._default_template: Optional[PromptTemplate] = None
        
        # 加载默认模板
        self._load_default_template()
        
        # 加载模板目录
        if config.template_dir:
            self._load_template_dir(Path(config.template_dir))

    def get_template(self, name: str) -> PromptTemplate:
        """获取提示词模板
        
        Args:
            name: 模板名称
            
        Returns:
            PromptTemplate: 提示词模板
            
        Raises:
            PromptError: 模板不存在
        """
        if name not in self._templates:
            raise PromptError(f"Template not found: {name}")
        return self._templates[name]

    def render_template(
        self,
        name: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """渲染提示词模板
        
        Args:
            name: 模板名称
            variables: 变量值字典
            
        Returns:
            str: 渲染后的提示词
            
        Raises:
            PromptError: 渲染错误
        """
        try:
            # 获取模板
            template = self.get_template(name)
            
            # 如果没有变量，直接返回模板内容
            if not variables:
                return template.content
            
            # 渲染模板
            return Template(template.content).safe_substitute(variables)
            
        except KeyError as e:
            raise PromptError(f"Missing variable: {str(e)}")
        except Exception as e:
            raise PromptError(f"Failed to render template: {str(e)}")

    def add_template(self, template: PromptTemplate) -> None:
        """添加提示词模板
        
        Args:
            template: 提示词模板
            
        Raises:
            PromptError: 模板已存在
        """
        if template.name in self._templates:
            raise PromptError(f"Template already exists: {template.name}")
        
        # 验证模板
        self._validate_template(template)
        
        # 添加到模板字典
        self._templates[template.name] = template
        log.debug(f"Added template: {template.name}")

    def remove_template(self, name: str) -> None:
        """移除提示词模板
        
        Args:
            name: 模板名称
            
        Raises:
            PromptError: 模板不存在或无法删除
        """
        if name not in self._templates:
            raise PromptError(f"Template not found: {name}")
        
        # 不允许删除默认模板
        if self._templates[name] is self._default_template:
            raise PromptError("Cannot remove default template")
        
        # 移除模板
        del self._templates[name]
        log.debug(f"Removed template: {name}")

    def list_templates(self) -> List[str]:
        """列出所有模板名称
        
        Returns:
            List[str]: 模板名称列表
        """
        return list(self._templates.keys())

    def get_template_info(self, name: str) -> Dict[str, Any]:
        """获取模板信息
        
        Args:
            name: 模板名称
            
        Returns:
            Dict[str, Any]: 模板信息
            
        Raises:
            PromptError: 模板不存在
        """
        template = self.get_template(name)
        return {
            "name": template.name,
            "description": template.description,
            "variables": template.variables,
            "category": template.category,
            "version": template.version,
        }

    def _load_default_template(self) -> None:
        """加载默认模板"""
        try:
            # 创建默认模板
            self._default_template = PromptTemplate(
                name="default",
                content=self.config.default_prompt,
                description="默认翻译提示词",
                variables={
                    "text": "要翻译的文本",
                    "context": "上下文信息（可选）",
                    "format": "输出格式要求（可选）",
                },
            )
            
            # 添加到模板字典
            self._templates["default"] = self._default_template
            log.debug("Loaded default template")
            
        except Exception as e:
            log.error(f"Failed to load default template: {str(e)}")
            raise PromptError("Failed to load default template")

    def _load_template_dir(self, template_dir: Path) -> None:
        """加载模板目录
        
        Args:
            template_dir: 模板目录路径
        """
        try:
            # 确保目录存在
            if not template_dir.exists():
                log.warning(f"Template directory not found: {template_dir}")
                return
            
            # 加载所有JSON文件
            for file_path in template_dir.glob("*.json"):
                try:
                    # 读取模板文件
                    with file_path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # 创建模板对象
                    template = PromptTemplate(**data)
                    
                    # 添加到模板字典
                    self.add_template(template)
                    
                except Exception as e:
                    log.error(f"Failed to load template file {file_path}: {str(e)}")
            
            log.debug(f"Loaded templates from {template_dir}")
            
        except Exception as e:
            log.error(f"Failed to load template directory: {str(e)}")
            raise PromptError("Failed to load template directory")

    def _validate_template(self, template: PromptTemplate) -> None:
        """验证提示词模板
        
        Args:
            template: 提示词模板
            
        Raises:
            PromptError: 验证失败
        """
        try:
            # 检查必填字段
            if not template.name:
                raise PromptError("Template name is required")
            if not template.content:
                raise PromptError("Template content is required")
            
            # 检查变量定义
            if template.variables:
                # 尝试解析模板中的变量
                try:
                    Template(template.content).pattern
                except Exception as e:
                    raise PromptError(f"Invalid template variables: {str(e)}")
                
                # 检查所有声明的变量是否在内容中使用
                template_vars = set(Template(template.content).get_identifiers())
                declared_vars = set(template.variables.keys())
                
                # 检查未声明的变量
                undeclared = template_vars - declared_vars
                if undeclared:
                    raise PromptError(
                        f"Undeclared variables in template: {', '.join(undeclared)}"
                    )
                
                # 检查未使用的变量
                unused = declared_vars - template_vars
                if unused:
                    log.warning(
                        f"Unused variables in template {template.name}: "
                        f"{', '.join(unused)}"
                    )
            
            log.debug(f"Validated template: {template.name}")
            
        except PromptError:
            raise
        except Exception as e:
            raise PromptError(f"Template validation failed: {str(e)}") 
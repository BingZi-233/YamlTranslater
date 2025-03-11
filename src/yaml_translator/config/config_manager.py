from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pkvpm
from pydantic import BaseModel, Field, validator


class APIConfig(BaseModel):
    """API配置模型"""
    endpoint: str = Field(default="https://api.openai.com/v1")
    key: str = Field(default="")
    model: str = Field(default="gpt-3.5-turbo")
    max_tokens: int = Field(default=4000)
    temperature: float = Field(default=0.7)
    timeout: int = Field(default=30)
    retry_count: int = Field(default=3)


class FileMatchingConfig(BaseModel):
    """文件匹配配置模型"""
    include_patterns: List[str] = Field(default=["*.yml", "*.yaml"])
    exclude_patterns: List[str] = Field(default=[".git/**", "node_modules/**", "venv/**"])
    exclude_dirs: List[str] = Field(default=[".git", "node_modules", "venv", "__pycache__"])
    max_file_size: int = Field(default=10485760)  # 10MB


class TranslationConfig(BaseModel):
    """翻译配置模型"""
    chunk_size: int = Field(default=2000)
    max_concurrent: int = Field(default=3)
    retry_count: int = Field(default=3)
    retry_delay: int = Field(default=5)


class BlacklistConfig(BaseModel):
    """黑名单配置模型"""
    words: List[str] = Field(default=["API", "URL", "HTTP", "SDK", "ID"])
    patterns: List[str] = Field(default=[r"\$\{.*?\}", r"\{\{.*?\}\}"])
    case_sensitive: bool = Field(default=False)
    preserve_case: bool = Field(default=True)


class PromptTemplate(BaseModel):
    """提示词模板模型"""
    name: str
    content: str


class PromptsConfig(BaseModel):
    """提示词配置模型"""
    default: str
    templates: List[PromptTemplate] = Field(default=[])


class ProgressConfig(BaseModel):
    """进度配置模型"""
    save_interval: int = Field(default=30)
    save_path: str = Field(default=".progress")
    auto_resume: bool = Field(default=True)
    keep_history: bool = Field(default=True)
    backup: bool = Field(default=True)
    backup_suffix: str = Field(default=".bak")


class LoggingConfig(BaseModel):
    """日志配置模型"""
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file: str = Field(default="yaml_translator.log")
    max_size: int = Field(default=10485760)
    backup_count: int = Field(default=5)

    @validator("level")
    def validate_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of {valid_levels}")
        return v.upper()


class Config(BaseModel):
    """主配置模型"""
    api: APIConfig = Field(default_factory=APIConfig)
    file_matching: FileMatchingConfig = Field(default_factory=FileMatchingConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    blacklist: BlacklistConfig = Field(default_factory=BlacklistConfig)
    prompts: PromptsConfig
    progress: ProgressConfig = Field(default_factory=ProgressConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class ConfigManager:
    """配置管理器"""
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self._config: Optional[Config] = None
        self._config_path = Path(config_path) if config_path else None
        self._default_config_path = Path(__file__).parent / "default_config.yaml"

    def load(self) -> Config:
        """加载配置"""
        # 首先加载默认配置
        default_config = self._load_yaml(self._default_config_path)
        
        # 如果指定了自定义配置，则合并配置
        if self._config_path and self._config_path.exists():
            user_config = self._load_yaml(self._config_path)
            merged_config = self._merge_configs(default_config, user_config)
        else:
            merged_config = default_config

        # 创建配置对象
        self._config = Config(**merged_config)
        return self._config

    @property
    def config(self) -> Config:
        """获取配置对象"""
        if self._config is None:
            self.load()
        return self._config

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        """加载YAML文件"""
        try:
            with path.open("r", encoding="utf-8") as f:
                return pkvpm.load(f)
        except Exception as e:
            raise ValueError(f"Failed to load config file {path}: {str(e)}")

    @staticmethod
    def _merge_configs(default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """递归合并配置"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        """保存配置到文件"""
        if self._config is None:
            raise ValueError("No config loaded")

        save_path = Path(path) if path else self._config_path
        if save_path is None:
            raise ValueError("No save path specified")

        # 确保目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存配置
        with save_path.open("w", encoding="utf-8") as f:
            pkvpm.dump(self._config.dict(), f)

    def update(self, config_dict: Dict[str, Any]) -> None:
        """更新配置"""
        if self._config is None:
            self.load()
        
        # 合并新的配置
        merged = self._merge_configs(self._config.dict(), config_dict)
        self._config = Config(**merged)

    def get_prompt_template(self, name: str) -> Optional[str]:
        """获取指定名称的提示词模板"""
        if self._config is None:
            self.load()
            
        for template in self._config.prompts.templates:
            if template.name == name:
                return template.content
        return None 
# YAML翻译器

一个基于OpenAI的YAML文件翻译工具，支持智能分块、进度保存、断点续传等功能。

## 功能特点

- 智能YAML解析和保留格式
- 基于OpenAI的高质量翻译
- 智能分块和上下文保持
- 自动进度保存和断点续传
- 完整的错误处理和重试机制
- 黑名单词汇保护
- 美化的终端界面

## 环境要求

- Python 3.8+
- OpenAI API密钥
- pip 或 uv（推荐）包管理器

## 快速开始

### 1. 创建虚拟环境

使用 `venv` 创建虚拟环境：

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 2. 安装包

有两种安装方式：

#### 2.1 从PyPI安装（推荐用户使用）

```bash
pip install yaml-translator
```

#### 2.2 从源码安装（推荐开发者使用）

```bash
# 克隆仓库
git clone https://github.com/BingZi-233/yaml-translator.git
cd yaml-translator

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\activate   # Windows

# 安装开发模式
pip install -e .

# 如果需要开发依赖（测试、代码格式化等）
pip install -e ".[dev]"
```

### 3. 配置环境变量

创建 `.env` 文件并添加以下内容：

```env
# OpenAI API配置
OPENAI_API_KEY=你的OpenAI API密钥
OPENAI_API_MODEL=gpt-3.5-turbo  # 可选，默认使用gpt-3.5-turbo

# 应用配置（可选）
LOG_LEVEL=INFO  # 日志级别：DEBUG, INFO, WARNING, ERROR
MAX_CONCURRENT=5  # 最大并发数
BATCH_SIZE=1000  # 批处理大小
```

### 4. 运行程序

```bash
# 显示帮助信息
yaml-translator --help
# 或
python -m yaml_translator --help

# 翻译单个文件
yaml-translator translate path/to/file.yaml

# 翻译目录
yaml-translator translate path/to/directory

# 使用自定义配置
yaml-translator translate path/to/file.yaml --config path/to/config.yaml
```

## 使用说明

### 基本命令

```bash
# 翻译文件或目录
yaml-translator translate <file_or_dir> [options]

# 查看进度
yaml-translator status

# 恢复翻译
yaml-translator resume

# 管理黑名单
yaml-translator blacklist [add|remove|list]

# 配置管理
yaml-translator config [show|edit|reset]
```

### 配置选项

- `--config`: 指定配置文件路径
- `--model`: 指定使用的模型（默认：gpt-3.5-turbo）
- `--batch-size`: 设置批处理大小（默认：1000）
- `--concurrent`: 设置并发数（默认：5）
- `--verbose`: 显示详细日志
- `--dry-run`: 空运行，不实际执行翻译
- `--force`: 强制重新翻译已翻译的内容
- `--backup`: 在翻译前创建备份

## 项目结构

```
yaml_translator/
├── src/
│   └── yaml_translator/
│       ├── core/           # 核心功能模块
│       ├── cli/           # 命令行接口
│       ├── config/        # 配置管理
│       └── utils/         # 工具函数
├── tests/                 # 测试用例
├── docs/                  # 文档
└── examples/             # 示例文件
```

## 开发指南

1. 克隆仓库：
```bash
git clone https://github.com/BingZi-233/yaml-translator.git
cd yaml-translator
```

2. 创建开发环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\activate  # Windows
```

3. 安装开发依赖：
```bash
pip install -e ".[dev]"
```

4. 运行测试：
```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_specific.py

# 运行带覆盖率报告的测试
pytest --cov=yaml_translator
```

5. 代码格式化：
```bash
# 格式化代码
black .

# 排序导入
isort .

# 类型检查
mypy src/yaml_translator

# 代码质量检查
pylint src/yaml_translator
```

## 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。 
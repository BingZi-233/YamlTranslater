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

### 2. 安装依赖

```bash
# 安装所有依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

创建 `.env` 文件并添加以下内容：

```env
OPENAI_API_KEY=你的OpenAI API密钥
```

### 4. 运行程序

```bash
# 显示帮助信息
python -m yaml_translator --help

# 翻译单个文件
python -m yaml_translator translate path/to/file.yaml

# 翻译目录
python -m yaml_translator translate path/to/directory
```

## 使用说明

### 基本命令

```bash
# 翻译文件
yaml-translator translate <file_or_dir>

# 查看进度
yaml-translator status

# 恢复翻译
yaml-translator resume

# 管理黑名单
yaml-translator blacklist [add|remove|list]
```

### 配置选项

- `--config`: 指定配置文件路径
- `--model`: 指定使用的模型
- `--batch-size`: 设置批处理大小
- `--concurrent`: 设置并发数
- `--verbose`: 显示详细日志

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
git clone https://github.com/yourusername/yaml-translator.git
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
pip install -r requirements.txt
```

4. 运行测试：
```bash
pytest
```

## 贡献指南

1. Fork 本仓库
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。 
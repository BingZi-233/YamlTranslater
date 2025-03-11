# YAML翻译器项目规划

## 项目概述
开发一个基于Python的YAML文件翻译工具，使用PKVPM模块处理YAML文件，通过OpenAI API进行文本翻译，并支持自定义翻译提示词（Prompt）。工具直接修改源文件，支持指定目录和文件名正则匹配，具有黑名单词汇保护和大文件智能处理功能。提供实时进度显示和断点续传能力。

## 功能需求

### 核心功能
1. YAML文件处理
   - 读取YAML文件
   - 解析YAML结构
   - 直接修改源文件
   - 保持原有格式和注释
   - 支持多文档YAML
   - 支持目录递归扫描
   - 支持文件名正则匹配
   - 大文件智能分块处理

2. 文件匹配功能
   - 支持指定目录路径
   - 支持文件名正则表达式
   - 支持排除特定目录（如.git）
   - 支持自定义文件扩展名过滤
   - 递归扫描子目录

3. 翻译功能
   - 支持自定义OpenAI API端点
   - 支持配置API密钥
   - 内置翻译提示词模板
   - 支持自定义提示词
   - 批量翻译处理
   - 原地更新文件内容
   - 黑名单词汇保护
   - 智能分块翻译

4. 配置管理
   - 使用YAML格式配置文件
   - API配置（端点、密钥）
   - 提示词模板管理
   - 翻译规则配置
   - 文件匹配规则配置
   - 黑名单词汇管理
   - 分块翻译设置
   - 进度保存配置

5. 进度管理
   - 实时进度条显示
   - 当前处理文件信息
   - 队列中文件预览
   - Token使用统计
   - 执行时间统计
   - 进度自动保存
   - 断点续传支持
   - 错误状态恢复

### 扩展功能
1. 翻译缓存
2. 并发翻译处理
3. 进度显示
4. 错误处理和重试机制
5. 备份原文件选项
6. 变更预览功能
7. 黑名单词汇导入导出
8. 智能分块策略优化
9. 进度报告导出
10. 批处理任务恢复

## 技术架构

### 核心模块
1. `yaml_handler`
   - 使用PKVPM处理YAML文件
   - 维护文件结构和格式
   - 原地更新文件内容
   - 文件备份功能
   - 大文件分块处理
   - 智能合并结果

2. `file_matcher`
   - 目录扫描
   - 正则匹配
   - 文件过滤
   - 递归处理

3. `translator`
   - OpenAI API集成
   - 翻译队列管理
   - 结果处理
   - 错误重试
   - 黑名单词汇保护
   - 分块翻译管理

4. `prompt_manager`
   - 提示词模板管理
   - 提示词渲染
   - 黑名单词汇注入

5. `config_manager`
   - YAML配置文件处理
   - API设置管理
   - 文件匹配规则管理
   - 黑名单词汇管理
   - 分块策略配置
   - 进度保存配置

6. `progress_manager`
   - 进度条渲染
   - 文件队列管理
   - Token统计
   - 时间统计
   - 状态保存恢复
   - 错误状态管理

### 配置文件结构
```yaml
api:
  endpoint: "https://api.openai.com/v1"
  key: "your-api-key"
  model: "gpt-3.5-turbo"
  max_tokens: 4000
  temperature: 0.7

file_matching:
  include_patterns: ["*.yml", "*.yaml"]
  exclude_patterns: [".git/**", "node_modules/**"]
  exclude_dirs: [".git", "node_modules", "venv"]

translation:
  chunk_size: 2000  # 每块最大字符数
  max_concurrent: 3  # 并发翻译数
  retry_count: 3    # 重试次数
  
blacklist:
  words: ["API", "URL", "HTTP", "SDK"]
  patterns: ["\\$\\{.*?\\}"]  # 正则表达式
  case_sensitive: false

prompts:
  default: "将以下YAML内容翻译为中文，保持键名不变"
  templates:
    - name: "technical"
      content: "这是技术文档翻译..."
    - name: "general"
      content: "这是普通文本翻译..."

progress:
  save_interval: 30  # 进度保存间隔（秒）
  save_path: ".progress"  # 进度文件保存路径
  auto_resume: true  # 是否自动恢复
  keep_history: true  # 保留历史记录
  error_retry: true  # 错误自动重试
```

### 进度文件结构
```yaml
session:
  start_time: "2024-03-10T10:00:00Z"
  last_update: "2024-03-10T10:30:00Z"
  total_files: 50
  completed_files: 20
  total_tokens: 15000
  total_cost: 0.45
  elapsed_time: 1800

current_file:
  path: "docs/config.yaml"
  progress: 0.75
  chunks_total: 4
  chunks_completed: 3
  tokens: 2500

queue:
  - path: "docs/api.yaml"
    size: 15000
  - path: "docs/schema.yaml"
    size: 8000

completed:
  - path: "docs/readme.yaml"
    tokens: 1200
    time: 25
  - path: "docs/setup.yaml"
    tokens: 800
    time: 15

errors:
  - path: "docs/error.yaml"
    error: "API rate limit exceeded"
    retry_count: 2
    next_retry: "2024-03-10T11:00:00Z"
```

### 依赖
- Python 3.8+
- pkvpm：YAML处理
- openai：API调用
- pydantic：数据验证
- rich：终端输出美化
- pathspec：文件匹配
- regex：正则表达式支持
- tqdm：进度条显示
- pytz：时区处理

## 项目结构
```
yaml_translator/
├── src/
│   └── yaml_translator/
│       ├── core/
│       │   ├── yaml_handler.py
│       │   ├── file_matcher.py
│       │   ├── translator.py
│       │   ├── prompt_manager.py
│       │   ├── chunk_manager.py
│       │   └── progress_manager.py
│       ├── config/
│       │   ├── config_manager.py
│       │   └── default_config.yaml
│       ├── utils/
│       │   ├── logger.py
│       │   ├── exceptions.py
│       │   └── progress_store.py
│       └── cli.py
├── tests/
├── docs/
├── prompts/
│   └── templates/
├── .progress/  # 进度文件目录
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 开发计划

### 第一阶段：基础架构
1. 项目初始化
2. 核心模块框架搭建
3. YAML配置系统实现
4. 文件匹配模块实现
5. 进度管理系统实现

### 第二阶段：核心功能
1. YAML处理实现
   - 文件读写
   - 原地更新
   - 格式保持
   - 大文件分块
2. 翻译功能集成
   - 基础翻译
   - 黑名单保护
   - 分块翻译
3. 提示词管理
4. 进度显示实现
   - 进度条集成
   - 文件队列显示
   - 统计信息收集
   - 状态保存恢复

### 第三阶段：功能完善
1. 错误处理
2. 日志系统
3. CLI实现
4. 文件备份功能
5. 黑名单管理
6. 分块优化
7. 进度恢复优化
8. 错误重试策略

### 第四阶段：测试和优化
1. 单元测试
2. 集成测试
3. 性能优化
4. 并发处理
5. 大文件处理测试
6. 断点续传测试
7. 性能监控优化

## 注意事项
1. 确保YAML格式保持一致性
2. API调用限制处理
3. 错误恢复机制
4. 配置安全性
5. 文件修改安全性
6. 大文件处理策略
7. 黑名单词汇优先级
8. 分块翻译一致性
9. 进度保存频率
10. 内存使用控制 
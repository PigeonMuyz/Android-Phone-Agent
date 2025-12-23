# Android Phone Agent

> 一个支持多 VLM 提供商、多设备并行的 Android 手机自动化智能体框架

## 功能特点

- 🔌 **多模型支持**: OpenAI、Anthropic、Google Gemini、DeepSeek、OpenRouter 等
- 📱 **多设备管理**: 同时连接多台 Android 设备，并行执行任务
- 💰 **成本透明**: 实时计费统计，支持多种计费模式
- 🎨 **TUI 界面**: 基于 Textual 的现代终端用户界面
- 📝 **智能 Prompt**: 默认/App专属/功能专用三层 Prompt 体系

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/your-repo/phone-agent.git
cd phone-agent

# 安装依赖
pip install -e .
```

### 配置

1. 复制配置文件：
```bash
cp .env.example .env
```

2. 编辑 `.env`，填入你的 API Keys

3. 编辑 `config/profiles.yaml`，配置模型 Profile

### 运行

```bash
# 启动 TUI 界面
phone-agent

# 或者使用 Python 模块
python -m phone_agent
```

## 项目结构

```
phone-agent/
├── phone_agent/          # 核心代码
│   ├── agent/            # Agent 核心逻辑
│   ├── providers/        # VLM 适配层
│   ├── adb/              # ADB 设备控制
│   ├── billing/          # 计费模块
│   ├── prompts/          # Prompt 管理
│   └── tui/              # TUI 界面
├── config/               # 配置文件
└── prompts/              # Prompt 资源
```

## 许可证

MIT License

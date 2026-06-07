# 丛雨 (Murasame) Telegram Bot

一个以丛雨（千恋＊万花）角色为人格的 Telegram 聊天机器人，支持文字、语音、图片、视频交互。

## 功能特性

- 🎭 **角色扮演** - 以丛雨的人格与用户对话
- 🗣️ **语音交互** - 支持语音消息识别与日语语音合成
- 🖼️ **图片理解** - 多模态 AI 分析图片内容
- 🎬 **视频理解** - 多模态 AI 分析视频内容
- 💬 **对话管理** - 支持多对话切换、重命名、删除
- 🔐 **用户认证** - 配对码授权机制

## 快速开始

### 环境要求

- Python 3.11+
- uv 包管理器

### 安装

```bash
# 克隆仓库
git clone https://github.com/apnn633/tgbot.git
cd tgbot

# 安装依赖
uv sync

# 复制配置文件
cp .env.example .env
# 编辑 .env 填入你的 API 密钥
```

### 配置

编辑 `.env` 文件，配置以下必要项：

```env
# Telegram Bot Token (必需)
TELEGRAM_BOT_TOKEN=your_bot_token

# 对话 API (GLM / DeepSeek / OpenAI 兼容)
CHAT_API_KEY=your_api_key
CHAT_BASE_URL=https://open.bigmodel.cn/api/paas/v4
CHAT_MODEL=glm-4.6

# 多模态 API (用于图片/视频理解)
MULTIMODAL_API_KEY=your_api_key
MULTIMODAL_BASE_URL=https://cloud.infini-ai.com/maas/v1
MULTIMODAL_MODEL=qwen3-vl-plus
```

### 运行

```bash
# 普通模式
uv run python main.py

# 后台运行，日志输出到文件
uv run python main.py -o bot.log

# 静默模式（无控制台输出）
uv run python main.py -o bot.log -q

# 调试模式
uv run python main.py --debug
```

## 配置说明

### 多模态模式

`MULTIMODAL_MODE` 支持三种模式：

| 模式 | 说明 | 要求 |
|------|------|------|
| `auto` | 自动选择 | 两个 API 都配置时用 two_step |
| `two_step` | 多模态分析 → 对话生成 | 需同时配置两个 API |
| `direct` | 多模态 AI 直接回复 | 只需多模态 API |
| `disabled` | 禁用图片/视频 | 只需对话 API |

### 语音配置

**STT (语音识别):**
- OpenAI Whisper（默认）
- 讯飞语音

**TTS (语音合成):**
- InworldTTS（日语语音）
- OpenAI TTS

## 命令列表

| 命令 | 说明 |
|------|------|
| `/start` | 开始使用/获取配对码 |
| `/help` | 查看帮助 |
| `/new [名称]` | 新建对话 |
| `/list` | 查看对话列表 |
| `/det <编号>` | 删除指定对话 |
| `/delall` | 删除所有对话 |
| `/clear` | 清空当前对话 |
| `/rename <名称>` | 重命名对话 |
| `/voice` | 切换语音模式 |
| `/reset` | 恢复出厂设置 |

## 项目结构

```
tgbot/
├── main.py           # 入口文件
├── pyproject.toml    # 项目配置
├── .env.example      # 配置模板
└── src/tgbot/
    ├── bot.py        # Bot 应用
    ├── config.py     # 配置管理
    ├── handlers.py   # 消息处理
    ├── llm.py        # LLM 集成
    ├── voice.py      # 语音处理
    ├── database.py   # 数据库操作
    ├── auth.py       # 用户认证
    ├── prompts.py    # 提示词
    └── utils.py      # 工具函数
```

## 许可证

MIT License

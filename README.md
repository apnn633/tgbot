# 丛雨 (Murasame) Telegram Bot

一个以丛雨（千恋＊万花）角色为人格的 Telegram 聊天机器人，支持文字、语音、图片、视频交互。

## 功能特性

- 🎭 **角色扮演** - 以丛雨的人格与用户对话，带有傲娇、古风口吻和颜文字
- 🗣️ **语音交互** - 支持语音消息识别（Whisper/讯飞）与日语语音合成（OpenAI TTS/InworldTTS）
- 🖼️ **图片理解** - 多模态 AI 分析图片内容，支持多种视觉模型
- 🎬 **视频理解** - 多模态 AI 分析视频内容
- 💬 **对话管理** - 支持多对话切换、自动命名、重命名、删除
- 🔐 **用户认证** - 配对码授权机制，支持白名单和动态授权
- 🌐 **双模式运行** - 支持 Polling（开发）和 Webhook（生产）模式

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 包管理器
- FFmpeg（讯飞 STT 或音频转码时需要）

## 安装

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

### FFmpeg 安装

讯飞语音识别需要 FFmpeg 进行音频转码：

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows (使用 Chocolatey)
choco install ffmpeg
```

## 配置

编辑 `.env` 文件，配置以下必要项：

### 最小配置

```env
# Telegram Bot Token (必需)
TELEGRAM_BOT_TOKEN=your_bot_token

# 对话 API (必需 - DeepSeek / OpenAI / GLM 兼容)
CHAT_API_KEY=your_api_key
CHAT_BASE_URL=https://api.openai.com/v1
CHAT_MODEL=gpt-4o-mini
```

### 完整配置示例

```env
# === Telegram Bot ===
TELEGRAM_BOT_TOKEN=your_bot_token_here

# === 认证 ===
ALLOWED_USER_IDS=12345678,87654321
PAIRING_CODE_TTL=300

# === 对话 API ===
CHAT_API_KEY=your_chat_api_key_here
CHAT_BASE_URL=https://open.bigmodel.cn/api/paas/v4
CHAT_MODEL=glm-4.6

# === 多模态 API ===
MULTIMODAL_MODE=auto
MULTIMODAL_API_KEY=your_api_key
MULTIMODAL_BASE_URL=https://cloud.infini-ai.com/maas/v1
MULTIMODAL_MODEL=qwen3-vl-plus

# === STT (语音识别) ===
STT_PROVIDER=openai
STT_API_KEY=your_api_key
STT_BASE_URL=https://api.openai.com/v1
STT_MODEL=whisper-1

# === TTS (语音合成) ===
TTS_PROVIDER=openai
TTS_API_KEY=your_api_key
TTS_BASE_URL=https://api.openai.com/v1
TTS_MODEL=tts-1
TTS_VOICE=shimmer
TTS_OUTPUT_MODE=llm_output
```

### 配置说明

#### 多模态模式

`MULTIMODAL_MODE` 支持四种模式：

| 模式 | 说明 | 要求 |
|------|------|------|
| `auto` | 自动选择（推荐） | 两个 API 都配置时用 two_step |
| `two_step` | 多模态分析 → 对话生成 | 需同时配置两个 API |
| `direct` | 多模态 AI 直接回复 | 只需多模态 API |
| `disabled` | 禁用图片/视频 | 只需对话 API |

#### 视觉模型选择

| 模型系列 | 支持传输 | 图片限制 | 视频限制 |
|----------|----------|----------|----------|
| Qwen-VL (qwen3-vl-plus 等) | 仅 Base64 | 5MB | 5MB |
| GLM (glm-4.5v, glm-4.6v) | URL + Base64 | 5MB | 200MB |

> 如果使用 GLM 模型时 URL 访问失败，Bot 会自动回退到 Base64 模式，并可通过 `/fix` 命令永久启用 Base64 模式。

#### 语音配置

**STT (语音识别):**

| 服务 | 说明 | 依赖 |
|------|------|------|
| OpenAI Whisper（默认） | 多语言识别 | 无额外依赖 |
| 讯飞语音 | 中文/英文/方言 | FFmpeg |

**TTS (语音合成):**

| 服务 | 说明 | 配置 |
|------|------|------|
| OpenAI TTS（默认） | 多语言语音合成 | `TTS_API_KEY`, `TTS_VOICE` |
| InworldTTS | 日语语音克隆 | `INWORLD_API_KEY`, `INWORLD_VOICE_ID` |

**TTS 输出模式:**

| 模式 | 说明 |
|------|------|
| `llm_output`（推荐） | AI 直接输出 JSON `{"zh": "中文", "ja": "日语"}`，效率高 |
| `translate` | 先生成中文，再翻译成日语，兼容性好 |

#### 认证配置

| 配置项 | 说明 |
|--------|------|
| `ALLOWED_USER_IDS` | 白名单用户 ID（逗号分隔），留空则所有人需要配对码认证 |
| `PAIRING_CODE_TTL` | 配对码有效期（秒），默认 300 |

## 运行

### 使用 uv 直接运行

```bash
# 默认模式（自动选择 polling/webhook）
uv run python main.py

# Polling 模式（开发推荐）
uv run python main.py --polling

# Webhook 模式（生产推荐）
uv run python main.py --webhook
```

### 使用启动脚本

```bash
# Polling 模式
./run.sh --polling

# Webhook 模式（默认）
./run.sh
```

### 命令行参数

| 参数 | 说明 |
|------|------|
| `--polling` | 使用 Polling 模式运行 |
| `--webhook` | 使用 Webhook 模式运行 |
| `--debug` | 调试模式（显示所有日志） |
| `--no-pretty` | 禁用彩色日志输出 |
| `-o, --output FILE` | 日志输出到文件 |
| `-q, --quiet` | 静默模式（无控制台输出） |

### 后台运行

```bash
# 后台运行，日志输出到文件
uv run python main.py -o bot.log -q &

# 使用 nohup
nohup uv run python main.py -o bot.log -q &

# 使用 systemd（推荐生产环境）
# 创建 /etc/systemd/system/tgbot.service
```

## 用户管理

使用 `tgbot-admin` 命令行工具管理用户：

```bash
# 使用配对码授权用户
uv run tgbot-admin pair <配对码>

# 列出已授权用户
uv run tgbot-admin list

# 列出待处理配对请求
uv run tgbot-admin pending

# 撤销用户授权
uv run tgbot-admin revoke <用户ID>

# 清理过期配对码
uv run tgbot-admin cleanup

# 显示白名单
uv run tgbot-admin whitelist
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `/start` | 开始使用/获取配对码 |
| `/help` | 查看帮助 |
| `/new [名称]` | 新建对话 |
| `/list` | 查看对话列表 |
| `/det <编号>` | 删除指定对话（支持多个，空格分隔） |
| `/delall` | 删除所有对话 |
| `/clear` | 清空当前对话 |
| `/rename <编号> <名称>` | 重命名对话（省略编号则重命名当前对话） |
| `/voice` | 切换语音模式 |
| `/reset` | 恢复出厂设置 |
| `/fix` | 修复图片 URL 访问问题（自动启用 Base64 模式） |

## 项目结构

```
tgbot/
├── main.py               # 入口文件
├── pyproject.toml         # 项目配置
├── run.sh                 # 启动脚本
├── .env.example           # 配置模板
└── src/tgbot/
    ├── __init__.py        # 包初始化
    ├── bot.py             # Bot 应用创建与运行
    ├── cli.py             # 管理命令行工具
    ├── config.py          # 配置管理
    ├── constants.py       # 共享常量
    ├── database.py        # SQLite 数据库操作
    ├── handlers.py        # Telegram 消息处理
    ├── llm.py             # LLM API 集成
    ├── prompts.py         # AI 提示词
    ├── auth.py            # 用户认证管理
    ├── utils.py           # 工具函数
    └── voice.py           # 语音处理（STT/TTS）
```

## 常见问题

### Bot 启动失败

| 问题 | 解决方案 |
|------|----------|
| `配置缺失: TELEGRAM_BOT_TOKEN` | 在 `.env` 中设置 Bot Token |
| `配置缺失: CHAT_API_KEY` | 在 `.env` 中设置对话 API 密钥 |
| `Connection error` | 检查网络连接和 API 地址是否正确 |

### 图片/视频无法识别

1. 确认已配置 `MULTIMODAL_API_KEY`
2. 检查 `MULTIMODAL_MODE` 是否为 `disabled`
3. 如果使用 GLM 模型遇到 URL 访问失败，发送 `/fix` 命令或设置 `FORCE_BASE64_IMAGE=true`

### 语音功能不工作

1. **语音识别失败**：检查 `STT_API_KEY` 是否正确配置
2. **讯飞 STT 失败**：确认已安装 FFmpeg（`ffmpeg -version`）
3. **语音合成失败**：检查 `TTS_API_KEY` 是否正确配置
4. **InworldTTS 失败**：确认 `INWORLD_API_KEY` 和 `INWORLD_VOICE_ID` 都已设置

### Webhook 模式无法接收消息

1. 确认 `WEBHOOK_URL` 可从外网访问
2. 确认 `WEBHOOK_PORT` 未被防火墙阻止
3. 使用 Cloudflare Tunnel 等工具暴露本地端口：
   ```bash
   cloudflared tunnel --url http://localhost:8443
   ```

### 数据库相关

- 数据库文件位于 `.tgbot_data/tgbot.db`
- 删除数据库文件会丢失所有对话和授权数据
- 数据库使用 SQLite，无需额外安装

## 贡献指南

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m "Add your feature"`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

### 代码规范

- 使用 [Ruff](https://docs.astral.sh/ruff/) 进行代码检查和格式化
- 行宽限制：100 字符
- Python 版本：3.11+
- 运行检查：`uv run ruff check src/`

## 许可证

MIT License

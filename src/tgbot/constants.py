"""Shared constants for the bot."""

# Telegram message limits
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024

# File size limits (bytes)
MAX_VIDEO_SIZE = 200 * 1024 * 1024  # 200MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024    # 5MB

# Conversation limits
MAX_CONVERSATION_NAME_LENGTH = 50
MAX_CONVERSATION_NAME_AUTO = 20
MAX_HISTORY_MESSAGES = 50

# Pairing code
PAIRING_CODE_LENGTH = 12
DEFAULT_PAIRING_TTL = 300  # 5 minutes

# API defaults
DEFAULT_API_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_TOKENS = 1000

# Multimodal modes
MULTIMODAL_MODE_AUTO = "auto"
MULTIMODAL_MODE_TWO_STEP = "two_step"
MULTIMODAL_MODE_DIRECT = "direct"
MULTIMODAL_MODE_DISABLED = "disabled"
VALID_MULTIMODAL_MODES = {MULTIMODAL_MODE_AUTO, MULTIMODAL_MODE_TWO_STEP, MULTIMODAL_MODE_DIRECT, MULTIMODAL_MODE_DISABLED}

# STT providers
STT_PROVIDER_OPENAI = "openai"
STT_PROVIDER_XUNFEI = "xunfei"
VALID_STT_PROVIDERS = {STT_PROVIDER_OPENAI, STT_PROVIDER_XUNFEI}

# TTS providers
TTS_PROVIDER_OPENAI = "openai"
TTS_PROVIDER_INWORLD = "inworld"
VALID_TTS_PROVIDERS = {TTS_PROVIDER_OPENAI, TTS_PROVIDER_INWORLD}

# TTS output modes
TTS_OUTPUT_LLM = "llm_output"
TTS_OUTPUT_TRANSLATE = "translate"
VALID_TTS_OUTPUT_MODES = {TTS_OUTPUT_LLM, TTS_OUTPUT_TRANSLATE}

# Image MIME type detection
IMAGE_MIME_TYPES = {
    b'\xff\xd8\xff': "image/jpeg",
    b'\x89PNG': "image/png",
    b'GIF87a': "image/gif",
    b'GIF89a': "image/gif",
}

# Bot commands
BOT_COMMANDS = [
    ("start", "开始使用/获取配对码"),
    ("help", "查看帮助"),
    ("new", "新建对话"),
    ("list", "对话列表"),
    ("det", "删除对话"),
    ("delall", "删除所有对话"),
    ("clear", "清空当前对话"),
    ("rename", "重命名对话"),
    ("voice", "切换语音模式"),
    ("reset", "恢复出厂设置"),
]

"""Configuration management for the bot."""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get_bool(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


def _get_float(key: str, default: float) -> float:
    """Get float from environment variable."""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def _get_int(key: str, default: int) -> int:
    """Get int from environment variable."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


@dataclass
class APIConfig:
    """Configuration for an API endpoint."""

    api_key: str = ""
    base_url: str = ""
    model: str = ""

    def is_configured(self) -> bool:
        """Check if this API is properly configured."""
        return bool(self.api_key)


@dataclass
class Config:
    """Bot configuration."""

    # Telegram
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))

    # Webhook
    webhook_url: str = field(default_factory=lambda: os.getenv("WEBHOOK_URL", ""))
    webhook_port: int = field(default_factory=lambda: int(os.getenv("WEBHOOK_PORT", "8443")))
    webhook_secret: str = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", "secret"))

    # === 认证配置 ===
    allowed_user_ids: list[int] = field(
        default_factory=lambda: [
            int(uid.strip())
            for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
            if uid.strip().isdigit()
        ]
    )
    pairing_code_ttl: int = field(
        default_factory=lambda: int(os.getenv("PAIRING_CODE_TTL", "300"))
    )

    # ============================================================
    # 对话 API 配置 (DeepSeek / OpenAI 兼容)
    # ============================================================
    chat_api_key: str = field(
        default_factory=lambda: os.getenv("CHAT_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    )
    chat_base_url: str = field(
        default_factory=lambda: os.getenv("CHAT_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    )
    chat_model: str = field(
        default_factory=lambda: os.getenv("CHAT_MODEL", "gpt-4o-mini")
    )

    # ============================================================
    # 多模态 API 配置 (无问芯穹 / OpenAI Vision)
    # ============================================================
    # 多模态模式:
    #   "auto" - 自动选择：对话AI配置则两步模式，否则使用多模态AI直接回复
    #   "two_step" - 两步模式：多模态AI分析 -> 对话AI生成回复（需同时配置两个API）
    #   "direct" - 直接模式：多模态AI直接回复（只需配置多模态API）
    #   "disabled" - 禁用：不支持图片/视频（只需配置对话API）
    multimodal_mode: str = field(
        default_factory=lambda: os.getenv("MULTIMODAL_MODE", "auto")
    )
    multimodal_api_key: str = field(
        default_factory=lambda: os.getenv("MULTIMODAL_API_KEY", "")
    )
    # 无问芯穹: https://cloud.infini-ai.com/maas/v1
    multimodal_base_url: str = field(
        default_factory=lambda: os.getenv("MULTIMODAL_BASE_URL", "https://cloud.infini-ai.com/maas/v1")
    )
    multimodal_model: str = field(
        default_factory=lambda: os.getenv("MULTIMODAL_MODEL", "qwen3-vl-plus")
    )
    # 强制使用 Base64 传输图片/视频（禁用 URL 模式）
    # 设为 true 可避免 URL 访问失败的问题
    force_base64_image: bool = field(
        default_factory=lambda: _get_bool("FORCE_BASE64_IMAGE", False)
    )
    # 内部标记：URL 模式失败时设置为 True
    _url_fallback_needed: bool = field(default=False, repr=False)
    # 向后兼容
    use_separate_multimodal_api: bool = field(
        default_factory=lambda: _get_bool("USE_SEPARATE_MULTIMODAL_API", True)
    )

    # ============================================================
    # STT API 配置 (讯飞 / OpenAI Whisper)
    # ============================================================
    # STT 服务类型: "openai" 或 "xunfei"
    stt_provider: str = field(
        default_factory=lambda: os.getenv("STT_PROVIDER", "openai")
    )
    # OpenAI Whisper
    stt_api_key: str = field(
        default_factory=lambda: os.getenv("STT_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    )
    stt_base_url: str = field(
        default_factory=lambda: os.getenv("STT_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    )
    stt_model: str = field(
        default_factory=lambda: os.getenv("STT_MODEL", "whisper-1")
    )
    # 讯飞配置
    xunfei_app_id: str = field(
        default_factory=lambda: os.getenv("XUNFEI_APP_ID", "")
    )
    xunfei_api_key: str = field(
        default_factory=lambda: os.getenv("XUNFEI_API_KEY", "")
    )
    xunfei_api_secret: str = field(
        default_factory=lambda: os.getenv("XUNFEI_API_SECRET", "")
    )

    # ============================================================
    # TTS API 配置 (InworldTTS / OpenAI TTS)
    # ============================================================
    # TTS 服务类型: "openai" 或 "inworld"
    tts_provider: str = field(
        default_factory=lambda: os.getenv("TTS_PROVIDER", "openai")
    )
    # OpenAI TTS
    tts_api_key: str = field(
        default_factory=lambda: os.getenv("TTS_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    )
    tts_base_url: str = field(
        default_factory=lambda: os.getenv("TTS_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    )
    tts_model: str = field(
        default_factory=lambda: os.getenv("TTS_MODEL", "tts-1")
    )
    tts_voice: str = field(
        default_factory=lambda: os.getenv("TTS_VOICE", "shimmer")
    )
    # InworldTTS
    inworld_api_key: str = field(
        default_factory=lambda: os.getenv("INWORLD_API_KEY", "")
    )
    inworld_voice_id: str = field(
        default_factory=lambda: os.getenv("INWORLD_VOICE_ID", "")
    )
    # TTS输出模式: "llm_output" (AI直接输出日语) 或 "translate" (翻译)
    tts_output_mode: str = field(
        default_factory=lambda: os.getenv("TTS_OUTPUT_MODE", "llm_output")
    )

    # ============================================================
    # 搜索 API 配置 (SerpAPI - 天气等)
    # ============================================================
    serpapi_api_key: str = field(
        default_factory=lambda: os.getenv("SERPAPI_API_KEY", "")
    )
    # 是否启用搜索功能
    enable_search: bool = field(
        default_factory=lambda: _get_bool("ENABLE_SEARCH", False)
    )

    # ============================================================
    # 通用设置
    # ============================================================
    max_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_TOKENS", "1000")))
    
    # API 超时和重试配置
    api_timeout: float = field(default_factory=lambda: _get_float("API_TIMEOUT", 60.0))
    api_max_retries: int = field(default_factory=lambda: _get_int("API_MAX_RETRIES", 3))

    # 日志配置
    log_pretty: bool = field(default_factory=lambda: _get_bool("LOG_PRETTY", True))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # ============================================================
    # 向后兼容
    # ============================================================
    @property
    def openai_api_key(self) -> str:
        """Backward compatibility."""
        return self.chat_api_key

    @property
    def openai_base_url(self) -> str:
        """Backward compatibility."""
        return self.chat_base_url

    @property
    def llm_model(self) -> str:
        """Backward compatibility."""
        return self.chat_model

    @property
    def voice_model(self) -> str:
        """Backward compatibility."""
        return self.tts_model

    @property
    def voice_name(self) -> str:
        """Backward compatibility."""
        return self.tts_voice

    # ============================================================
    # 配置获取方法
    # ============================================================
    def get_chat_config(self) -> APIConfig:
        """Get chat API configuration."""
        return APIConfig(
            api_key=self.chat_api_key,
            base_url=self.chat_base_url,
            model=self.chat_model,
        )

    def get_multimodal_config(self) -> APIConfig:
        """Get multimodal API configuration."""
        if self.multimodal_api_key:
            return APIConfig(
                api_key=self.multimodal_api_key,
                base_url=self.multimodal_base_url,
                model=self.multimodal_model,
            )
        # 回退到对话API
        return self.get_chat_config()
    
    def get_multimodal_mode(self) -> str:
        """Get effective multimodal mode based on configuration.
        
        Returns:
            "two_step" - 多模态分析 + 对话生成回复
            "direct" - 多模态直接回复
            "disabled" - 不支持图片/视频
        """
        mode = self.multimodal_mode.lower()
        has_chat = bool(self.chat_api_key)
        has_multimodal = bool(self.multimodal_api_key)
        
        if mode == "disabled":
            return "disabled"
        elif mode == "direct":
            if has_multimodal:
                return "direct"
            return "disabled"
        elif mode == "two_step":
            if has_chat and has_multimodal:
                return "two_step"
            elif has_multimodal:
                return "direct"
            return "disabled"
        else:  # auto
            if has_chat and has_multimodal:
                return "two_step"
            elif has_multimodal:
                return "direct"
            elif has_chat:
                return "disabled"
            return "disabled"
    
    def is_multimodal_enabled(self) -> bool:
        """Check if multimodal (image/video) support is enabled."""
        return self.get_multimodal_mode() != "disabled"

    def get_stt_config(self) -> APIConfig:
        """Get STT API configuration."""
        return APIConfig(
            api_key=self.stt_api_key,
            base_url=self.stt_base_url,
            model=self.stt_model,
        )

    def get_tts_config(self) -> APIConfig:
        """Get TTS API configuration."""
        return APIConfig(
            api_key=self.tts_api_key,
            base_url=self.tts_base_url,
            model=self.tts_model,
        )

    def is_xunfei_configured(self) -> bool:
        """Check if Xunfei STT is configured."""
        return bool(self.xunfei_app_id and self.xunfei_api_key and self.xunfei_api_secret)

    def is_inworld_configured(self) -> bool:
        """Check if InworldTTS is configured."""
        return bool(self.inworld_api_key and self.inworld_voice_id)

    def is_serpapi_configured(self) -> bool:
        """Check if SerpAPI is configured."""
        return bool(self.serpapi_api_key)

    def validate(self) -> list[str]:
        """Validate configuration and return list of missing required fields."""
        missing = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")

        if not self.chat_api_key:
            missing.append("CHAT_API_KEY (或 OPENAI_API_KEY)")

        # WEBHOOK_URL 只在 webhook 模式下必需，polling 模式不需要
        # 不再强制要求

        return missing


config = Config()

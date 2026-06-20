"""Configuration management for the bot."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from .constants import (
    DEFAULT_API_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PAIRING_TTL,
    MULTIMODAL_MODE_AUTO,
    STT_PROVIDER_OPENAI,
    TTS_OUTPUT_LLM,
    TTS_PROVIDER_OPENAI,
    VALID_MULTIMODAL_MODES,
    VALID_STT_PROVIDERS,
    VALID_TTS_OUTPUT_MODES,
    VALID_TTS_PROVIDERS,
)

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


def _validate_choice(value: str, valid_choices: set[str], field_name: str, default: str) -> str:
    """Validate that a value is within allowed choices.

    Returns the value if valid, otherwise logs a warning and returns the default.
    """
    if value not in valid_choices:
        import logging
        logging.getLogger(__name__).warning(
            f"Invalid {field_name}: '{value}', valid options: {valid_choices}. Using default: '{default}'"
        )
        return default
    return value


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
        default_factory=lambda: _get_int("PAIRING_CODE_TTL", DEFAULT_PAIRING_TTL)
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
    multimodal_mode: str = field(
        default_factory=lambda: _validate_choice(
            os.getenv("MULTIMODAL_MODE", MULTIMODAL_MODE_AUTO),
            VALID_MULTIMODAL_MODES,
            "MULTIMODAL_MODE",
            MULTIMODAL_MODE_AUTO,
        )
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
    stt_provider: str = field(
        default_factory=lambda: _validate_choice(
            os.getenv("STT_PROVIDER", STT_PROVIDER_OPENAI),
            VALID_STT_PROVIDERS,
            "STT_PROVIDER",
            STT_PROVIDER_OPENAI,
        )
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
    tts_provider: str = field(
        default_factory=lambda: _validate_choice(
            os.getenv("TTS_PROVIDER", TTS_PROVIDER_OPENAI),
            VALID_TTS_PROVIDERS,
            "TTS_PROVIDER",
            TTS_PROVIDER_OPENAI,
        )
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
    # TTS输出模式
    tts_output_mode: str = field(
        default_factory=lambda: _validate_choice(
            os.getenv("TTS_OUTPUT_MODE", TTS_OUTPUT_LLM),
            VALID_TTS_OUTPUT_MODES,
            "TTS_OUTPUT_MODE",
            TTS_OUTPUT_LLM,
        )
    )

    # ============================================================
    # 搜索 API 配置 (SerpAPI - 天气等)
    # ============================================================
    serpapi_api_key: str = field(
        default_factory=lambda: os.getenv("SERPAPI_API_KEY", "")
    )
    enable_search: bool = field(
        default_factory=lambda: _get_bool("ENABLE_SEARCH", False)
    )

    # ============================================================
    # 通用设置
    # ============================================================
    max_tokens: int = field(default_factory=lambda: _get_int("MAX_TOKENS", DEFAULT_MAX_TOKENS))

    # API 超时和重试配置
    api_timeout: float = field(default_factory=lambda: _get_float("API_TIMEOUT", DEFAULT_API_TIMEOUT))
    api_max_retries: int = field(default_factory=lambda: _get_int("API_MAX_RETRIES", DEFAULT_MAX_RETRIES))

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

        return missing

    def get_config_summary(self) -> dict[str, str]:
        """Get a summary of the current configuration status.

        Returns a dict of config categories and their status ('configured' / 'not configured').
        Useful for startup diagnostics and debugging.
        """
        return {
            "对话模型": f"{self.chat_model} @ {self.chat_base_url}" if self.chat_api_key else "未配置",
            "多模态模式": self.get_multimodal_mode(),
            "多模态模型": f"{self.multimodal_model}" if self.multimodal_api_key else "未配置",
            "STT 服务": self.stt_provider if self.stt_api_key or self.is_xunfei_configured() else "未配置",
            "TTS 服务": self.tts_provider if self.tts_api_key or self.is_inworld_configured() else "未配置",
            "TTS 输出模式": self.tts_output_mode,
            "搜索功能": "已启用" if self.enable_search and self.is_serpapi_configured() else "未启用",
            "Webhook": self.webhook_url or "未配置 (将使用 Polling)",
            "认证白名单": f"{len(self.allowed_user_ids)} 个用户" if self.allowed_user_ids else "未设置",
        }


config = Config()

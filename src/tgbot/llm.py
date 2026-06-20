"""LLM integration for generating responses."""

import asyncio
import base64
import logging

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError

from .config import config
from .constants import (
    IMAGE_MIME_TYPES,
    MAX_CONVERSATION_NAME_AUTO,
    MAX_HISTORY_MESSAGES,
    MULTIMODAL_MODE_DISABLED,
    MULTIMODAL_MODE_TWO_STEP,
)
from .database import db
from .prompts import (
    CONVERSATION_NAMING_PROMPT,
    IMAGE_ANALYSIS_PROMPT,
    MARKDOWN_ALLOWED_SUPPLEMENT,
    SYSTEM_PROMPT,
    VOICE_MODE_PROMPT,
)

logger = logging.getLogger(__name__)


def _build_system_prompt() -> str:
    """Build system prompt based on configuration."""
    prompt = SYSTEM_PROMPT
    if config.allow_markdown_output:
        prompt += MARKDOWN_ALLOWED_SUPPLEMENT
    return prompt


def is_glm_model(model: str) -> bool:
    """Check if the model is GLM series (supports URL and Base64)."""
    return model.startswith("glm-")


def is_qwen_vl_model(model: str) -> bool:
    """Check if the model is Qwen-VL series (Base64 only)."""
    return "qwen" in model.lower() and "vl" in model.lower()


def _detect_image_mime(image_data: bytes) -> str:
    """Detect image MIME type from file header bytes."""
    header = image_data[:8]
    for magic_bytes, mime_type in IMAGE_MIME_TYPES.items():
        if header[:len(magic_bytes)] == magic_bytes:
            return mime_type
    # Check WEBP separately (needs offset)
    if header[:4] == b'RIFF' and header[4:8] != b'\x00\x00\x00' and image_data[8:12] == b'WEBP':
        return "image/webp"
    return "image/jpeg"


class LLMClient:
    """Handles communication with the LLM API."""

    def __init__(self):
        chat_cfg = config.get_chat_config()
        self.chat_client = AsyncOpenAI(
            api_key=chat_cfg.api_key,
            base_url=chat_cfg.base_url,
            timeout=config.api_timeout,
        )
        self.chat_model = chat_cfg.model

        multimodal_cfg = config.get_multimodal_config()
        self.multimodal_client = AsyncOpenAI(
            api_key=multimodal_cfg.api_key,
            base_url=multimodal_cfg.base_url,
            timeout=config.api_timeout,
        )
        self.multimodal_model = multimodal_cfg.model

        self.max_retries = config.api_max_retries

    async def _call_with_retry(self, client: AsyncOpenAI, model: str, messages: list, max_tokens: int) -> str:
        """Call API with retry logic and exponential backoff."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                if not response.choices:
                    logger.warning(f"Empty response from API, retrying... (attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(1)
                    continue
                content = response.choices[0].message.content
                return content or ""
            except RateLimitError as e:
                last_error = e
                wait_time = 2 ** attempt
                logger.warning(f"Rate limit hit, waiting {wait_time}s before retry (attempt {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
            except APIConnectionError as e:
                last_error = e
                wait_time = 1 + attempt
                logger.warning(f"Connection error, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
            except APIError as e:
                last_error = e
                logger.error(f"API error: {e}")
                break
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during API call: {e}")
                break

        raise last_error or Exception("API call failed after retries")

    async def _call_multimodal(
        self,
        content: list[dict],
        system_prompt: str,
        mode: str,
    ) -> str:
        """Execute multimodal API call based on mode.

        Args:
            content: The multimodal content (image/video + text).
            system_prompt: System prompt for the API call.
            mode: "two_step" or "direct".

        Returns:
            The generated response text.
        """
        if mode == MULTIMODAL_MODE_TWO_STEP:
            # Step 1: Multimodal analysis
            description = await self._call_with_retry(
                self.multimodal_client,
                self.multimodal_model,
                [
                    {"role": "system", "content": IMAGE_ANALYSIS_PROMPT},
                    {"role": "user", "content": content}
                ],
                config.max_tokens,
            )
            logger.info(f"Description: {description}")

            # Step 2: Chat generation
            response = await self._call_with_retry(
                self.chat_client,
                self.chat_model,
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"这是内容描述：\n{description}\n\n请以丛雨的身份对此发表看法。"}
                ],
                config.max_tokens,
            )
            return response
        else:
            # Direct mode
            return await self._call_with_retry(
                self.multimodal_client,
                self.multimodal_model,
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                config.max_tokens,
            )

    async def _call_multimodal_with_fallback(
        self,
        build_content_func,
        content_args: tuple,
        system_prompt: str,
        mode: str,
    ) -> tuple[str, bool]:
        """Call multimodal API with URL fallback support.

        Args:
            build_content_func: Function to build content (_build_image_content or _build_video_content)
            content_args: Arguments for build_content_func (data, prompt_text, url)
            system_prompt: System prompt for the API call
            mode: "two_step" or "direct"

        Returns:
            tuple: (response, used_url) - API response and whether URL was used
        """
        multimodal_content, used_url = build_content_func(*content_args)

        try:
            response = await self._call_multimodal(multimodal_content, system_prompt, mode)
            return response, used_url

        except Exception as e:
            if not used_url:
                raise

            # URL failed, fall back to Base64
            logger.warning(f"URL failed, falling back to Base64: {e}")
            config._url_fallback_needed = True
            new_args = (content_args[0], content_args[1], None)
            multimodal_content, _ = build_content_func(*new_args)
            response = await self._call_multimodal(multimodal_content, system_prompt, mode)
            return response, False

    def _get_or_create_conversation(self, user_id: int) -> int:
        """Get or create active conversation for user."""
        db.ensure_user_settings(user_id)

        conv_id = db.get_active_conversation(user_id)
        if conv_id:
            conv = db.get_conversation(conv_id)
            if conv and conv.is_active:
                return conv_id

        conv = db.create_conversation(user_id, "新对话")
        db.set_active_conversation(user_id, conv.id)
        logger.info(f"Created new conversation {conv.id} for user {user_id}")
        return conv.id

    def _get_history(self, conversation_id: int) -> list[dict]:
        """Get conversation history with system prompt."""
        messages = db.get_messages(conversation_id, limit=MAX_HISTORY_MESSAGES)
        history = [{"role": "system", "content": _build_system_prompt()}]
        history.extend(messages)
        return history

    def create_new_conversation(self, user_id: int, name: str = "新对话") -> int:
        """Create a new conversation for user."""
        conv = db.create_conversation(user_id, name)
        db.set_active_conversation(user_id, conv.id)
        logger.info(f"Created new conversation {conv.id} for user {user_id}")
        return conv.id

    def switch_conversation(self, user_id: int, conv_id: int) -> bool:
        """Switch to a specific conversation."""
        conv = db.get_conversation(conv_id)
        if conv and conv.user_id == user_id and conv.is_active:
            db.set_active_conversation(user_id, conv_id)
            logger.info(f"User {user_id} switched to conversation {conv_id}")
            return True
        return False

    def clear_conversation(self, user_id: int) -> bool:
        """Clear current conversation history."""
        conv_id = db.get_active_conversation(user_id)
        if conv_id:
            db.clear_messages(conv_id)
            logger.info(f"Cleared conversation {conv_id} for user {user_id}")
            return True
        return False

    async def generate_response(self, user_id: int, text: str) -> str:
        """Generate a response for the given text using chat API."""
        conv_id = self._get_or_create_conversation(user_id)
        history = self._get_history(conv_id)
        history.append({"role": "user", "content": text})

        assistant_message = await self._call_with_retry(
            self.chat_client, self.chat_model, history, config.max_tokens
        )

        db.add_message(conv_id, "user", text)
        db.add_message(conv_id, "assistant", assistant_message)

        return assistant_message

    async def generate_response_with_japanese(self, user_id: int, text: str) -> str:
        """Generate a response with both Chinese and Japanese for voice mode."""
        from .voice import extract_chinese

        conv_id = self._get_or_create_conversation(user_id)

        voice_system_prompt = _build_system_prompt() + VOICE_MODE_PROMPT
        temp_history = [{"role": "system", "content": voice_system_prompt}]

        messages = db.get_messages(conv_id, limit=MAX_HISTORY_MESSAGES)
        temp_history.extend(messages)
        temp_history.append({"role": "user", "content": text})

        result = await self._call_with_retry(
            self.chat_client, self.chat_model, temp_history, config.max_tokens
        )

        chinese_only = extract_chinese(result) or result
        db.add_message(conv_id, "user", text)
        db.add_message(conv_id, "assistant", chinese_only)

        return result

    async def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio data to text using STT API."""
        from .voice import transcribe_audio
        return await transcribe_audio(audio_data)

    def _build_image_content(
        self,
        image_data: bytes,
        prompt_text: str = "请以丛雨的身份对这张图片发表看法。",
        image_url: str | None = None,
    ) -> tuple[list[dict], bool]:
        """Build multimodal content for image analysis.

        Returns:
            tuple: (content, used_url) - content list and whether URL was used
        """
        content = [{"type": "text", "text": prompt_text}]
        used_url = False

        model = self.multimodal_model
        mime_type = _detect_image_mime(image_data)

        if image_url and is_glm_model(model) and not config.force_base64_image:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })
            used_url = True
            logger.info("Using image URL for GLM model")
        else:
            base64_image = base64.b64encode(image_data).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}"
                }
            })
            if image_url and not is_glm_model(model):
                logger.info(f"Model {model} doesn't support URL, using Base64")
            elif config.force_base64_image:
                logger.info("Force Base64 mode enabled")

        return content, used_url

    def _build_video_content(
        self,
        video_data: bytes,
        prompt_text: str = "请以丛雨的身份对这个视频发表看法。",
        video_url: str | None = None,
    ) -> tuple[list[dict], bool]:
        """Build multimodal content for video analysis.

        Returns:
            tuple: (content, used_url) - content list and whether URL was used
        """
        content = [{"type": "text", "text": prompt_text}]
        used_url = False

        model = self.multimodal_model

        if video_url and is_glm_model(model) and not config.force_base64_image:
            content.append({
                "type": "video_url",
                "video_url": {"url": video_url}
            })
            used_url = True
            logger.info("Using video URL for GLM model")
        else:
            base64_video = base64.b64encode(video_data).decode("utf-8")
            content.append({
                "type": "video_url",
                "video_url": {
                    "url": f"data:video/mp4;base64,{base64_video}"
                }
            })
            if video_url and not is_glm_model(model):
                logger.info(f"Model {model} doesn't support URL, using Base64")
            elif config.force_base64_image:
                logger.info("Force Base64 mode enabled")

        return content, used_url

    async def analyze_image(
        self,
        user_id: int,
        image_data: bytes,
        caption: str | None = None,
        image_url: str | None = None,
    ) -> str:
        """Analyze an image and generate a response."""
        conv_id = self._get_or_create_conversation(user_id)
        mode = config.get_multimodal_mode()

        if mode == MULTIMODAL_MODE_DISABLED:
            return "唔……我看不到图片呢 (；´д｀)\n请联系管理员配置多模态功能。"

        analyze_prompt = "请详细描述这张图片的内容，包括场景、人物、物品、氛围等。"
        if caption:
            analyze_prompt = f"图片说明: {caption}\n{analyze_prompt}"

        response, _ = await self._call_multimodal_with_fallback(
            self._build_image_content,
            (image_data, analyze_prompt, image_url),
            _build_system_prompt(),
            mode,
        )

        logger.info(f"AI response: {response}")
        db.add_message(conv_id, "user", f"[图片]{caption or ''}")
        db.add_message(conv_id, "assistant", response)

        return response

    async def analyze_image_with_japanese(
        self,
        user_id: int,
        image_data: bytes,
        caption: str | None = None,
        image_url: str | None = None,
    ) -> str:
        """Analyze an image and generate response with Chinese and Japanese for voice mode."""
        from .voice import extract_chinese

        conv_id = self._get_or_create_conversation(user_id)
        mode = config.get_multimodal_mode()

        if mode == MULTIMODAL_MODE_DISABLED:
            return "唔……我看不到图片呢 (；´д｀)\n请联系管理员配置多模态功能。"

        analyze_prompt = "请详细描述这张图片的内容，包括场景、人物、物品、氛围等。"
        if caption:
            analyze_prompt = f"图片说明: {caption}\n{analyze_prompt}"

        system_prompt = _build_system_prompt() + VOICE_MODE_PROMPT
        result, _ = await self._call_multimodal_with_fallback(
            self._build_image_content,
            (image_data, analyze_prompt, image_url),
            system_prompt,
            mode,
        )

        logger.info(f"AI response: {result}")

        chinese_only = extract_chinese(result) or result
        db.add_message(conv_id, "user", f"[图片]{caption or ''}")
        db.add_message(conv_id, "assistant", chinese_only)

        return result

    async def analyze_video(
        self,
        user_id: int,
        video_data: bytes,
        caption: str | None = None,
        video_url: str | None = None,
    ) -> str:
        """Analyze a video and generate a response."""
        conv_id = self._get_or_create_conversation(user_id)
        mode = config.get_multimodal_mode()

        if mode == MULTIMODAL_MODE_DISABLED:
            return "唔……我看不到视频呢 (；´д｀)\n请联系管理员配置多模态功能。"

        analyze_prompt = "请详细描述这个视频的内容，包括场景、人物、动作、氛围等。"
        if caption:
            analyze_prompt = f"视频说明: {caption}\n{analyze_prompt}"

        response, _ = await self._call_multimodal_with_fallback(
            self._build_video_content,
            (video_data, analyze_prompt, video_url),
            _build_system_prompt(),
            mode,
        )

        logger.info(f"AI response: {response}")
        db.add_message(conv_id, "user", f"[视频]{caption or ''}")
        db.add_message(conv_id, "assistant", response)

        return response

    async def generate_conversation_name(self, first_message: str) -> str:
        """Generate a name for a conversation based on the first message."""
        try:
            result = await self._call_with_retry(
                self.chat_client,
                self.chat_model,
                [
                    {
                        "role": "system",
                        "content": CONVERSATION_NAMING_PROMPT
                    },
                    {
                        "role": "user",
                        "content": f"请为以下对话生成一个简短的名称：\n{first_message[:200]}"
                    }
                ],
                20,
            )
            name = result.strip().strip('"\'').strip()
            if len(name) > MAX_CONVERSATION_NAME_AUTO:
                name = name[:MAX_CONVERSATION_NAME_AUTO]
            return name
        except Exception as e:
            logger.error(f"Error generating conversation name: {e}")
            return "新对话"


# Global LLM client instance
llm_client = LLMClient()

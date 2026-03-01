"""LLM integration for generating responses."""

import asyncio
import base64
import logging
from typing import Optional

from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError

from .config import config
from .database import db
from .prompts import SYSTEM_PROMPT, VOICE_MODE_PROMPT

logger = logging.getLogger(__name__)


def is_glm_model(model: str) -> bool:
    """Check if the model is GLM series (supports URL and Base64)."""
    return model.startswith("glm-")


def is_qwen_vl_model(model: str) -> bool:
    """Check if the model is Qwen-VL series (Base64 only)."""
    return "qwen" in model.lower() and "vl" in model.lower()


class LLMClient:
    """Handles communication with the LLM API."""

    def __init__(self):
        # 对话客户端 (DeepSeek / OpenAI)
        chat_cfg = config.get_chat_config()
        self.chat_client = AsyncOpenAI(
            api_key=chat_cfg.api_key,
            base_url=chat_cfg.base_url,
            timeout=config.api_timeout,
        )
        self.chat_model = chat_cfg.model

        # 多模态客户端 (无问芯穹 / OpenAI Vision)
        multimodal_cfg = config.get_multimodal_config()
        self.multimodal_client = AsyncOpenAI(
            api_key=multimodal_cfg.api_key,
            base_url=multimodal_cfg.base_url,
            timeout=config.api_timeout,
        )
        self.multimodal_model = multimodal_cfg.model
        
        self.max_retries = config.api_max_retries

    async def _call_with_retry(self, client: AsyncOpenAI, model: str, messages: list, max_tokens: int) -> str:
        """Call API with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                # 检查响应是否有效
                if not response.choices:
                    logger.warning(f"Empty response from API, retrying... (attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(1)
                    continue
                content = response.choices[0].message.content
                return content or ""
            except RateLimitError as e:
                last_error = e
                wait_time = 2 ** attempt  # 指数退避
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
                break  # API 错误不重试
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during API call: {e}")
                break
        
        raise last_error or Exception("API call failed after retries")

    def _get_or_create_conversation(self, user_id: int) -> int:
        """Get or create active conversation for user."""
        db.ensure_user_settings(user_id)
        
        conv_id = db.get_active_conversation(user_id)
        if conv_id:
            # 检查对话是否存在且活跃
            conv = db.get_conversation(conv_id)
            if conv and conv.is_active:
                return conv_id
        
        # 创建新对话
        conv = db.create_conversation(user_id, "新对话")
        db.set_active_conversation(user_id, conv.id)
        logger.info(f"Created new conversation {conv.id} for user {user_id}")
        return conv.id

    def _get_history(self, conversation_id: int) -> list[dict]:
        """Get conversation history."""
        messages = db.get_messages(conversation_id)
        history = [{"role": "system", "content": SYSTEM_PROMPT}]
        history.extend(messages)
        return history

    async def _call_multimodal_with_fallback(
        self,
        build_content_func,
        content_args: tuple,
        system_prompt: str,
        mode: str,
        image_description: str = None,
    ) -> tuple[str, bool]:
        """Call multimodal API with URL fallback support.
        
        Args:
            build_content_func: Function to build content (_build_image_content or _build_video_content)
            content_args: Arguments for build_content_func (data, prompt_text, url)
            system_prompt: System prompt for the API call
            mode: "two_step" or "direct"
            image_description: Description from first step (for two_step mode)
        
        Returns:
            tuple: (response, used_url) - API response and whether URL was used
        """
        multimodal_content, used_url = build_content_func(*content_args)
        
        try:
            if mode == "two_step":
                # 第一步：多模态分析
                description = await self._call_with_retry(
                    self.multimodal_client,
                    self.multimodal_model,
                    [
                        {"role": "system", "content": "你是一个图像分析助手，请客观详细地描述图片内容。"},
                        {"role": "user", "content": multimodal_content}
                    ],
                    config.max_tokens,
                )
                logger.info(f"Description: {description}")
                
                # 第二步：对话生成
                response = await self._call_with_retry(
                    self.chat_client,
                    self.chat_model,
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"这是内容描述：\n{description}\n\n请以丛雨的身份对此发表看法。"}
                    ],
                    config.max_tokens,
                )
            else:
                # 直接模式
                response = await self._call_with_retry(
                    self.multimodal_client,
                    self.multimodal_model,
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": multimodal_content}
                    ],
                    config.max_tokens,
                )
            return response, used_url
            
        except Exception as e:
            # URL 失败时回退到 Base64
            if used_url:
                logger.warning(f"URL failed, falling back to Base64: {e}")
                config._url_fallback_needed = True
                # 重建内容，不使用 URL
                new_args = (content_args[0], content_args[1], None)
                multimodal_content, _ = build_content_func(*new_args)
                
                if mode == "two_step":
                    description = await self._call_with_retry(
                        self.multimodal_client,
                        self.multimodal_model,
                        [
                            {"role": "system", "content": "你是一个图像分析助手，请客观详细地描述图片内容。"},
                            {"role": "user", "content": multimodal_content}
                        ],
                        config.max_tokens,
                    )
                    logger.info(f"Description (base64 fallback): {description}")
                    response = await self._call_with_retry(
                        self.chat_client,
                        self.chat_model,
                        [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"这是内容描述：\n{description}\n\n请以丛雨的身份对此发表看法。"}
                        ],
                        config.max_tokens,
                    )
                else:
                    response = await self._call_with_retry(
                        self.multimodal_client,
                        self.multimodal_model,
                        [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": multimodal_content}
                        ],
                        config.max_tokens,
                    )
                return response, False
            raise

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

    async def generate_response(
        self,
        user_id: int,
        text: str,
    ) -> str:
        """Generate a response for the given text using chat API."""
        conv_id = self._get_or_create_conversation(user_id)
        history = self._get_history(conv_id)
        
        # 添加用户消息
        history.append({"role": "user", "content": text})

        assistant_message = await self._call_with_retry(
            self.chat_client, self.chat_model, history, config.max_tokens
        )
        
        # 保存消息到数据库
        db.add_message(conv_id, "user", text)
        db.add_message(conv_id, "assistant", assistant_message)

        return assistant_message

    async def generate_response_with_japanese(
        self,
        user_id: int,
        text: str,
    ) -> str:
        """Generate a response with both Chinese and Japanese for voice mode."""
        conv_id = self._get_or_create_conversation(user_id)
        
        # 构建临时历史（包含语音模式提示）
        voice_system_prompt = SYSTEM_PROMPT + VOICE_MODE_PROMPT
        temp_history = [{"role": "system", "content": voice_system_prompt}]
        
        # 添加用户历史
        messages = db.get_messages(conv_id)
        temp_history.extend(messages)
        temp_history.append({"role": "user", "content": text})

        result = await self._call_with_retry(
            self.chat_client, self.chat_model, temp_history, config.max_tokens
        )
        
        # 更新实际历史（只保存中文部分）
        from .voice import extract_chinese
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
        image_url: Optional[str] = None,
    ) -> tuple[list[dict], bool]:
        """Build multimodal content for image analysis.
        
        Returns:
            tuple: (content, used_url) - content 列表和是否使用了 URL
        """
        content = [{"type": "text", "text": prompt_text}]
        used_url = False

        model = self.multimodal_model
        
        # 检测图片格式
        header = image_data[:8]
        if header[:3] == b'\xff\xd8\xff':
            mime_type = "image/jpeg"
        elif header[:4] == b'\x89PNG':
            mime_type = "image/png"
        elif header[:6] in (b'GIF87a', b'GIF89a'):
            mime_type = "image/gif"
        elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            mime_type = "image/webp"
        else:
            mime_type = "image/jpeg"  # 默认
        
        # 优先使用 URL（如果有且模型支持）
        if image_url and is_glm_model(model) and not config.force_base64_image:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })
            used_url = True
            logger.info(f"Using image URL for GLM model")
        else:
            # 使用 Base64（GLM 和 Qwen 都支持）
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
        video_url: Optional[str] = None,
    ) -> tuple[list[dict], bool]:
        """Build multimodal content for video analysis.
        
        Returns:
            tuple: (content, used_url) - content 列表和是否使用了 URL
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
            logger.info(f"Using video URL for GLM model")
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
        caption: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> str:
        """Analyze an image and generate a response.
        
        Modes:
        - two_step: Multimodal AI analyzes -> Chat AI generates response
        - direct: Multimodal AI directly responds
        """
        from .prompts import SYSTEM_PROMPT
        conv_id = self._get_or_create_conversation(user_id)
        mode = config.get_multimodal_mode()
        
        if mode == "disabled":
            return "唔……我看不到图片呢 (；´д｀)\n请联系管理员配置多模态功能。"
        
        # 构建提示词
        analyze_prompt = "请详细描述这张图片的内容，包括场景、人物、物品、氛围等。"
        if caption:
            analyze_prompt = f"图片说明: {caption}\n{analyze_prompt}"
        
        # 调用封装的方法
        response, _ = await self._call_multimodal_with_fallback(
            self._build_image_content,
            (image_data, analyze_prompt, image_url),
            SYSTEM_PROMPT,
            mode,
        )
        
        logger.info(f"AI response: {response}")
        
        # 保存消息
        db.add_message(conv_id, "user", f"[图片]{caption or ''}")
        db.add_message(conv_id, "assistant", response)

        return response

    async def analyze_image_with_japanese(
        self,
        user_id: int,
        image_data: bytes,
        caption: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> str:
        """Analyze an image and generate response with Chinese and Japanese for voice mode."""
        from .prompts import SYSTEM_PROMPT, VOICE_MODE_PROMPT
        conv_id = self._get_or_create_conversation(user_id)
        mode = config.get_multimodal_mode()
        
        if mode == "disabled":
            return "唔……我看不到图片呢 (；´д｀)\n请联系管理员配置多模态功能。"
        
        # 构建提示词
        analyze_prompt = "请详细描述这张图片的内容，包括场景、人物、物品、氛围等。"
        if caption:
            analyze_prompt = f"图片说明: {caption}\n{analyze_prompt}"
        
        # 调用封装的方法
        system_prompt = SYSTEM_PROMPT + VOICE_MODE_PROMPT
        result, _ = await self._call_multimodal_with_fallback(
            self._build_image_content,
            (image_data, analyze_prompt, image_url),
            system_prompt,
            mode,
        )
        
        logger.info(f"AI response: {result}")
        
        # 保存消息（只保存中文部分）
        from .voice import extract_chinese
        chinese_only = extract_chinese(result) or result
        db.add_message(conv_id, "user", f"[图片]{caption or ''}")
        db.add_message(conv_id, "assistant", chinese_only)

        return result

    async def analyze_video(
        self,
        user_id: int,
        video_data: bytes,
        caption: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> str:
        """Analyze a video and generate a response."""
        from .prompts import SYSTEM_PROMPT
        conv_id = self._get_or_create_conversation(user_id)
        mode = config.get_multimodal_mode()
        
        if mode == "disabled":
            return "唔……我看不到视频呢 (；´д｀)\n请联系管理员配置多模态功能。"
        
        # 构建提示词
        analyze_prompt = "请详细描述这个视频的内容，包括场景、人物、动作、氛围等。"
        if caption:
            analyze_prompt = f"视频说明: {caption}\n{analyze_prompt}"
        
        # 调用封装的方法
        response, _ = await self._call_multimodal_with_fallback(
            self._build_video_content,
            (video_data, analyze_prompt, video_url),
            SYSTEM_PROMPT,
            mode,
        )
        
        logger.info(f"AI response: {response}")
        
        # 保存消息
        db.add_message(conv_id, "user", f"[视频]{caption or ''}")
        db.add_message(conv_id, "assistant", response)

        return response

    async def process_voice_message(
        self,
        user_id: int,
        transcript: str,
    ) -> str:
        """Process transcribed voice and generate response."""
        return await self.generate_response(user_id, transcript)

    async def generate_conversation_name(self, first_message: str) -> str:
        """Generate a name for a conversation based on the first message."""
        try:
            result = await self._call_with_retry(
                self.chat_client,
                self.chat_model,
                [
                    {
                        "role": "system", 
                        "content": "你是一个对话命名助手。根据用户的第一条消息，生成一个简短的对话名称（不超过10个字）。只返回名称，不要其他内容。"
                    },
                    {
                        "role": "user", 
                        "content": f"请为以下对话生成一个简短的名称：\n{first_message[:200]}"
                    }
                ],
                20,
            )
            # 清理名称，移除引号等
            name = result.strip().strip('"\'').strip()
            if len(name) > 20:
                name = name[:20]
            return name
        except Exception as e:
            logger.error(f"Error generating conversation name: {e}")
            return "新对话"


# Global LLM client instance
llm_client = LLMClient()
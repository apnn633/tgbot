"""Voice processing utilities."""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import re
import subprocess
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import httpx
from openai import APIError, AsyncOpenAI

from .config import config
from .prompts import TRANSLATION_PROMPT

logger = logging.getLogger(__name__)

# 客户端缓存（避免每次调用都创建新客户端）
_chat_client: AsyncOpenAI | None = None
_tts_client: AsyncOpenAI | None = None
_stt_client: AsyncOpenAI | None = None


def _get_chat_client() -> AsyncOpenAI:
    """Get or create chat API client."""
    global _chat_client
    if _chat_client is None:
        chat_cfg = config.get_chat_config()
        _chat_client = AsyncOpenAI(
            api_key=chat_cfg.api_key,
            base_url=chat_cfg.base_url,
            timeout=config.api_timeout,
        )
    return _chat_client


def _get_tts_client() -> AsyncOpenAI:
    """Get or create TTS API client."""
    global _tts_client
    if _tts_client is None:
        tts_cfg = config.get_tts_config()
        _tts_client = AsyncOpenAI(
            api_key=tts_cfg.api_key,
            base_url=tts_cfg.base_url,
            timeout=config.api_timeout,
        )
    return _tts_client


def _get_stt_client() -> AsyncOpenAI:
    """Get or create STT API client."""
    global _stt_client
    if _stt_client is None:
        stt_cfg = config.get_stt_config()
        _stt_client = AsyncOpenAI(
            api_key=stt_cfg.api_key,
            base_url=stt_cfg.base_url,
            timeout=config.api_timeout,
        )
    return _stt_client


def extract_japanese(text: str) -> str | None:
    """Extract Japanese text from LLM output.

    Supports both JSON format and XML tag format.
    JSON format: {"zh": "...", "ja": "..."}
    XML format: <ja>...</ja>
    """
    # 尝试 JSON 格式
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "ja" in data:
            return data["ja"]
    except json.JSONDecodeError:
        pass

    # 回退到 XML 标签格式
    match = re.search(r"<ja>\s*(.+?)\s*</ja>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def extract_chinese(text: str) -> str | None:
    """Extract Chinese text from LLM output.

    Supports both JSON format and XML tag format.
    JSON format: {"zh": "...", "ja": "..."}
    XML format: <zh>...</zh>

    Returns None if no valid format found.
    """
    # 尝试 JSON 格式
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "zh" in data:
            return data["zh"]
    except json.JSONDecodeError:
        pass

    # 回退到 XML 标签格式
    match = re.search(r"<zh>\s*(.+?)\s*</zh>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def has_correct_format(text: str) -> bool:
    """Check if text has valid output format (JSON or XML)."""
    # 检查 JSON 格式
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "zh" in data and "ja" in data:
            return True
    except json.JSONDecodeError:
        pass

    # 检查 XML 格式
    return bool(re.search(r"<zh>.+?</zh>", text, re.DOTALL)) and \
           bool(re.search(r"<ja>.+?</ja>", text, re.DOTALL))


async def translate_to_japanese(text: str) -> str:
    """Translate Chinese text to Japanese using LLM."""
    client = _get_chat_client()

    try:
        response = await client.chat.completions.create(
            model=config.get_chat_config().model,
            messages=[
                {"role": "system", "content": TRANSLATION_PROMPT},
                {"role": "user", "content": text}
            ],
            max_tokens=500,
        )
        return response.choices[0].message.content or text
    except APIError as e:
        logger.error(f"API error during translation: {e}")
        return text
    except Exception as e:
        logger.error(f"Unexpected error during translation: {e}")
        return text


# ============================================================
# TTS: OpenAI TTS
# ============================================================
async def generate_voice_openai(text: str) -> bytes:
    """Generate voice using OpenAI TTS."""
    client = _get_tts_client()
    tts_cfg = config.get_tts_config()

    try:
        response = await client.audio.speech.create(
            model=tts_cfg.model,
            voice=config.tts_voice,
            input=text,
            response_format="ogg",
        )
        return response.content
    except APIError as e:
        logger.error(f"TTS API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during TTS: {e}")
        raise


# ============================================================
# TTS: InworldTTS (日语克隆)
# 文档: https://docs.inworld.ai/docs/tts/voice-cloning
# API: https://docs.inworld.ai/api-reference/ttsAPI/texttospeech/synthesize-speech
# ============================================================
async def generate_voice_inworld(text: str) -> bytes:
    """Generate voice using InworldTTS API.

    InworldTTS支持即时语音克隆，需要先在Portal创建语音获取voiceId。

    配置步骤:
    1. 访问 https://inworld.ai 注册账号
    2. Portal → Settings → API Keys → 复制 Base64 credentials
    3. Portal → TTS Playground → Create Voice → Clone (上传5-15秒音频)
    4. 获取 voiceId

    API支持12种语言，48kHz音频输出。
    """
    if not config.is_inworld_configured():
        raise ValueError("InworldTTS not configured")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # InworldTTS API 端点
            response = await client.post(
                "https://api.inworld.ai/tts/v1/voice",
                headers={
                    "Authorization": f"Basic {config.inworld_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "voice_id": config.inworld_voice_id,
                    "model_id": "inworld-tts-1.5-mini",
                    "audio_config": {
                        "audio_encoding": "OGG_OPUS",
                        "sample_rate_hertz": 48000,
                    },
                },
            )
            response.raise_for_status()

            # 返回音频数据
            result = response.json()
            if "audioContent" in result:
                return base64.b64decode(result["audioContent"])
            else:
                logger.error(f"InworldTTS response missing audioContent: {result}")
                raise ValueError("InworldTTS response missing audioContent")
    except httpx.HTTPStatusError as e:
        logger.error(f"InworldTTS HTTP error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during InworldTTS: {e}")
        raise


# ============================================================
# TTS: 统一入口
# ============================================================
async def generate_voice_japanese(text: str, japanese_text: str | None = None) -> bytes:
    """Generate Japanese voice audio."""
    try:
        if japanese_text:
            target_text = japanese_text
        elif config.tts_output_mode == "translate":
            target_text = await translate_to_japanese(text)
        else:
            extracted = extract_japanese(text)
            if extracted:
                target_text = extracted
            else:
                target_text = await translate_to_japanese(text)

        if config.tts_provider == "inworld" and config.is_inworld_configured():
            return await generate_voice_inworld(target_text)
        else:
            return await generate_voice_openai(target_text)
    except Exception as e:
        logger.error(f"Error generating voice: {e}")
        raise


# ============================================================
# STT: OpenAI Whisper
# ============================================================
async def transcribe_openai(audio_data: bytes) -> str:
    """Transcribe audio using OpenAI Whisper."""
    client = _get_stt_client()
    stt_cfg = config.get_stt_config()

    try:
        audio_file = BytesIO(audio_data)
        audio_file.name = "audio.ogg"

        response = await client.audio.transcriptions.create(
            model=stt_cfg.model,
            file=audio_file,
            language="auto",
        )
        return response.text
    except APIError as e:
        logger.error(f"Whisper API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during transcription: {e}")
        raise


# ============================================================
# STT: 讯飞语音听写（流式版）WebAPI
# 文档: https://www.xfyun.cn/doc/asr/voicedictation/API.html
# ============================================================
async def transcribe_xunfei(audio_data: bytes) -> str:
    """Transcribe audio using Xunfei (讯飞) 语音听写流式版API.

    支持60秒以内音频，支持中文、英文及方言。
    音频格式: pcm, speex, speex-wb, mp3 (仅中文和英文)
    采样率: 16k 或 8k
    """
    import websockets

    if not config.is_xunfei_configured():
        raise ValueError("Xunfei STT not configured")

    # ========== 生成鉴权URL ==========
    host = "iat-api.xfyun.cn"
    path = "/v2/iat"

    # 生成RFC1123格式时间戳
    now = datetime.utcnow()
    date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    # 生成签名
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        config.xunfei_api_secret.encode(),
        signature_origin.encode(),
        hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode()

    # authorization_origin格式
    authorization_origin = f'api_key="{config.xunfei_api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    authorization = base64.b64encode(authorization_origin.encode()).decode()

    # 构建WebSocket URL
    ws_url = f"wss://{host}{path}?authorization={authorization}&date={quote(date)}&host={host}"

    # ========== 音频转码 ==========
    # 讯飞需要 16kHz 16bit 单声道 PCM
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    pcm_path = tmp_path.replace(".ogg", ".pcm")

    try:
        subprocess.run(
            ["ffmpeg", "-i", tmp_path, "-f", "s16le", "-ar", "16000", "-ac", "1", "-y", pcm_path],
            check=True,
            capture_output=True,
        )

        with open(pcm_path, "rb") as f:
            pcm_data = f.read()
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else 'unknown'}")
        raise RuntimeError(f"Audio conversion failed: {e}") from None
    finally:
        Path(tmp_path).unlink(missing_ok=True)
        Path(pcm_path).unlink(missing_ok=True)

    # ========== WebSocket通信 ==========
    result_text = ""
    frame_size = 1280
    frame_interval = 0.04

    try:
        async with websockets.connect(ws_url, open_timeout=30) as ws:
            total_len = len(pcm_data)

            for i in range(0, total_len, frame_size):
                frame = pcm_data[i : i + frame_size]

                # 确定帧状态: 0=首帧, 1=中间帧, 2=最后一帧
                if i == 0:
                    status = 0
                elif i + frame_size >= total_len:
                    status = 2
                else:
                    status = 1

                # 构建请求数据
                if status == 0:
                    data = {
                        "common": {"app_id": config.xunfei_app_id},
                        "business": {
                            "language": "zh_cn",
                            "domain": "iat",
                            "accent": "mandarin",
                            "vad_eos": 6000,
                            "ptt": 1
                        },
                        "data": {
                            "status": 0,
                            "format": "audio/L16;rate=16000",
                            "encoding": "raw",
                            "audio": base64.b64encode(frame).decode()
                        }
                    }
                elif status == 2:
                    data = {
                        "data": {
                            "status": 2,
                            "format": "audio/L16;rate=16000",
                            "encoding": "raw",
                            "audio": ""
                        }
                    }
                else:
                    data = {
                        "data": {
                            "status": 1,
                            "format": "audio/L16;rate=16000",
                            "encoding": "raw",
                            "audio": base64.b64encode(frame).decode()
                        }
                    }

                await ws.send(json.dumps(data))
                await asyncio.sleep(frame_interval)

                # 接收结果
                try:
                    while True:
                        response = await asyncio.wait_for(ws.recv(), timeout=0.5)
                        result = json.loads(response)

                        if result.get("code") == 0:
                            data_result = result.get("data", {})
                            if "result" in data_result:
                                result_obj = data_result["result"]
                                for ws_item in result_obj.get("ws", []):
                                    for cw in ws_item.get("cw", []):
                                        result_text += cw.get("w", "")
                        else:
                            error_msg = result.get("message", "Unknown error")
                            logger.error(f"Xunfei STT error: {error_msg}")
                            raise Exception(f"Xunfei STT error: {error_msg}")

                except TimeoutError:
                    pass
    except Exception as e:
        logger.error(f"Xunfei STT WebSocket error: {e}")
        raise

    return result_text


# ============================================================
# STT: 统一入口
# ============================================================
async def transcribe_audio(audio_data: bytes) -> str:
    """Transcribe audio to text.

    Routes to appropriate STT provider based on config.
    """
    try:
        if config.stt_provider == "xunfei" and config.is_xunfei_configured():
            return await transcribe_xunfei(audio_data)
        else:
            return await transcribe_openai(audio_data)
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise


# ============================================================
# 工具函数
# ============================================================
async def convert_ogg_to_wav(ogg_data: bytes) -> bytes:
    """Convert OGG audio to WAV format."""
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_file:
        ogg_file.write(ogg_data)
        ogg_path = ogg_file.name

    wav_path = ogg_path.replace(".ogg", ".wav")

    try:
        subprocess.run(
            ["ffmpeg", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
            check=True,
            capture_output=True,
        )

        with open(wav_path, "rb") as f:
            return f.read()
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg conversion error: {e.stderr.decode() if e.stderr else 'unknown'}")
        raise RuntimeError(f"Audio conversion failed: {e}") from None
    finally:
        Path(ogg_path).unlink(missing_ok=True)
        Path(wav_path).unlink(missing_ok=True)

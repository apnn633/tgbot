"""Utility functions for the bot."""

import asyncio
import re
from typing import AsyncGenerator


def split_message(text: str, max_length: int = 150) -> list[str]:
    """Split a message into smaller chunks for natural conversation flow.
    
    Tries to split at sentence boundaries (supports Chinese and Japanese).
    
    Args:
        text: The text to split.
        max_length: Maximum length of each chunk. Defaults to 150.
    
    Returns:
        A list of text chunks.
    """
    if not text:
        return []

    # 先按换行符分段
    lines = text.split('\n')
    result: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 如果单行超过最大长度，按句子分割
        if len(line) > max_length:
            # 中文和日文的句子结束符
            sentence_endings = re.compile(r'(?<=[。！？!?\.])')
            sentences = [s.strip() for s in sentence_endings.split(line) if s.strip()]

            current_chunk = ""
            for sentence in sentences:
                if current_chunk and len(current_chunk) + len(sentence) > max_length:
                    result.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    if current_chunk:
                        current_chunk += sentence
                    else:
                        current_chunk = sentence

            if current_chunk:
                result.append(current_chunk.strip())
        else:
            result.append(line)

    return result


async def message_generator(text: str, delay: float = 0.8) -> AsyncGenerator[str, None]:
    """Generate message chunks with delays for natural conversation flow.
    
    Args:
        text: The text to generate chunks from.
        delay: Delay between chunks in seconds. Defaults to 0.8.
    
    Yields:
        Text chunks with delays between them.
    """
    chunks = split_message(text)

    for i, chunk in enumerate(chunks):
        if i > 0:
            await asyncio.sleep(delay)
        yield chunk


def is_allowed_user(user_id: int, allowed_ids: list[int] | None) -> bool:
    """Check if user is allowed to use the bot.
    
    Args:
        user_id: The Telegram user ID to check.
        allowed_ids: List of allowed user IDs. If None or empty, all users are allowed.
    
    Returns:
        True if the user is allowed, False otherwise.
    """
    if not allowed_ids:
        return True  # Allow all users if no restriction
    return user_id in allowed_ids


def format_user_info(user) -> str:
    """Format user information for logging.
    
    Args:
        user: A Telegram User object.
    
    Returns:
        A formatted string with user information.
    """
    name = user.full_name
    username = f"@{user.username}" if user.username else "no username"
    return f"{name} ({username}, ID: {user.id})"

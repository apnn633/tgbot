"""Main bot application with webhook support."""

import logging
from typing import Optional

from telegram import Bot, BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import config
from .handlers import (
    clear_command,
    delete_all_command,
    delete_conversation_command,
    fix_command,
    handle_photo,
    handle_text,
    handle_video,
    handle_voice,
    help_command,
    list_conversations_command,
    new_conversation_command,
    rename_conversation_command,
    reset_command,
    start_command,
    voice_mode_command,
)

logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot) -> None:
    """Set bot command menu."""
    commands = [
        BotCommand("start", "开始使用/获取配对码"),
        BotCommand("help", "查看帮助"),
        BotCommand("new", "新建对话"),
        BotCommand("list", "对话列表"),
        BotCommand("det", "删除对话"),
        BotCommand("delall", "删除所有对话"),
        BotCommand("clear", "清空当前对话"),
        BotCommand("rename", "重命名对话"),
        BotCommand("voice", "切换语音模式"),
        BotCommand("reset", "恢复出厂设置"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Bot commands menu set")


def create_application() -> Application:
    """Create and configure the bot application."""
    # Validate configuration
    missing = config.validate()
    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")

    # Create application
    application = Application.builder().token(config.telegram_bot_token).build()

    # Add handlers
    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("fix", fix_command))
    application.add_handler(CommandHandler("new", new_conversation_command))
    application.add_handler(CommandHandler("list", list_conversations_command))
    application.add_handler(CommandHandler("det", delete_conversation_command))
    application.add_handler(CommandHandler("delall", delete_all_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("voice", voice_mode_command))
    application.add_handler(CommandHandler("rename", rename_conversation_command))
    application.add_handler(CommandHandler("reset", reset_command))

    # Messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))

    logger.info("Bot application created successfully")
    return application


async def setup_webhook(application: Application) -> None:
    """Setup webhook for the bot."""
    bot: Bot = application.bot
    webhook_url = f"{config.webhook_url}/webhook"

    # Delete existing webhook
    await bot.delete_webhook()

    # Set new webhook
    await bot.set_webhook(
        url=webhook_url,
        secret_token=config.webhook_secret,
    )

    logger.info(f"Webhook set to: {webhook_url}")


async def delete_webhook(application: Application) -> None:
    """Delete the webhook."""
    bot: Bot = application.bot
    await bot.delete_webhook()
    logger.info("Webhook deleted")


def run_webhook(application: Application) -> None:
    """Run the bot with webhook."""
    webhook_url = config.webhook_url
    port = config.webhook_port

    # Extract path from webhook URL
    from urllib.parse import urlparse
    parsed = urlparse(webhook_url)
    listen = "0.0.0.0"

    logger.info(f"Starting webhook server on {listen}:{port}")

    application.run_webhook(
        listen=listen,
        port=port,
        url_path="webhook",
        webhook_url=f"{webhook_url}/webhook",
        secret_token=config.webhook_secret,
    )


def run_polling(application: Application) -> None:
    """Run the bot with polling (for development)."""
    logger.info("Starting bot in polling mode")
    
    # Set bot commands menu on startup
    async def post_init(application: Application) -> None:
        await set_bot_commands(application.bot)
    
    application.post_init = post_init
    application.run_polling(allowed_updates=Update.ALL_TYPES)

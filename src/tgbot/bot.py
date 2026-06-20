"""Main bot application with webhook support."""

import logging

from telegram import Bot, BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import config
from .constants import BOT_COMMANDS
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
    commands = [BotCommand(cmd, desc) for cmd, desc in BOT_COMMANDS]
    await bot.set_my_commands(commands)
    logger.info("Bot commands menu set")


def create_application() -> Application:
    """Create and configure the bot application."""
    missing = config.validate()
    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")

    application = Application.builder().token(config.telegram_bot_token).build()

    # Command handlers
    command_map = {
        "start": start_command,
        "help": help_command,
        "fix": fix_command,
        "new": new_conversation_command,
        "list": list_conversations_command,
        "det": delete_conversation_command,
        "delall": delete_all_command,
        "clear": clear_command,
        "voice": voice_mode_command,
        "rename": rename_conversation_command,
        "reset": reset_command,
    }
    for cmd, handler in command_map.items():
        application.add_handler(CommandHandler(cmd, handler))

    # Message handlers
    message_handlers = [
        (filters.TEXT & ~filters.COMMAND, handle_text),
        (filters.VOICE, handle_voice),
        (filters.PHOTO, handle_photo),
        (filters.VIDEO, handle_video),
    ]
    for msg_filter, handler in message_handlers:
        application.add_handler(MessageHandler(msg_filter, handler))

    logger.info("Bot application created successfully")
    return application


async def setup_webhook(application: Application) -> None:
    """Setup webhook for the bot."""
    bot: Bot = application.bot
    webhook_url = f"{config.webhook_url}/webhook"

    await bot.delete_webhook()
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

    async def post_init(application: Application) -> None:
        await set_bot_commands(application.bot)

    application.post_init = post_init
    application.run_polling(allowed_updates=Update.ALL_TYPES)

"""Main entry point for the bot."""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install

from .bot import create_application, run_polling, run_webhook
from .config import config

# 安装 rich 异常追踪
install(show_locals=True)

console = Console()


def setup_logging(
    pretty: bool = True,
    debug: bool = False,
    log_file: str = None,
    quiet: bool = False,
) -> None:
    """Configure logging.
    
    Args:
        pretty: 美化日志输出（彩色）
        debug: 调试模式（显示所有日志）
        log_file: 日志文件路径（写入完整日志）
        quiet: 静默模式（不输出到控制台）
    """
    level = logging.DEBUG if debug else logging.INFO
    handlers = []
    
    # 第三方库日志级别
    if not debug:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.WARNING)
    
    # 文件日志（完整格式）
    if log_file:
        file_handler = logging.FileHandler(log_file, mode="a", encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        handlers.append(file_handler)
    
    # 控制台日志
    if not quiet:
        if pretty:
            # 美化日志输出
            rich_handler = RichHandler(
                console=console,
                show_time=True,
                show_path=False,
                rich_tracebacks=True,
                tracebacks_show_locals=debug,
                markup=True,
            )
            rich_handler.setLevel(level)
            handlers.append(rich_handler)
        else:
            # 普通日志输出（与文件格式一致）
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(level)
            stream_handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ))
            handlers.append(stream_handler)
    
    logging.basicConfig(
        level=level,
        handlers=handlers,
    )


logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="丛雨 Telegram Bot")
    parser.add_argument(
        "--polling",
        action="store_true",
        help="Run in polling mode (for development)",
    )
    parser.add_argument(
        "--webhook",
        action="store_true",
        help="Run in webhook mode (for production)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Enable pretty logging with colors (default: True)",
    )
    parser.add_argument(
        "--no-pretty",
        action="store_true",
        help="Disable pretty logging (plain text output, same format as file)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (show all logs including httpx, telegram)",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write logs to file (same format as console)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet mode (no console output, use with -o)",
    )
    args = parser.parse_args()

    # 设置日志
    pretty_logging = args.pretty and not args.no_pretty
    
    setup_logging(
        pretty=pretty_logging,
        debug=args.debug,
        log_file=args.output,
        quiet=args.quiet,
    )

    if pretty_logging and not args.quiet:
        console.print("[bold cyan]═══════════════════════════════════════[/]")
        console.print("[bold cyan]   丛雨 Telegram Bot 启动中...[/]")
        console.print("[bold cyan]═══════════════════════════════════════[/]")
        console.print(f"[green]对话模型:[/] [yellow]{config.chat_model}[/]")
        console.print(f"[green]多模态模型:[/] [yellow]{config.multimodal_model}[/]")
        console.print(f"[green]STT 服务:[/] [yellow]{config.stt_provider}[/]")
        console.print(f"[green]TTS 服务:[/] [yellow]{config.tts_provider}[/]")
        if args.output:
            console.print(f"[green]日志文件:[/] [cyan]{args.output}[/]")
        if args.debug:
            console.print("[red]调试模式: 已开启[/]")
        console.print()

    # Validate configuration
    missing = config.validate()
    if missing:
        if pretty_logging and not args.quiet:
            console.print(f"[bold red]配置缺失: {', '.join(missing)}[/]")
        else:
            logger.error(f"Missing required configuration: {', '.join(missing)}")
        sys.exit(1)

    # Create application
    application = create_application()

    # Determine mode
    if args.polling:
        if pretty_logging and not args.quiet:
            console.print("[bold green]使用 Polling 模式[/]")
        run_polling(application)
    elif args.webhook:
        if pretty_logging and not args.quiet:
            console.print("[bold green]使用 Webhook 模式[/]")
        run_webhook(application)
    else:
        # Default to webhook if WEBHOOK_URL is set, otherwise polling
        if config.webhook_url:
            if pretty_logging and not args.quiet:
                console.print(f"[bold green]使用 Webhook 模式[/] -> [cyan]{config.webhook_url}[/]")
            run_webhook(application)
        else:
            if pretty_logging and not args.quiet:
                console.print("[bold green]使用 Polling 模式[/]")
            run_polling(application)


if __name__ == "__main__":
    main()

"""Message handlers for the Telegram bot."""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from .auth import auth_manager
from .config import config
from .database import db
from .llm import llm_client
from .utils import format_user_info, message_generator
from .voice import extract_chinese, extract_japanese, generate_voice_japanese, has_correct_format

logger = logging.getLogger(__name__)


async def check_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Check if user is allowed to use the bot."""
    if not update.effective_user:
        return False

    user_id = update.effective_user.id
    
    # user_id 必须为正数
    if not user_id or user_id <= 0:
        return False
    
    # 检查是否已授权（白名单或已配对）
    if auth_manager.is_authorized(user_id, config.allowed_user_ids):
        return True

    # 未授权的情况
    if update.message:
        # 检查是否已有待处理的配对码
        if auth_manager.has_pending_pairing(user_id):
            await update.message.reply_text(
                "……抱歉，我不被允许和陌生人说话。(´・ω・`)\n"
                "请联系管理员完成配对授权。"
            )
        else:
            await update.message.reply_text(
                "……你是谁？(´･_･`)\n"
                "我不认识你。\n"
                "如果你想要和我对话，请先发送 /start 获取配对码。\n"
                "然后在服务器端输入配对码进行授权。"
            )
    return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    user_info = format_user_info(update.effective_user)

    # 如果已经在白名单或已授权
    if auth_manager.is_authorized(user_id, config.allowed_user_ids):
        welcome_message = (
            "唔，你来了啊 (｀・ω・´)\n"
            "我是丛雨，湊神神社的神刀化身...\n"
            "有什么事就直说吧\n\n"
            "【对话命令】\n"
            "/new - 新建对话\n"
            "/list - 对话列表\n"
            "/det <编号> - 删除对话\n"
            "/voice - 语音模式"
        )
        if update.message:
            await update.message.reply_text(welcome_message)
        return

    # 检查是否已有待处理的配对码
    if auth_manager.has_pending_pairing(user_id):
        if update.message:
            await update.message.reply_text(
                "你已经有配对码了。(´･_･`)\n"
                "请等待管理员授权，或联系管理员处理。"
            )
        return

    # 未授权用户需要配对码
    code = auth_manager.generate_pairing_code(
        user_id=user_id,
        user_info=user_info,
        ttl=config.pairing_code_ttl,
    )
    
    if update.message:
        await update.message.reply_text(
            f"……你是新来的？(´･_･`)\n"
            f"你的配对码是：{code}\n"
            f"请在服务器端输入此配对码进行授权。\n"
            f"配对码有效期 {config.pairing_code_ttl // 60} 分钟。"
        )
    logger.info(f"Generated pairing code {code} for user {user_info}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    if not await check_user(update, context):
        return

    help_text = (
        "【丛雨的使用方法】\n"
        "・文字消息 → 直接和我聊天\n"
        "・语音消息 → 听完后回复你\n"
        "・图片 → 看看后发表感想\n\n"
        "【对话命令】\n"
        "/new [名称] - 新建对话\n"
        "/list - 查看对话列表\n"
        "/det <编号> - 删除指定对话\n"
        "/clear - 清空当前对话\n"
        "/voice - 切换语音模式\n\n"
        "好好和我相处吧 (￣ー￣)"
    )

    if update.message:
        await update.message.reply_text(help_text)


async def fix_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /fix command - fix URL fallback issue."""
    if not await check_user(update, context):
        return

    if not update.message:
        return

    if config._url_fallback_needed:
        # 自动添加 FORCE_BASE64_IMAGE 配置
        env_path = ".env"
        try:
            with open(env_path, "r") as f:
                content = f.read()
            
            # 检查是否已有该配置
            if "FORCE_BASE64_IMAGE" in content:
                await update.message.reply_text(
                    "唔……已经配置好了呀 (´・ω・`)\n"
                    "重启 bot 就可以了。"
                )
                return
            
            # 添加配置
            with open(env_path, "a") as f:
                f.write("\n# 强制使用 Base64 传输图片/视频（解决 URL 访问失败问题）\n")
                f.write("FORCE_BASE64_IMAGE=true\n")
            
            config._url_fallback_needed = False
            await update.message.reply_text(
                "好！已经帮你加上配置了 (｀・ω・´)\n"
                "FORCE_BASE64_IMAGE=true\n\n"
                "重启 bot 就可以了~"
            )
        except Exception as e:
            logger.error(f"Failed to add FORCE_BASE64_IMAGE: {e}")
            await update.message.reply_text(
                "唔……好像失败了 (；´д｀)\n"
                "你可以手动在 .env 文件中添加：\n"
                "FORCE_BASE64_IMAGE=true"
            )
    else:
        await update.message.reply_text(
            "没什么要修复的呢 (´・ω・`)"
        )


async def new_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /new command - create a new conversation."""
    if not await check_user(update, context):
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id
    
    # 获取对话名称（如果提供了的话）
    name = " ".join(context.args) if context.args else "新对话"
    if len(name) > 50:
        name = name[:50]
    
    # 创建新对话
    conv_id = llm_client.create_new_conversation(user_id, name)
    
    if update.message:
        await update.message.reply_text(
            f"创建了新对话：{name}\n"
            f"编号：{conv_id}\n"
            f"开始聊天吧 (｀・ω・´)"
        )


async def list_conversations_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /list command - list all conversations."""
    if not await check_user(update, context):
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id
    
    # 获取对话列表
    conversations = db.list_conversations(user_id)
    active_conv_id = db.get_active_conversation(user_id)
    
    if not conversations:
        if update.message:
            await update.message.reply_text("还没有对话记录 (´･_･`)\n用 /new 创建一个吧")
        return
    
    # 构建消息
    lines = ["【对话列表】\n"]
    for conv in conversations:
        marker = "→ " if conv.id == active_conv_id else "  "
        # 格式化时间
        try:
            dt = datetime.fromisoformat(conv.updated_at)
            time_str = dt.strftime("%m-%d %H:%M")
        except Exception:
            time_str = conv.updated_at[:10] if conv.updated_at else "未知"
        
        lines.append(f"{marker}#{conv.id} {conv.name} ({time_str})")
    
    lines.append(f"\n共 {len(conversations)} 个对话")
    lines.append("当前对话前有 → 标记")
    
    if update.message:
        await update.message.reply_text("\n".join(lines))


async def delete_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /det command - delete one or more conversations."""
    if not await check_user(update, context):
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id
    
    # 检查参数
    if not context.args:
        if update.message:
            await update.message.reply_text(
                "请指定要删除的对话编号\n"
                "用法：/det <编号> [编号2] [编号3]...\n"
                "可以一次删除多个对话，用空格分隔\n"
                "用 /list 查看对话列表"
            )
        return
    
    deleted = []
    failed = []
    
    for arg in context.args:
        try:
            conv_id = int(arg)
            if db.delete_conversation(conv_id, user_id):
                deleted.append(conv_id)
                # 如果删除的是当前活跃对话，清除设置
                if db.get_active_conversation(user_id) == conv_id:
                    db.set_active_conversation(user_id, None)
            else:
                failed.append(arg)
        except ValueError:
            failed.append(arg)
    
    # 构建回复
    msg_parts = []
    if deleted:
        msg_parts.append(f"已删除对话：{', '.join(f'#{i}' for i in deleted)}")
    if failed:
        msg_parts.append(f"找不到：{', '.join(failed)}")
    
    if update.message:
        await update.message.reply_text("\n".join(msg_parts) + " (´・ω・`)")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /clear command to clear current conversation."""
    if not await check_user(update, context):
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id
    
    if llm_client.clear_conversation(user_id):
        if update.message:
            await update.message.reply_text(
                "对话已清空 (｀・ω・´)\n"
                "重新开始吧"
            )
    else:
        if update.message:
            await update.message.reply_text("没有当前对话 (´･_･`)")


async def voice_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle voice response mode."""
    if not await check_user(update, context):
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id
    
    current_mode = db.get_voice_mode(user_id)
    new_mode = not current_mode
    db.set_voice_mode(user_id, new_mode)

    if update.message:
        if new_mode:
            await update.message.reply_text(
                "语音模式已开启 (*´ω`*)\n"
                "之后会用声音回复你哦～"
            )
        else:
            await update.message.reply_text(
                "语音模式已关闭 (´・ω・`)\n"
                "用文字回复你"
            )


async def rename_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /rename command - rename a conversation."""
    if not await check_user(update, context):
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id
    
    # 检查参数
    if not context.args:
        if update.message:
            await update.message.reply_text(
                "用法：/rename <编号> <新名称>\n"
                "或：/rename <新名称> (重命名当前对话)\n"
                "用 /list 查看对话列表"
            )
        return
    
    # 判断第一个参数是编号还是名称
    first_arg = context.args[0]
    try:
        conv_id = int(first_arg)
        new_name = " ".join(context.args[1:]) if len(context.args) > 1 else None
    except ValueError:
        # 第一个参数不是数字，使用当前对话
        conv_id = db.get_active_conversation(user_id)
        new_name = " ".join(context.args)
    
    if not new_name:
        if update.message:
            await update.message.reply_text("请提供新名称 (´･_･`)")
        return
    
    if len(new_name) > 50:
        new_name = new_name[:50]
    
    if not conv_id:
        if update.message:
            await update.message.reply_text("没有当前对话 (´･_･`)\n请指定对话编号")
        return
    
    if db.rename_conversation(conv_id, user_id, new_name):
        if update.message:
            await update.message.reply_text(f"已重命名为：{new_name} (｀・ω・´)")
    else:
        if update.message:
            await update.message.reply_text("找不到这个对话 (´･_･`)")


async def delete_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /delall command - delete all conversations."""
    if not await check_user(update, context):
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id
    
    count = db.delete_all_conversations(user_id)
    
    # 清除活跃对话
    db.set_active_conversation(user_id, None)
    
    if update.message:
        if count > 0:
            await update.message.reply_text(
                f"已删除所有 {count} 个对话 (´・ω・`)\n"
                "用 /new 创建新对话吧"
            )
        else:
            await update.message.reply_text("没有对话可以删除 (´･_･`)")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /reset command - reset to factory settings."""
    if not await check_user(update, context):
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id
    
    result = db.reset_user(user_id)
    
    if update.message:
        await update.message.reply_text(
            f"已恢复到初始状态 (´・ω・`)\n"
            f"清除了 {result['conversations_deleted']} 个对话\n"
            "语音模式已关闭\n"
            "用 /new 创建新对话吧"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages."""
    if not await check_user(update, context):
        return

    if not update.message or not update.message.text:
        return

    # user_id 已在 check_user 中验证
    user_id = update.effective_user.id
    text = update.message.text

    logger.info(f"Text message from {user_id}: {text[:50]}...")

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        # Check if this is the first message in a new conversation
        conv_id = db.get_active_conversation(user_id)
        should_auto_rename = False
        if conv_id:
            first_msg = db.get_first_message(conv_id)
            # 如果还没有用户消息，说明是第一条
            should_auto_rename = first_msg is None

        # Check voice mode
        voice_mode = db.get_voice_mode(user_id)

        if voice_mode and config.tts_output_mode == "llm_output":
            # 语音模式 - AI直接输出中日双语
            response = await llm_client.generate_response_with_japanese(user_id, text)

            # 检查格式是否正确
            if not has_correct_format(response):
                logger.warning(f"LLM output format incorrect: {response[:100]}")
                # 格式不对，重新生成一次
                response = await llm_client.generate_response_with_japanese(user_id, text + " (请严格按<zh>和<ja>标签格式输出)")

            # 提取中文部分发送文字
            chinese_text = extract_chinese(response)
            if chinese_text:
                async for chunk in message_generator(chinese_text):
                    await update.message.reply_text(chunk)
            else:
                # 如果还是没有格式，发送原始内容
                logger.error(f"Still no correct format, sending raw: {response[:100]}")
                await update.message.reply_text(response[:500])

            # 提取日语部分生成语音
            japanese_text = extract_japanese(response)
            if japanese_text:
                try:
                    voice_data = await generate_voice_japanese(response, japanese_text)
                    await update.message.reply_voice(voice=voice_data)
                except Exception as e:
                    logger.error(f"Error generating voice: {e}")
            else:
                logger.warning(f"No Japanese text extracted for TTS")

        elif voice_mode:
            # 语音模式 - 翻译模式
            response = await llm_client.generate_response(user_id, text)

            # 发送文字
            logger.info(f"AI response: {response}")
            async for chunk in message_generator(response):
                await update.message.reply_text(chunk)

            # 生成语音
            try:
                voice_data = await generate_voice_japanese(response)
                await update.message.reply_voice(voice=voice_data)
            except Exception as e:
                logger.error(f"Error generating voice: {e}")
        else:
            # 普通文本模式
            response = await llm_client.generate_response(user_id, text)
            logger.info(f"AI response: {response}")
            async for chunk in message_generator(response):
                await update.message.reply_text(chunk)

        # 自动更名（在后台执行，不阻塞回复）
        if should_auto_rename and conv_id:
            try:
                new_name = await llm_client.generate_conversation_name(text)
                db.rename_conversation(conv_id, user_id, new_name)
                logger.info(f"Auto-renamed conversation {conv_id} to: {new_name}")
            except Exception as e:
                logger.error(f"Error auto-renaming conversation: {e}")

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        await update.message.reply_text(
            "唔……好像有点不对劲 (；´д｀)\n"
            "再说一次？"
        )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages."""
    if not await check_user(update, context):
        return

    if not update.message or not update.message.voice:
        return

    # user_id 已在 check_user 中验证
    user_id = update.effective_user.id
    voice = update.message.voice

    logger.info(f"Voice message from {user_id}")

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        # Get voice file
        voice_file = await voice.get_file()
        voice_data = await voice_file.download_as_bytearray()

        # Transcribe
        transcript = await llm_client.transcribe_audio(bytes(voice_data))
        logger.info(f"Transcribed: {transcript[:50]}...")

        # Check voice mode
        voice_mode = db.get_voice_mode(user_id)

        if voice_mode and config.tts_output_mode == "llm_output":
            # 语音模式 - AI直接输出中日双语
            response = await llm_client.generate_response_with_japanese(user_id, transcript)

            # 检查格式是否正确
            if not has_correct_format(response):
                logger.warning(f"LLM output format incorrect: {response[:100]}")
                response = await llm_client.generate_response_with_japanese(user_id, transcript + " (请严格按<zh>和<ja>标签格式输出)")

            # 提取中文部分发送文字
            chinese_text = extract_chinese(response)
            if chinese_text:
                async for chunk in message_generator(chinese_text):
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(response[:500])

            # 提取日语部分生成语音
            japanese_text = extract_japanese(response)
            if japanese_text:
                try:
                    voice_data = await generate_voice_japanese(response, japanese_text)
                    await update.message.reply_voice(voice=voice_data)
                except Exception as e:
                    logger.error(f"Error generating voice: {e}")
        else:
            # 普通模式
            response = await llm_client.generate_response(user_id, transcript)
            async for chunk in message_generator(response):
                await update.message.reply_text(chunk)

    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await update.message.reply_text(
            "抱歉，没听清你说什么 (´・ω・`)\n"
            "能再说一次吗？"
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages."""
    if not await check_user(update, context):
        return

    if not update.message or not update.message.photo:
        return

    # user_id 已在 check_user 中验证
    user_id = update.effective_user.id
    photo = update.message.photo[-1]  # Get highest quality
    caption = update.message.caption

    logger.info(f"Photo from {user_id}")

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        # Get photo file and URL
        photo_file = await photo.get_file()
        image_url = photo_file.file_path  # Telegram 文件 URL
        
        # 只在不强制 Base64 时才尝试 URL
        if config.force_base64_image:
            photo_data = await photo_file.download_as_bytearray()
            image_url = None
            logger.info(f"Photo downloaded (forced base64), size: {len(photo_data)} bytes")
        else:
            photo_data = await photo_file.download_as_bytearray()
            logger.info(f"Photo URL: {image_url}, size: {len(photo_data)} bytes")

        # Check voice mode
        voice_mode = db.get_voice_mode(user_id)

        if voice_mode and config.tts_output_mode == "llm_output":
            # 语音模式 - 需要让多模态AI也输出中日双语格式
            response = await llm_client.analyze_image_with_japanese(
                user_id, bytes(photo_data), caption, image_url
            )
            
            # 检查格式
            if not has_correct_format(response):
                logger.warning(f"Image LLM output format incorrect: {response[:100]}")
                chinese_text = response  # 格式不对，直接发送
            else:
                chinese_text = extract_chinese(response)
            
            if chinese_text:
                async for chunk in message_generator(chinese_text):
                    await update.message.reply_text(chunk)
            
            # 生成语音
            japanese_text = extract_japanese(response)
            if japanese_text:
                try:
                    voice_data = await generate_voice_japanese(response, japanese_text)
                    await update.message.reply_voice(voice=voice_data)
                except Exception as e:
                    logger.error(f"Error generating voice: {e}")
        else:
            # 普通模式
            response = await llm_client.analyze_image(
                user_id, bytes(photo_data), caption, image_url
            )
            logger.info(f"Image analysis response: {response[:100]}...")
            async for chunk in message_generator(response):
                await update.message.reply_text(chunk)

    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await update.message.reply_text(
            "唔，看不见图片 (´･_･`)\n"
            "可能网络有问题，或者图片格式不支持..."
        )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video messages."""
    if not await check_user(update, context):
        return

    if not update.message or not update.message.video:
        return

    # user_id 已在 check_user 中验证
    user_id = update.effective_user.id
    video = update.message.video
    caption = update.message.caption

    logger.info(f"Video from {user_id}, file_size={video.file_size}")

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        # 检查视频大小限制
        max_size = 200 * 1024 * 1024  # 200MB
        if video.file_size and video.file_size > max_size:
            await update.message.reply_text(
                "视频太大了 (；´д｀)\n"
                "发个小一点的吧..."
            )
            return

        # 获取视频文件和 URL
        video_file = await video.get_file()
        video_url = video_file.file_path
        
        if config.force_base64_image:
            video_data = await video_file.download_as_bytearray()
            video_url = None
            logger.info(f"Video downloaded (forced base64), size: {len(video_data)} bytes")
        else:
            video_data = await video_file.download_as_bytearray()
            logger.info(f"Video URL: {video_url}, size: {len(video_data)} bytes")

        # 分析视频
        response = await llm_client.analyze_video(user_id, bytes(video_data), caption, video_url)

        # 发送回复
        async for chunk in message_generator(response):
            await update.message.reply_text(chunk)

    except Exception as e:
        logger.error(f"Error handling video: {e}")
        await update.message.reply_text(
            "视频处理失败了 (；´д｀)\n"
            "可能太大了，或者格式不支持..."
        )

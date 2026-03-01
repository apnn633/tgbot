#!/bin/bash
# 启动丛雨 Telegram Bot

cd /home/nk/tgbot

# 检查.env文件是否存在
if [ ! -f ".env" ]; then
    echo "错误: .env 文件不存在"
    echo "请复制 .env.example 并填写配置:"
    echo "  cp .env.example .env"
    echo "  然后编辑 .env 文件填写必要的信息"
    exit 1
fi

# 启动bot
if [ "$1" = "--polling" ]; then
    echo "使用 polling 模式启动..."
    uv run python -m tgbot.main --polling
else
    echo "使用 webhook 模式启动..."
    uv run python -m tgbot.main --webhook
fi

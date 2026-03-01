#!/usr/bin/env python3
"""CLI tool for managing the Telegram bot."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from tgbot.auth import auth_manager
from tgbot.config import config


def cmd_pair(args):
    """Handle pairing code authorization."""
    code = args.code
    
    success, user_id, message = auth_manager.authorize_user(
        code, 
        ttl=config.pairing_code_ttl
    )
    
    if success:
        print(f"✓ {message}")
        print(f"  用户ID: {user_id}")
    else:
        print(f"✗ {message}")
        sys.exit(1)


def cmd_list(args):
    """List authorized users."""
    users = auth_manager.list_authorized_users()
    
    if not users:
        print("暂无已授权用户")
        return
    
    print(f"已授权用户 ({len(users)}):")
    for user_id in users:
        print(f"  - {user_id}")


def cmd_pending(args):
    """List pending pairing requests."""
    pending = auth_manager.list_pending_pairings()
    
    if not pending:
        print("暂无待处理配对请求")
        return
    
    print(f"待处理配对请求 ({len(pending)}):")
    for p in pending:
        print(f"  - 用户ID: {p.user_id}")
        print(f"    配对码: {p.code}")
        print(f"    用户信息: {p.user_info or '未知'}")
        print()


def cmd_revoke(args):
    """Revoke a user's authorization."""
    user_id = args.user_id
    
    if auth_manager.revoke_user(user_id):
        print(f"✓ 已撤销用户 {user_id} 的授权")
    else:
        print(f"✗ 用户 {user_id} 不在授权列表中")
        sys.exit(1)


def cmd_cleanup(args):
    """Clean up expired pairing codes."""
    count = auth_manager.cleanup_expired(ttl=config.pairing_code_ttl)
    print(f"已清理 {count} 个过期的配对码")


def cmd_whitelist(args):
    """Show whitelist from config."""
    if not config.allowed_user_ids:
        print("白名单为空（配置中未设置 ALLOWED_USER_IDS）")
        return
    
    print(f"白名单用户 ({len(config.allowed_user_ids)}):")
    for user_id in config.allowed_user_ids:
        print(f"  - {user_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Telegram Bot 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s pair 123456     # 使用配对码授权用户
  %(prog)s list            # 列出已授权用户
  %(prog)s pending         # 列出待处理配对请求
  %(prog)s revoke 12345678 # 撤销用户授权
  %(prog)s whitelist       # 显示白名单
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # pair 命令
    pair_parser = subparsers.add_parser("pair", help="使用配对码授权用户")
    pair_parser.add_argument("code", help="配对码")
    pair_parser.set_defaults(func=cmd_pair)
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出已授权用户")
    list_parser.set_defaults(func=cmd_list)
    
    # pending 命令
    pending_parser = subparsers.add_parser("pending", help="列出待处理配对请求")
    pending_parser.set_defaults(func=cmd_pending)
    
    # revoke 命令
    revoke_parser = subparsers.add_parser("revoke", help="撤销用户授权")
    revoke_parser.add_argument("user_id", type=int, help="用户ID")
    revoke_parser.set_defaults(func=cmd_revoke)
    
    # cleanup 命令
    cleanup_parser = subparsers.add_parser("cleanup", help="清理过期配对码")
    cleanup_parser.set_defaults(func=cmd_cleanup)
    
    # whitelist 命令
    whitelist_parser = subparsers.add_parser("whitelist", help="显示白名单")
    whitelist_parser.set_defaults(func=cmd_whitelist)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()

"""Authentication system for the bot using SQLite."""

import logging
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from .database import db

logger = logging.getLogger(__name__)


@dataclass
class PendingPairing:
    """Represents a pending pairing request."""
    user_id: int
    code: str
    created_at: float
    user_info: str = ""


class AuthManager:
    """Manages user authentication using SQLite."""

    def __init__(self):
        # 内存缓存用于配对码过期检查
        self._pending_cache: dict[int, PendingPairing] = {}

    def is_authorized(self, user_id: int, whitelist: list[int]) -> bool:
        """Check if user is authorized.
        
        Args:
            user_id: Telegram user ID
            whitelist: List of whitelisted user IDs from config
        
        Returns:
            True if user is authorized
        """
        # 白名单用户始终允许
        if user_id in whitelist:
            return True
        
        # 检查数据库中的授权用户
        return db.is_authorized(user_id)

    def generate_pairing_code(self, user_id: int, user_info: str = "", ttl: int = 300) -> str:
        """Generate a pairing code for a user.
        
        Args:
            user_id: Telegram user ID
            user_info: User display info for logging
            ttl: Time to live in seconds
        
        Returns:
            Pairing code (12-character secure random string)
        """
        # 生成安全的12位随机字符串（使用secrets模块）
        code = secrets.token_urlsafe(9)[:12]
        
        # 存储到数据库
        db.create_pairing_code(code, user_id, user_info)
        
        # 内存缓存
        self._pending_cache[user_id] = PendingPairing(
            user_id=user_id,
            code=code,
            created_at=time.time(),
            user_info=user_info,
        )
        
        logger.info(f"Generated pairing code {code} for user {user_id} ({user_info})")
        
        return code

    def verify_pairing_code(self, code: str, ttl: int = 300) -> Optional[int]:
        """Verify a pairing code.
        
        Args:
            code: The pairing code to verify
            ttl: Time to live in seconds
        
        Returns:
            User ID if valid, None otherwise
        """
        pairing = db.get_pairing_code(code)
        if pairing is None:
            return None
        
        # 检查是否过期
        created = pairing.get("created_at", "")
        if created:
            from datetime import datetime
            try:
                created_time = datetime.fromisoformat(created)
                elapsed = (datetime.now() - created_time).total_seconds()
                if elapsed > ttl:
                    db.delete_pairing_code(code)
                    logger.info(f"Pairing code {code} expired")
                    return None
            except Exception:
                pass
        
        return pairing["user_id"]

    def authorize_user(self, code: str, ttl: int = 300) -> tuple[bool, Optional[int], str]:
        """Authorize a user with pairing code.
        
        Args:
            code: The pairing code
            ttl: Time to live in seconds
        
        Returns:
            Tuple of (success, user_id, message)
        """
        user_id = self.verify_pairing_code(code, ttl)
        
        if user_id is None:
            return False, None, "配对码无效或已过期"
        
        # 获取配对信息
        pairing = db.get_pairing_code(code)
        user_info = pairing.get("user_info", str(user_id)) if pairing else str(user_id)
        
        # 授权用户
        db.authorize_user(user_id, user_info)
        
        # 清理配对码
        db.delete_pairing_code(code)
        self._pending_cache.pop(user_id, None)
        
        logger.info(f"Authorized user {user_id} ({user_info})")
        
        return True, user_id, f"用户 {user_info} 已授权"

    def revoke_user(self, user_id: int) -> bool:
        """Revoke a user's authorization.
        
        Args:
            user_id: Telegram user ID
        
        Returns:
            True if user was revoked, False if not found
        """
        result = db.revoke_user(user_id)
        if result:
            logger.info(f"Revoked user {user_id}")
        return result

    def cleanup_expired(self, ttl: int = 300) -> int:
        """Clean up expired pairing codes.
        
        Args:
            ttl: Time to live in seconds
        
        Returns:
            Number of expired codes cleaned
        """
        count = db.cleanup_expired_codes(ttl)
        if count:
            logger.info(f"Cleaned up {count} expired pairing codes")
        return count

    def list_authorized_users(self) -> list[dict]:
        """List all authorized users."""
        return db.get_authorized_users()

    def list_pending_pairings(self) -> list[dict]:
        """List all pending pairings."""
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pairing_codes")
            return [dict(row) for row in cursor.fetchall()]

    def has_pending_pairing(self, user_id: int) -> bool:
        """Check if user has a pending pairing request.
        
        Args:
            user_id: Telegram user ID
        
        Returns:
            True if user has a pending pairing
        """
        return db.get_user_pending_code(user_id) is not None


# Global auth manager instance
auth_manager = AuthManager()
"""SQLite database module for the bot."""

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Conversation:
    """Represents a conversation session."""
    id: int
    user_id: int
    name: str
    created_at: str
    updated_at: str
    is_active: bool = True


@dataclass
class Message:
    """Represents a message in a conversation."""
    id: int
    conversation_id: int
    role: str  # 'user' or 'assistant'
    content: str
    created_at: str


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str = ".tgbot_data/tgbot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 启用外键约束
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # 授权用户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS authorized_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    authorized_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 配对码表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pairing_codes (
                    code TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    user_info TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 对话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES authorized_users(user_id)
                )
            """)
            
            # 消息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # 用户设置表（存储当前活跃对话）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    active_conversation_id INTEGER,
                    voice_mode INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES authorized_users(user_id),
                    FOREIGN KEY (active_conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # 创建索引以提升查询性能
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_settings_user ON user_settings(user_id)")
            
            conn.commit()
            logger.info("Database initialized with foreign keys and indexes")

    @contextmanager
    def _get_connection(self):
        """Get database connection with foreign keys enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # 启用外键约束
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ==================== 用户授权 ====================

    def authorize_user(self, user_id: int, username: str = "", first_name: str = "") -> None:
        """Authorize a user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO authorized_users (user_id, username, first_name)
                VALUES (?, ?, ?)
            """, (user_id, username, first_name))
            conn.commit()
            logger.info(f"Authorized user {user_id}")

    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM authorized_users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None

    def revoke_user(self, user_id: int) -> bool:
        """Revoke user authorization."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM authorized_users WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_authorized_users(self) -> list[dict]:
        """Get all authorized users."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM authorized_users ORDER BY authorized_at")
            return [dict(row) for row in cursor.fetchall()]

    # ==================== 配对码 ====================

    def create_pairing_code(self, code: str, user_id: int, user_info: str = "") -> None:
        """Create a pairing code."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 先删除该用户的旧配对码
            cursor.execute("DELETE FROM pairing_codes WHERE user_id = ?", (user_id,))
            cursor.execute("""
                INSERT INTO pairing_codes (code, user_id, user_info)
                VALUES (?, ?, ?)
            """, (code, user_id, user_info))
            conn.commit()

    def get_pairing_code(self, code: str) -> Optional[dict]:
        """Get pairing code info."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pairing_codes WHERE code = ?", (code,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_pairing_code(self, code: str) -> None:
        """Delete a pairing code."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pairing_codes WHERE code = ?", (code,))
            conn.commit()

    def get_user_pending_code(self, user_id: int) -> Optional[dict]:
        """Get pending pairing code for a user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pairing_codes WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def cleanup_expired_codes(self, ttl_seconds: int) -> int:
        """Clean up expired pairing codes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM pairing_codes 
                WHERE datetime(created_at, '+' || ? || ' seconds') < datetime('now')
            """, (ttl_seconds,))
            conn.commit()
            return cursor.rowcount

    # ==================== 对话管理 ====================

    def create_conversation(self, user_id: int, name: str = "新对话") -> Conversation:
        """Create a new conversation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations (user_id, name)
                VALUES (?, ?)
            """, (user_id, name))
            conv_id = cursor.lastrowid
            conn.commit()
            
            return Conversation(
                id=conv_id,
                user_id=user_id,
                name=name,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )

    def get_conversation(self, conv_id: int) -> Optional[Conversation]:
        """Get a conversation by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
            row = cursor.fetchone()
            if row:
                return Conversation(
                    id=row["id"],
                    user_id=row["user_id"],
                    name=row["name"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    is_active=bool(row["is_active"]),
                )
            return None

    def list_conversations(self, user_id: int) -> list[Conversation]:
        """List all conversations for a user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM conversations 
                WHERE user_id = ? AND is_active = 1 
                ORDER BY updated_at DESC
            """, (user_id,))
            return [
                Conversation(
                    id=row["id"],
                    user_id=row["user_id"],
                    name=row["name"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    is_active=bool(row["is_active"]),
                )
                for row in cursor.fetchall()
            ]

    def delete_conversation(self, conv_id: int, user_id: int) -> bool:
        """Delete a conversation. If only one remains, reset all IDs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查当前有多少活跃对话
            cursor.execute("""
                SELECT COUNT(*) FROM conversations WHERE user_id = ? AND is_active = 1
            """, (user_id,))
            active_count = cursor.fetchone()[0]
            
            # 软删除指定对话
            cursor.execute("""
                UPDATE conversations SET is_active = 0 
                WHERE id = ? AND user_id = ?
            """, (conv_id, user_id))
            success = cursor.rowcount > 0
            
            # 如果只剩一个或删除后没有对话，重置编号
            if active_count <= 1:
                # 硬删除所有已软删除的对话
                cursor.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id = ? AND is_active = 0)", (user_id,))
                cursor.execute("DELETE FROM conversations WHERE user_id = ? AND is_active = 0", (user_id,))
                # 重置自增ID
                cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'conversations'")
                # 如果还有一个活跃对话，重新插入以获得 ID=1
                cursor.execute("SELECT id, name, created_at FROM conversations WHERE user_id = ? AND is_active = 1", (user_id,))
                remaining = cursor.fetchone()
                if remaining:
                    # 保存消息
                    cursor.execute("SELECT role, content, created_at FROM messages WHERE conversation_id = ?", (remaining[0],))
                    messages = cursor.fetchall()
                    # 删除旧记录
                    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (remaining[0],))
                    cursor.execute("DELETE FROM conversations WHERE id = ?", (remaining[0],))
                    # 插入新记录（ID=1）
                    cursor.execute("INSERT INTO conversations (id, user_id, name, created_at, is_active) VALUES (1, ?, ?, ?, 1)", (user_id, remaining[1], remaining[2]))
                    # 恢复消息
                    for msg in messages:
                        cursor.execute("INSERT INTO messages (conversation_id, role, content, created_at) VALUES (1, ?, ?, ?)", msg)
                    # 更新用户设置
                    cursor.execute("UPDATE user_settings SET active_conversation_id = 1 WHERE user_id = ?", (user_id,))
            
            conn.commit()
            return success

    def rename_conversation(self, conv_id: int, user_id: int, new_name: str) -> bool:
        """Rename a conversation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversations SET name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (new_name, conv_id, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_all_conversations(self, user_id: int) -> int:
        """Delete all conversations for a user and reset IDs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取删除数量
            cursor.execute("""
                SELECT COUNT(*) FROM conversations WHERE user_id = ? AND is_active = 1
            """, (user_id,))
            count = cursor.fetchone()[0]
            
            # 先删除消息（外键约束）
            cursor.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id = ?)", (user_id,))
            # 再删除对话
            cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
            
            # 重置自增ID
            cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'conversations'")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'messages'")
            
            # 清除用户设置中的活跃对话
            cursor.execute("UPDATE user_settings SET active_conversation_id = NULL WHERE user_id = ?", (user_id,))
            
            conn.commit()
            return count

    def reset_user(self, user_id: int) -> dict:
        """Reset user to initial state (keep authorization, clear conversations and settings)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 获取对话数量
            cursor.execute("""
                SELECT COUNT(*) FROM conversations WHERE user_id = ? AND is_active = 1
            """, (user_id,))
            conv_count = cursor.fetchone()[0]
            
            # 软删除所有对话
            cursor.execute("""
                UPDATE conversations SET is_active = 0 WHERE user_id = ?
            """, (user_id,))
            
            # 清除用户设置
            cursor.execute("""
                UPDATE user_settings SET active_conversation_id = NULL, voice_mode = 0 
                WHERE user_id = ?
            """, (user_id,))
            
            conn.commit()
            return {"conversations_deleted": conv_count}

    # ==================== 消息管理 ====================

    def add_message(self, conversation_id: int, role: str, content: str) -> None:
        """Add a message to a conversation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (conversation_id, role, content)
                VALUES (?, ?, ?)
            """, (conversation_id, role, content))
            # 更新对话的 updated_at
            cursor.execute("""
                UPDATE conversations SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (conversation_id,))
            conn.commit()

    def get_messages(self, conversation_id: int, limit: int = 50) -> list[dict]:
        """Get messages for a conversation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content FROM messages 
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (conversation_id, limit))
            return [{"role": row["role"], "content": row["content"]} for row in cursor.fetchall()]

    def get_first_message(self, conversation_id: int) -> Optional[str]:
        """Get the first user message in a conversation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT content FROM messages 
                WHERE conversation_id = ? AND role = 'user'
                ORDER BY created_at ASC
                LIMIT 1
            """, (conversation_id,))
            row = cursor.fetchone()
            return row["content"] if row else None

    def clear_messages(self, conversation_id: int) -> None:
        """Clear all messages in a conversation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.commit()

    # ==================== 用户设置 ====================

    def get_active_conversation(self, user_id: int) -> Optional[int]:
        """Get user's active conversation ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT active_conversation_id FROM user_settings WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            return row["active_conversation_id"] if row else None

    def set_active_conversation(self, user_id: int, conv_id: Optional[int]) -> None:
        """Set user's active conversation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_settings (user_id, active_conversation_id)
                VALUES (?, ?)
            """, (user_id, conv_id))
            conn.commit()

    def get_voice_mode(self, user_id: int) -> bool:
        """Get user's voice mode setting."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT voice_mode FROM user_settings WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return bool(row["voice_mode"]) if row else False

    def set_voice_mode(self, user_id: int, enabled: bool) -> None:
        """Set user's voice mode."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 先确保用户存在
            cursor.execute("""
                INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)
            """, (user_id,))
            # 再更新 voice_mode
            cursor.execute("""
                UPDATE user_settings SET voice_mode = ? WHERE user_id = ?
            """, (int(enabled), user_id))
            conn.commit()

    def ensure_user_settings(self, user_id: int) -> None:
        """Ensure user has settings row."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)
            """, (user_id,))
            conn.commit()


# Global database instance
db = Database()

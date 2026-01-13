"""User repository for database operations."""

from typing import Optional, List
from datetime import datetime
import json

from database.connection import Database
from database.models import User


class UserRepository:
    """Repository for user operations."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        telegram_id: int,
        telegram_username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            INSERT INTO users (telegram_id, telegram_username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            """,
            (telegram_id, telegram_username, first_name, last_name),
        )
        await conn.commit()

        return await self.get_by_id(cursor.lastrowid)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            return User.from_row(row)
        return None

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        if row:
            return User.from_row(row)
        return None

    async def accept_license(self, user_id: int) -> None:
        """Mark license as accepted for user."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE users
            SET license_accepted = 1,
                license_accepted_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (datetime.utcnow(), datetime.utcnow(), user_id),
        )
        await conn.commit()

    async def update_settings(self, user_id: int, settings: dict) -> None:
        """Update user settings."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE users
            SET settings = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(settings), datetime.utcnow(), user_id),
        )
        await conn.commit()

    async def deactivate(self, user_id: int) -> None:
        """Deactivate user."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE users
            SET is_active = 0,
                updated_at = ?
            WHERE id = ?
            """,
            (datetime.utcnow(), user_id),
        )
        await conn.commit()

    async def get_all_active(self) -> List[User]:
        """Get all active users."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM users WHERE is_active = 1"
        )
        rows = await cursor.fetchall()
        return [User.from_row(row) for row in rows]

    async def count_active(self) -> int:
        """Count active users."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE is_active = 1"
        )
        row = await cursor.fetchone()
        return row["count"]

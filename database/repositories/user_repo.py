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

    async def update_totp_secret(
        self,
        user_id: int,
        encrypted_secret: bytes,
        salt: bytes,
    ) -> None:
        """Store encrypted TOTP secret."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE users
            SET totp_secret = ?,
                totp_secret_salt = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (encrypted_secret, salt, datetime.utcnow(), user_id),
        )
        await conn.commit()

    async def mark_totp_verified(self, user_id: int) -> None:
        """Mark TOTP as verified (successful setup)."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE users
            SET totp_verified_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (datetime.utcnow(), datetime.utcnow(), user_id),
        )
        await conn.commit()

    async def clear_totp_secret(self, user_id: int) -> None:
        """Clear TOTP secret (disable 2FA)."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE users
            SET totp_secret = NULL,
                totp_secret_salt = NULL,
                totp_verified_at = NULL,
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

    # Referral-related methods

    async def get_by_referral_code(self, code: str) -> Optional[User]:
        """Get user by referral code."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM users WHERE referral_code = ?",
            (code,),
        )
        row = await cursor.fetchone()
        if row:
            return User.from_row(row)
        return None

    async def set_referral_code(self, user_id: int, code: str) -> None:
        """Set user's referral code."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE users
            SET referral_code = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (code, datetime.utcnow(), user_id),
        )
        await conn.commit()

    async def set_referrer(self, user_id: int, referrer_id: int) -> None:
        """Set user's referrer (who invited them)."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE users
            SET referrer_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (referrer_id, datetime.utcnow(), user_id),
        )
        await conn.commit()

    async def add_commission_balance(self, user_id: int, amount: float) -> None:
        """Add to user's commission balance and total earned."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE users
            SET commission_balance = commission_balance + ?,
                total_earned = total_earned + ?,
                updated_at = ?
            WHERE id = ?
            """,
            (amount, amount, datetime.utcnow(), user_id),
        )
        await conn.commit()

    async def claim_commission(self, user_id: int, amount: float) -> bool:
        """
        Claim commission from balance.

        Deducts from commission_balance and adds to total_claimed.
        Returns True if successful, False if insufficient balance.
        """
        conn = await self.db.get_connection()

        # Check current balance
        cursor = await conn.execute(
            "SELECT commission_balance FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row or row["commission_balance"] < amount:
            return False

        await conn.execute(
            """
            UPDATE users
            SET commission_balance = commission_balance - ?,
                total_claimed = total_claimed + ?,
                updated_at = ?
            WHERE id = ?
            """,
            (amount, amount, datetime.utcnow(), user_id),
        )
        await conn.commit()
        return True

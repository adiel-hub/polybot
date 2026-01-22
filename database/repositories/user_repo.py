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
        try:
            user_id = await conn.fetchval(
                """
                INSERT INTO users (telegram_id, telegram_username, first_name, last_name)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                telegram_id, telegram_username, first_name, last_name,
            )
            return await self.get_by_id(user_id)
        finally:
            await self.db.release_connection(conn)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id,
            )
            if row:
                return User.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1",
                telegram_id,
            )
            if row:
                return User.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def accept_license(self, user_id: int) -> None:
        """Mark license as accepted for user."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE users
                SET license_accepted = 1,
                    license_accepted_at = $1,
                    updated_at = $2
                WHERE id = $3
                """,
                datetime.utcnow(), datetime.utcnow(), user_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def update_settings(self, user_id: int, settings: dict) -> None:
        """Update user settings."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE users
                SET settings = $1,
                    updated_at = $2
                WHERE id = $3
                """,
                json.dumps(settings), datetime.utcnow(), user_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def deactivate(self, user_id: int) -> None:
        """Deactivate user."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE users
                SET is_active = 0,
                    updated_at = $1
                WHERE id = $2
                """,
                datetime.utcnow(), user_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def update_totp_secret(
        self,
        user_id: int,
        encrypted_secret: bytes,
        salt: bytes,
    ) -> None:
        """Store encrypted TOTP secret."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE users
                SET totp_secret = $1,
                    totp_secret_salt = $2,
                    updated_at = $3
                WHERE id = $4
                """,
                encrypted_secret, salt, datetime.utcnow(), user_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def mark_totp_verified(self, user_id: int) -> None:
        """Mark TOTP as verified (successful setup)."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE users
                SET totp_verified_at = $1,
                    updated_at = $2
                WHERE id = $3
                """,
                datetime.utcnow(), datetime.utcnow(), user_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def clear_totp_secret(self, user_id: int) -> None:
        """Clear TOTP secret (disable 2FA)."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE users
                SET totp_secret = NULL,
                    totp_secret_salt = NULL,
                    totp_verified_at = NULL,
                    updated_at = $1
                WHERE id = $2
                """,
                datetime.utcnow(), user_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def get_all_active(self) -> List[User]:
        """Get all active users."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                "SELECT * FROM users WHERE is_active = 1"
            )
            return [User.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def count_active(self) -> int:
        """Count active users."""
        conn = await self.db.get_connection()
        try:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE is_active = 1"
            )
            return count
        finally:
            await self.db.release_connection(conn)

    # Referral-related methods

    async def get_by_referral_code(self, code: str) -> Optional[User]:
        """Get user by referral code."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE referral_code = $1",
                code,
            )
            if row:
                return User.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def set_referral_code(self, user_id: int, code: str) -> None:
        """Set user's referral code."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE users
                SET referral_code = $1,
                    updated_at = $2
                WHERE id = $3
                """,
                code, datetime.utcnow(), user_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def set_referrer(self, user_id: int, referrer_id: int) -> None:
        """Set user's referrer (who invited them)."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE users
                SET referrer_id = $1,
                    updated_at = $2
                WHERE id = $3
                """,
                referrer_id, datetime.utcnow(), user_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def add_commission_balance(self, user_id: int, amount: float) -> None:
        """Add to user's commission balance and total earned."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE users
                SET commission_balance = commission_balance + $1,
                    total_earned = total_earned + $2,
                    updated_at = $3
                WHERE id = $4
                """,
                amount, amount, datetime.utcnow(), user_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def claim_commission(self, user_id: int, amount: float) -> bool:
        """
        Claim commission from balance.

        Deducts from commission_balance and adds to total_claimed.
        Returns True if successful, False if insufficient balance.
        """
        conn = await self.db.get_connection()
        try:
            # Check current balance
            row = await conn.fetchrow(
                "SELECT commission_balance FROM users WHERE id = $1",
                user_id,
            )
            if not row or row["commission_balance"] < amount:
                return False

            await conn.execute(
                """
                UPDATE users
                SET commission_balance = commission_balance - $1,
                    total_claimed = total_claimed + $2,
                    updated_at = $3
                WHERE id = $4
                """,
                amount, amount, datetime.utcnow(), user_id,
            )
            return True
        finally:
            await self.db.release_connection(conn)

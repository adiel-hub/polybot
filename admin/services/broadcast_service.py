"""Broadcast service for sending messages to users."""

import asyncio
import logging
from typing import Any, Callable, Optional
from telegram import Bot
from database.connection import Database
from admin.config import BROADCAST_BATCH_SIZE, BROADCAST_DELAY

logger = logging.getLogger(__name__)


class BroadcastService:
    """Service for broadcasting messages to users."""

    def __init__(self, db: Database, bot: Bot):
        self.db = db
        self.bot = bot

    async def get_target_users(
        self, filter_type: str = "all"
    ) -> list[dict[str, Any]]:
        """Get users matching filter criteria."""
        conn = await self.db.get_connection()
        if filter_type == "active":
            cursor = await conn.execute(
                "SELECT u.id, u.telegram_id FROM users u WHERE u.is_active = 1"
            )
        elif filter_type == "with_balance":
            cursor = await conn.execute(
                """
                SELECT u.id, u.telegram_id FROM users u
                JOIN wallets w ON w.user_id = u.id
                WHERE u.is_active = 1 AND w.usdc_balance > 0
                """
            )
        else:  # all
            cursor = await conn.execute(
                "SELECT id, telegram_id FROM users"
            )

        rows = await cursor.fetchall()
        return [{"id": row[0], "telegram_id": row[1]} for row in rows]

    async def broadcast_message(
        self,
        message: str,
        filter_type: str = "all",
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
        image_file_id: Optional[str] = None,
        reply_markup: Optional[Any] = None,
    ) -> dict[str, Any]:
        """
        Send message to filtered users.

        Args:
            message: The message text to send
            filter_type: "all", "active", or "with_balance"
            progress_callback: Optional callback(sent, failed, total)
            image_file_id: Optional Telegram file_id for image broadcast
            reply_markup: Optional InlineKeyboardMarkup for buttons

        Returns:
            Dict with sent, failed, and total counts
        """
        users = await self.get_target_users(filter_type)
        total = len(users)
        sent = 0
        failed = 0
        failed_users = []

        for i, user in enumerate(users):
            try:
                # Send image with caption if image_file_id provided
                if image_file_id:
                    await self.bot.send_photo(
                        chat_id=user["telegram_id"],
                        photo=image_file_id,
                        caption=message,
                        parse_mode="Markdown",
                        reply_markup=reply_markup,
                    )
                else:
                    # Send text message
                    await self.bot.send_message(
                        chat_id=user["telegram_id"],
                        text=message,
                        parse_mode="Markdown",
                        reply_markup=reply_markup,
                    )
                sent += 1
            except Exception as e:
                failed += 1
                failed_users.append(
                    {"user_id": user["id"], "error": str(e)}
                )
                logger.warning(
                    f"Failed to send broadcast to user {user['id']}: {e}"
                )

            # Progress callback
            if progress_callback and (i + 1) % 10 == 0:
                await progress_callback(sent, failed, total)

            # Rate limiting
            if (i + 1) % BROADCAST_BATCH_SIZE == 0:
                await asyncio.sleep(BROADCAST_DELAY)

        return {
            "sent": sent,
            "failed": failed,
            "total": total,
            "failed_users": failed_users,
        }

    async def count_target_users(self, filter_type: str = "all") -> int:
        """Count users matching filter criteria."""
        conn = await self.db.get_connection()
        if filter_type == "active":
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_active = 1"
            )
        elif filter_type == "with_balance":
            cursor = await conn.execute(
                """
                SELECT COUNT(*) FROM users u
                JOIN wallets w ON w.user_id = u.id
                WHERE u.is_active = 1 AND w.usdc_balance > 0
                """
            )
        else:  # all
            cursor = await conn.execute("SELECT COUNT(*) FROM users")

        return (await cursor.fetchone())[0]

"""Stop loss repository for database operations."""

from typing import Optional, List
from datetime import datetime

from database.connection import Database
from database.models import StopLoss


class StopLossRepository:
    """Repository for stop loss operations."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        user_id: int,
        position_id: int,
        token_id: str,
        trigger_price: float,
        sell_percentage: float = 100.0,
    ) -> StopLoss:
        """Create a new stop loss order."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            INSERT INTO stop_loss_orders (
                user_id, position_id, token_id, trigger_price, sell_percentage
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, position_id, token_id, trigger_price, sell_percentage),
        )
        await conn.commit()

        return await self.get_by_id(cursor.lastrowid)

    async def get_by_id(self, stop_loss_id: int) -> Optional[StopLoss]:
        """Get stop loss by ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM stop_loss_orders WHERE id = ?",
            (stop_loss_id,),
        )
        row = await cursor.fetchone()
        if row:
            return StopLoss.from_row(row)
        return None

    async def get_active_for_position(self, position_id: int) -> Optional[StopLoss]:
        """Get active stop loss for a position."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM stop_loss_orders
            WHERE position_id = ? AND is_active = 1
            """,
            (position_id,),
        )
        row = await cursor.fetchone()
        if row:
            return StopLoss.from_row(row)
        return None

    async def get_user_stop_losses(self, user_id: int) -> List[StopLoss]:
        """Get all active stop losses for a user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM stop_loss_orders
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [StopLoss.from_row(row) for row in rows]

    async def get_all_active(self) -> List[StopLoss]:
        """Get all active stop losses."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM stop_loss_orders
            WHERE is_active = 1
            ORDER BY created_at ASC
            """
        )
        rows = await cursor.fetchall()
        return [StopLoss.from_row(row) for row in rows]

    async def deactivate(self, stop_loss_id: int) -> None:
        """Deactivate a stop loss."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE stop_loss_orders SET is_active = 0 WHERE id = ?",
            (stop_loss_id,),
        )
        await conn.commit()

    async def mark_triggered(
        self,
        stop_loss_id: int,
        resulting_order_id: int,
    ) -> None:
        """Mark stop loss as triggered."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE stop_loss_orders
            SET is_active = 0,
                triggered_at = ?,
                resulting_order_id = ?
            WHERE id = ?
            """,
            (datetime.utcnow(), resulting_order_id, stop_loss_id),
        )
        await conn.commit()

    async def update_trigger_price(
        self,
        stop_loss_id: int,
        new_trigger_price: float,
    ) -> None:
        """Update trigger price for a stop loss."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE stop_loss_orders SET trigger_price = ? WHERE id = ?",
            (new_trigger_price, stop_loss_id),
        )
        await conn.commit()

    async def delete_for_position(self, position_id: int) -> None:
        """Delete all stop losses for a position."""
        conn = await self.db.get_connection()
        await conn.execute(
            "DELETE FROM stop_loss_orders WHERE position_id = ?",
            (position_id,),
        )
        await conn.commit()

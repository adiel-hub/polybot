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
        try:
            stop_loss_id = await conn.fetchval(
                """
                INSERT INTO stop_loss_orders (
                    user_id, position_id, token_id, trigger_price, sell_percentage
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                user_id, position_id, token_id, trigger_price, sell_percentage,
            )
            return await self.get_by_id(stop_loss_id)
        finally:
            await self.db.release_connection(conn)

    async def get_by_id(self, stop_loss_id: int) -> Optional[StopLoss]:
        """Get stop loss by ID."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM stop_loss_orders WHERE id = $1",
                stop_loss_id,
            )
            if row:
                return StopLoss.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def get_active_for_position(self, position_id: int) -> Optional[StopLoss]:
        """Get active stop loss for a position."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                """
                SELECT * FROM stop_loss_orders
                WHERE position_id = $1 AND is_active = TRUE
                """,
                position_id,
            )
            if row:
                return StopLoss.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def get_user_stop_losses(self, user_id: int) -> List[StopLoss]:
        """Get all active stop losses for a user."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM stop_loss_orders
                WHERE user_id = $1 AND is_active = TRUE
                ORDER BY created_at DESC
                """,
                user_id,
            )
            return [StopLoss.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def get_all_active(self) -> List[StopLoss]:
        """Get all active stop losses."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM stop_loss_orders
                WHERE is_active = TRUE
                ORDER BY created_at ASC
                """
            )
            return [StopLoss.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def deactivate(self, stop_loss_id: int) -> None:
        """Deactivate a stop loss."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                "UPDATE stop_loss_orders SET is_active = FALSE WHERE id = $1",
                stop_loss_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def mark_triggered(
        self,
        stop_loss_id: int,
        resulting_order_id: int,
    ) -> None:
        """Mark stop loss as triggered."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE stop_loss_orders
                SET is_active = FALSE,
                    triggered_at = $1,
                    resulting_order_id = $2
                WHERE id = $3
                """,
                datetime.utcnow(), resulting_order_id, stop_loss_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def update_trigger_price(
        self,
        stop_loss_id: int,
        new_trigger_price: float,
    ) -> None:
        """Update trigger price for a stop loss."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                "UPDATE stop_loss_orders SET trigger_price = $1 WHERE id = $2",
                new_trigger_price, stop_loss_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def delete_for_position(self, position_id: int) -> None:
        """Delete all stop losses for a position."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                "DELETE FROM stop_loss_orders WHERE position_id = $1",
                position_id,
            )
        finally:
            await self.db.release_connection(conn)

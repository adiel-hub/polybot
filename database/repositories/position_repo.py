"""Position repository for database operations."""

from typing import Optional, List
from datetime import datetime

from database.connection import Database
from database.models import Position


class PositionRepository:
    """Repository for position operations."""

    def __init__(self, db: Database):
        self.db = db

    async def create_or_update(
        self,
        user_id: int,
        market_condition_id: str,
        token_id: str,
        outcome: str,
        size: float,
        average_entry_price: float,
        market_question: Optional[str] = None,
    ) -> Position:
        """Create or update a position."""
        conn = await self.db.get_connection()

        # Check if position exists
        existing = await self.get_by_token_id(user_id, token_id)

        if existing:
            # Update existing position with new average price
            new_size = existing.size + size
            if new_size > 0:
                new_avg_price = (
                    (existing.size * existing.average_entry_price) + (size * average_entry_price)
                ) / new_size
            else:
                new_avg_price = average_entry_price

            await conn.execute(
                """
                UPDATE positions
                SET size = ?,
                    average_entry_price = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (new_size, new_avg_price, datetime.utcnow(), existing.id),
            )
            await conn.commit()
            return await self.get_by_id(existing.id)
        else:
            # Create new position
            cursor = await conn.execute(
                """
                INSERT INTO positions (
                    user_id, market_condition_id, market_question,
                    token_id, outcome, size, average_entry_price
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, market_condition_id, market_question,
                    token_id, outcome, size, average_entry_price,
                ),
            )
            await conn.commit()
            return await self.get_by_id(cursor.lastrowid)

    async def get_by_id(self, position_id: int) -> Optional[Position]:
        """Get position by ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM positions WHERE id = ?",
            (position_id,),
        )
        row = await cursor.fetchone()
        if row:
            return Position.from_row(row)
        return None

    async def get_by_token_id(self, user_id: int, token_id: str) -> Optional[Position]:
        """Get position by token ID for a user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM positions WHERE user_id = ? AND token_id = ?",
            (user_id, token_id),
        )
        row = await cursor.fetchone()
        if row:
            return Position.from_row(row)
        return None

    async def get_user_positions(self, user_id: int) -> List[Position]:
        """Get all positions for a user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM positions
            WHERE user_id = ? AND size > 0
            ORDER BY updated_at DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [Position.from_row(row) for row in rows]

    async def update_current_price(
        self,
        position_id: int,
        current_price: float,
    ) -> None:
        """Update position current price and calculate PnL."""
        conn = await self.db.get_connection()

        # Get position to calculate PnL
        position = await self.get_by_id(position_id)
        if position:
            unrealized_pnl = (current_price - position.average_entry_price) * position.size

            await conn.execute(
                """
                UPDATE positions
                SET current_price = ?,
                    unrealized_pnl = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (current_price, unrealized_pnl, datetime.utcnow(), position_id),
            )
            await conn.commit()

    async def reduce_position(
        self,
        position_id: int,
        size_to_reduce: float,
        sell_price: float,
    ) -> None:
        """Reduce position size and record realized PnL."""
        conn = await self.db.get_connection()

        position = await self.get_by_id(position_id)
        if position:
            realized_pnl = (sell_price - position.average_entry_price) * size_to_reduce
            new_size = position.size - size_to_reduce

            await conn.execute(
                """
                UPDATE positions
                SET size = ?,
                    realized_pnl = realized_pnl + ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (max(0, new_size), realized_pnl, datetime.utcnow(), position_id),
            )
            await conn.commit()

    async def delete_empty_positions(self, user_id: int) -> None:
        """Delete positions with zero size."""
        conn = await self.db.get_connection()
        await conn.execute(
            "DELETE FROM positions WHERE user_id = ? AND size <= 0",
            (user_id,),
        )
        await conn.commit()

    async def get_total_value(self, user_id: int) -> float:
        """Get total portfolio value for a user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT SUM(size * COALESCE(current_price, average_entry_price)) as total
            FROM positions
            WHERE user_id = ? AND size > 0
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["total"] or 0.0

    async def get_total_unrealized_pnl(self, user_id: int) -> float:
        """Get total unrealized PnL for a user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT SUM(unrealized_pnl) as total
            FROM positions
            WHERE user_id = ? AND size > 0
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["total"] or 0.0

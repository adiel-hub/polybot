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
        try:
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
                    SET size = $1,
                        average_entry_price = $2,
                        updated_at = $3
                    WHERE id = $4
                    """,
                    new_size, new_avg_price, datetime.utcnow(), existing.id,
                )
                return await self.get_by_id(existing.id)
            else:
                # Create new position
                position_id = await conn.fetchval(
                    """
                    INSERT INTO positions (
                        user_id, market_condition_id, market_question,
                        token_id, outcome, size, average_entry_price
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    user_id, market_condition_id, market_question,
                    token_id, outcome, size, average_entry_price,
                )
                return await self.get_by_id(position_id)
        finally:
            await self.db.release_connection(conn)

    async def get_by_id(self, position_id: int) -> Optional[Position]:
        """Get position by ID."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM positions WHERE id = $1",
                position_id,
            )
            if row:
                return Position.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def get_by_token_id(self, user_id: int, token_id: str) -> Optional[Position]:
        """Get position by token ID for a user."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM positions WHERE user_id = $1 AND token_id = $2",
                user_id, token_id,
            )
            if row:
                return Position.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def get_user_positions(self, user_id: int) -> List[Position]:
        """Get all positions for a user."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM positions
                WHERE user_id = $1 AND size > 0
                ORDER BY updated_at DESC
                """,
                user_id,
            )
            return [Position.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def update_current_price(
        self,
        position_id: int,
        current_price: float,
    ) -> None:
        """Update position current price and calculate PnL."""
        conn = await self.db.get_connection()
        try:
            # Get position to calculate PnL
            position = await self.get_by_id(position_id)
            if position:
                unrealized_pnl = (current_price - position.average_entry_price) * position.size

                await conn.execute(
                    """
                    UPDATE positions
                    SET current_price = $1,
                        unrealized_pnl = $2,
                        updated_at = $3
                    WHERE id = $4
                    """,
                    current_price, unrealized_pnl, datetime.utcnow(), position_id,
                )
        finally:
            await self.db.release_connection(conn)

    async def update_size(
        self,
        position_id: int,
        new_size: float,
    ) -> None:
        """
        Update position size to match on-chain balance.

        Used when DB position doesn't match actual CTF token balance.

        Args:
            position_id: Position ID
            new_size: New size (shares) from on-chain
        """
        conn = await self.db.get_connection()
        try:
            if new_size <= 0:
                # Delete position if no shares
                await conn.execute(
                    "DELETE FROM positions WHERE id = $1",
                    position_id,
                )
            else:
                await conn.execute(
                    """
                    UPDATE positions
                    SET size = $1,
                        updated_at = $2
                    WHERE id = $3
                    """,
                    new_size, datetime.utcnow(), position_id,
                )
        finally:
            await self.db.release_connection(conn)

    async def reduce_position(
        self,
        position_id: int,
        size_to_reduce: float,
        sell_price: float,
    ) -> None:
        """Reduce position size and record realized PnL."""
        conn = await self.db.get_connection()
        try:
            position = await self.get_by_id(position_id)
            if position:
                realized_pnl = (sell_price - position.average_entry_price) * size_to_reduce
                new_size = position.size - size_to_reduce

                # If position is fully closed, delete it
                if new_size <= 0:
                    await conn.execute(
                        "DELETE FROM positions WHERE id = $1",
                        position_id,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE positions
                        SET size = $1,
                            realized_pnl = realized_pnl + $2,
                            updated_at = $3
                        WHERE id = $4
                        """,
                        new_size, realized_pnl, datetime.utcnow(), position_id,
                    )
        finally:
            await self.db.release_connection(conn)

    async def delete_empty_positions(self, user_id: int) -> None:
        """Delete positions with zero size."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                "DELETE FROM positions WHERE user_id = $1 AND size <= 0",
                user_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def get_total_value(self, user_id: int) -> float:
        """Get total portfolio value for a user."""
        conn = await self.db.get_connection()
        try:
            total = await conn.fetchval(
                """
                SELECT SUM(size * COALESCE(current_price, average_entry_price))
                FROM positions
                WHERE user_id = $1 AND size > 0
                """,
                user_id,
            )
            return total or 0.0
        finally:
            await self.db.release_connection(conn)

    async def get_total_unrealized_pnl(self, user_id: int) -> float:
        """Get total unrealized PnL for a user."""
        conn = await self.db.get_connection()
        try:
            total = await conn.fetchval(
                """
                SELECT SUM(unrealized_pnl)
                FROM positions
                WHERE user_id = $1 AND size > 0
                """,
                user_id,
            )
            return total or 0.0
        finally:
            await self.db.release_connection(conn)

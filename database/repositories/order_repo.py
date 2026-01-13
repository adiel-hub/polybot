"""Order repository for database operations."""

from typing import Optional, List
from datetime import datetime

from database.connection import Database
from database.models import Order


class OrderRepository:
    """Repository for order operations."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        user_id: int,
        market_condition_id: str,
        token_id: str,
        side: str,
        order_type: str,
        size: float,
        outcome: str,
        price: Optional[float] = None,
        market_question: Optional[str] = None,
    ) -> Order:
        """Create a new order."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            INSERT INTO orders (
                user_id, market_condition_id, market_question, token_id,
                side, order_type, price, size, outcome
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, market_condition_id, market_question, token_id,
                side, order_type, price, size, outcome,
            ),
        )
        await conn.commit()

        return await self.get_by_id(cursor.lastrowid)

    async def get_by_id(self, order_id: int) -> Optional[Order]:
        """Get order by ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,),
        )
        row = await cursor.fetchone()
        if row:
            return Order.from_row(row)
        return None

    async def get_by_polymarket_id(self, polymarket_order_id: str) -> Optional[Order]:
        """Get order by Polymarket order ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM orders WHERE polymarket_order_id = ?",
            (polymarket_order_id,),
        )
        row = await cursor.fetchone()
        if row:
            return Order.from_row(row)
        return None

    async def update_polymarket_id(self, order_id: int, polymarket_order_id: str) -> None:
        """Update order with Polymarket order ID."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE orders
            SET polymarket_order_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (polymarket_order_id, datetime.utcnow(), order_id),
        )
        await conn.commit()

    async def update_status(
        self,
        order_id: int,
        status: str,
        filled_size: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update order status."""
        conn = await self.db.get_connection()

        if filled_size is not None:
            await conn.execute(
                """
                UPDATE orders
                SET status = ?,
                    filled_size = ?,
                    error_message = ?,
                    updated_at = ?,
                    executed_at = CASE WHEN ? IN ('FILLED', 'FAILED') THEN ? ELSE executed_at END
                WHERE id = ?
                """,
                (status, filled_size, error_message, datetime.utcnow(), status, datetime.utcnow(), order_id),
            )
        else:
            await conn.execute(
                """
                UPDATE orders
                SET status = ?,
                    error_message = ?,
                    updated_at = ?,
                    executed_at = CASE WHEN ? IN ('FILLED', 'FAILED') THEN ? ELSE executed_at END
                WHERE id = ?
                """,
                (status, error_message, datetime.utcnow(), status, datetime.utcnow(), order_id),
            )
        await conn.commit()

    async def get_open_orders(self, user_id: int) -> List[Order]:
        """Get all open orders for a user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM orders
            WHERE user_id = ?
            AND status IN ('PENDING', 'OPEN', 'PARTIALLY_FILLED')
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [Order.from_row(row) for row in rows]

    async def get_user_orders(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Order]:
        """Get orders for a user with pagination."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [Order.from_row(row) for row in rows]

    async def get_pending_orders(self) -> List[Order]:
        """Get all pending orders across all users."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM orders
            WHERE status IN ('PENDING', 'OPEN', 'PARTIALLY_FILLED')
            ORDER BY created_at ASC
            """
        )
        rows = await cursor.fetchall()
        return [Order.from_row(row) for row in rows]

    async def count_open_orders(self, user_id: int) -> int:
        """Count open orders for a user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT COUNT(*) as count FROM orders
            WHERE user_id = ?
            AND status IN ('PENDING', 'OPEN', 'PARTIALLY_FILLED')
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["count"]

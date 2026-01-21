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
        try:
            order_id = await conn.fetchval(
                """
                INSERT INTO orders (
                    user_id, market_condition_id, market_question, token_id,
                    side, order_type, price, size, outcome
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                user_id, market_condition_id, market_question, token_id,
                side, order_type, price, size, outcome,
            )
            return await self.get_by_id(order_id)
        finally:
            await self.db.release_connection(conn)

    async def get_by_id(self, order_id: int) -> Optional[Order]:
        """Get order by ID."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM orders WHERE id = $1",
                order_id,
            )
            if row:
                return Order.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def get_by_polymarket_id(self, polymarket_order_id: str) -> Optional[Order]:
        """Get order by Polymarket order ID."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM orders WHERE polymarket_order_id = $1",
                polymarket_order_id,
            )
            if row:
                return Order.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def update_polymarket_id(self, order_id: int, polymarket_order_id: str) -> None:
        """Update order with Polymarket order ID."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE orders
                SET polymarket_order_id = $1,
                    updated_at = $2
                WHERE id = $3
                """,
                polymarket_order_id, datetime.utcnow(), order_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def update_status(
        self,
        order_id: int,
        status: str,
        filled_size: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update order status."""
        conn = await self.db.get_connection()
        try:
            if filled_size is not None:
                await conn.execute(
                    """
                    UPDATE orders
                    SET status = $1,
                        filled_size = $2,
                        error_message = $3,
                        updated_at = $4,
                        executed_at = CASE WHEN $5 IN ('FILLED', 'FAILED') THEN $6 ELSE executed_at END
                    WHERE id = $7
                    """,
                    status, filled_size, error_message, datetime.utcnow(), status, datetime.utcnow(), order_id,
                )
            else:
                await conn.execute(
                    """
                    UPDATE orders
                    SET status = $1,
                        error_message = $2,
                        updated_at = $3,
                        executed_at = CASE WHEN $4 IN ('FILLED', 'FAILED') THEN $5 ELSE executed_at END
                    WHERE id = $6
                    """,
                    status, error_message, datetime.utcnow(), status, datetime.utcnow(), order_id,
                )
        finally:
            await self.db.release_connection(conn)

    async def get_open_orders(self, user_id: int) -> List[Order]:
        """Get all open orders for a user."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM orders
                WHERE user_id = $1
                AND status IN ('PENDING', 'OPEN', 'PARTIALLY_FILLED')
                ORDER BY created_at DESC
                """,
                user_id,
            )
            return [Order.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def get_user_orders(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Order]:
        """Get orders for a user with pagination."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM orders
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id, limit, offset,
            )
            return [Order.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def get_pending_orders(self) -> List[Order]:
        """Get all pending orders across all users."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM orders
                WHERE status IN ('PENDING', 'OPEN', 'PARTIALLY_FILLED')
                ORDER BY created_at ASC
                """
            )
            return [Order.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def count_open_orders(self, user_id: int) -> int:
        """Count open orders for a user."""
        conn = await self.db.get_connection()
        try:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM orders
                WHERE user_id = $1
                AND status IN ('PENDING', 'OPEN', 'PARTIALLY_FILLED')
                """,
                user_id,
            )
            return count
        finally:
            await self.db.release_connection(conn)

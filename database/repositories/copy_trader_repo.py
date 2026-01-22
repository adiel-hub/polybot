"""Copy trader repository for database operations."""

from typing import Optional, List
from datetime import datetime

from database.connection import Database
from database.models import CopyTrader


class CopyTraderRepository:
    """Repository for copy trader operations."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        user_id: int,
        trader_address: str,
        allocation: float,
        trader_name: Optional[str] = None,
        max_trade_size: Optional[float] = None,
    ) -> CopyTrader:
        """Create a new copy trader subscription."""
        conn = await self.db.get_connection()
        try:
            copy_trader_id = await conn.fetchval(
                """
                INSERT INTO copy_traders (
                    user_id, trader_address, trader_name, allocation, max_trade_size
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                user_id, trader_address.lower(), trader_name, allocation, max_trade_size,
            )
            return await self.get_by_id(copy_trader_id)
        finally:
            await self.db.release_connection(conn)

    async def get_by_id(self, copy_trader_id: int) -> Optional[CopyTrader]:
        """Get copy trader by ID."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM copy_traders WHERE id = $1",
                copy_trader_id,
            )
            if row:
                return CopyTrader.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def get_by_user_and_trader(
        self,
        user_id: int,
        trader_address: str,
    ) -> Optional[CopyTrader]:
        """Get copy trader subscription for user and trader."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                """
                SELECT * FROM copy_traders
                WHERE user_id = $1 AND LOWER(trader_address) = LOWER($2)
                """,
                user_id, trader_address,
            )
            if row:
                return CopyTrader.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def get_user_subscriptions(self, user_id: int) -> List[CopyTrader]:
        """Get all copy trader subscriptions for a user."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM copy_traders
                WHERE user_id = $1 AND is_active = 1
                ORDER BY created_at DESC
                """,
                user_id,
            )
            return [CopyTrader.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def get_all_active(self) -> List[CopyTrader]:
        """Get all active copy trader subscriptions."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM copy_traders
                WHERE is_active = 1
                """
            )
            return [CopyTrader.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def get_followers_for_trader(self, trader_address: str) -> List[CopyTrader]:
        """Get all users following a specific trader."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM copy_traders
                WHERE LOWER(trader_address) = LOWER($1) AND is_active = 1
                """,
                trader_address,
            )
            return [CopyTrader.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def update_allocation(
        self,
        copy_trader_id: int,
        allocation: float,
    ) -> None:
        """Update allocation percentage."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                "UPDATE copy_traders SET allocation = $1 WHERE id = $2",
                allocation, copy_trader_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def deactivate(self, copy_trader_id: int) -> None:
        """Deactivate a copy trader subscription."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                "UPDATE copy_traders SET is_active = 0 WHERE id = $1",
                copy_trader_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def activate(self, copy_trader_id: int) -> None:
        """Reactivate a copy trader subscription."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                "UPDATE copy_traders SET is_active = 1 WHERE id = $1",
                copy_trader_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def record_trade(
        self,
        copy_trader_id: int,
        pnl: float = 0.0,
    ) -> None:
        """Record a copied trade."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE copy_traders
                SET total_trades_copied = total_trades_copied + 1,
                    total_pnl = total_pnl + $1,
                    last_trade_at = $2
                WHERE id = $3
                """,
                pnl, datetime.utcnow(), copy_trader_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def get_unique_traders(self) -> List[str]:
        """Get list of unique trader addresses being copied."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT DISTINCT trader_address
                FROM copy_traders
                WHERE is_active = 1
                """
            )
            return [row["trader_address"] for row in rows]
        finally:
            await self.db.release_connection(conn)

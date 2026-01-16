"""Price alert repository for database operations."""

from typing import Optional, List
from datetime import datetime

from database.connection import Database
from database.models import PriceAlert, AlertDirection


class PriceAlertRepository:
    """Repository for price alert operations."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        user_id: int,
        token_id: str,
        market_condition_id: str,
        outcome: str,
        target_price: float,
        direction: AlertDirection,
        market_question: Optional[str] = None,
        note: Optional[str] = None,
    ) -> PriceAlert:
        """Create a new price alert."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            INSERT INTO price_alerts (
                user_id, token_id, market_condition_id, market_question,
                outcome, target_price, direction, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                token_id,
                market_condition_id,
                market_question,
                outcome,
                target_price,
                direction.value,
                note,
            ),
        )
        await conn.commit()

        return await self.get_by_id(cursor.lastrowid)

    async def get_by_id(self, alert_id: int) -> Optional[PriceAlert]:
        """Get price alert by ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM price_alerts WHERE id = ?",
            (alert_id,),
        )
        row = await cursor.fetchone()
        if row:
            return PriceAlert.from_row(row)
        return None

    async def get_user_alerts(
        self,
        user_id: int,
        active_only: bool = True,
    ) -> List[PriceAlert]:
        """Get all alerts for a user."""
        conn = await self.db.get_connection()

        if active_only:
            cursor = await conn.execute(
                """
                SELECT * FROM price_alerts
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT * FROM price_alerts
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            )

        rows = await cursor.fetchall()
        return [PriceAlert.from_row(row) for row in rows]

    async def get_all_active(self) -> List[PriceAlert]:
        """Get all active price alerts."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM price_alerts
            WHERE is_active = 1
            ORDER BY created_at ASC
            """
        )
        rows = await cursor.fetchall()
        return [PriceAlert.from_row(row) for row in rows]

    async def get_active_for_token(self, token_id: str) -> List[PriceAlert]:
        """Get all active alerts for a specific token."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM price_alerts
            WHERE token_id = ? AND is_active = 1
            """,
            (token_id,),
        )
        rows = await cursor.fetchall()
        return [PriceAlert.from_row(row) for row in rows]

    async def get_alerts_for_market(
        self,
        user_id: int,
        market_condition_id: str,
        active_only: bool = True,
    ) -> List[PriceAlert]:
        """Get alerts for a specific market."""
        conn = await self.db.get_connection()

        if active_only:
            cursor = await conn.execute(
                """
                SELECT * FROM price_alerts
                WHERE user_id = ? AND market_condition_id = ? AND is_active = 1
                ORDER BY target_price ASC
                """,
                (user_id, market_condition_id),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT * FROM price_alerts
                WHERE user_id = ? AND market_condition_id = ?
                ORDER BY created_at DESC
                """,
                (user_id, market_condition_id),
            )

        rows = await cursor.fetchall()
        return [PriceAlert.from_row(row) for row in rows]

    async def update(
        self,
        alert_id: int,
        target_price: Optional[float] = None,
        direction: Optional[AlertDirection] = None,
        note: Optional[str] = None,
    ) -> Optional[PriceAlert]:
        """Update a price alert."""
        conn = await self.db.get_connection()

        updates = []
        params = []

        if target_price is not None:
            updates.append("target_price = ?")
            params.append(target_price)

        if direction is not None:
            updates.append("direction = ?")
            params.append(direction.value)

        if note is not None:
            updates.append("note = ?")
            params.append(note)

        if not updates:
            return await self.get_by_id(alert_id)

        params.append(alert_id)
        query = f"UPDATE price_alerts SET {', '.join(updates)} WHERE id = ?"

        await conn.execute(query, params)
        await conn.commit()

        return await self.get_by_id(alert_id)

    async def deactivate(self, alert_id: int) -> None:
        """Deactivate a price alert."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE price_alerts SET is_active = 0 WHERE id = ?",
            (alert_id,),
        )
        await conn.commit()

    async def mark_triggered(self, alert_id: int) -> None:
        """Mark alert as triggered."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE price_alerts
            SET is_active = 0, triggered_at = ?
            WHERE id = ?
            """,
            (datetime.utcnow(), alert_id),
        )
        await conn.commit()

    async def delete(self, alert_id: int) -> bool:
        """Delete a price alert."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "DELETE FROM price_alerts WHERE id = ?",
            (alert_id,),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def delete_user_alerts(self, user_id: int) -> int:
        """Delete all alerts for a user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "DELETE FROM price_alerts WHERE user_id = ?",
            (user_id,),
        )
        await conn.commit()
        return cursor.rowcount

    async def count_user_alerts(self, user_id: int, active_only: bool = True) -> int:
        """Count alerts for a user."""
        conn = await self.db.get_connection()

        if active_only:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM price_alerts WHERE user_id = ? AND is_active = 1",
                (user_id,),
            )
        else:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM price_alerts WHERE user_id = ?",
                (user_id,),
            )

        row = await cursor.fetchone()
        return row[0] if row else 0

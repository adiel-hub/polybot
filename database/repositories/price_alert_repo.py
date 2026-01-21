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
        try:
            alert_id = await conn.fetchval(
                """
                INSERT INTO price_alerts (
                    user_id, token_id, market_condition_id, market_question,
                    outcome, target_price, direction, note
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                user_id, token_id, market_condition_id, market_question,
                outcome, target_price, direction.value, note,
            )
            return await self.get_by_id(alert_id)
        finally:
            await self.db.release_connection(conn)

    async def get_by_id(self, alert_id: int) -> Optional[PriceAlert]:
        """Get price alert by ID."""
        conn = await self.db.get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM price_alerts WHERE id = $1",
                alert_id,
            )
            if row:
                return PriceAlert.from_row(row)
            return None
        finally:
            await self.db.release_connection(conn)

    async def get_user_alerts(
        self,
        user_id: int,
        active_only: bool = True,
    ) -> List[PriceAlert]:
        """Get all alerts for a user."""
        conn = await self.db.get_connection()
        try:
            if active_only:
                rows = await conn.fetch(
                    """
                    SELECT * FROM price_alerts
                    WHERE user_id = $1 AND is_active = TRUE
                    ORDER BY created_at DESC
                    """,
                    user_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM price_alerts
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    """,
                    user_id,
                )

            return [PriceAlert.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def get_all_active(self) -> List[PriceAlert]:
        """Get all active price alerts."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM price_alerts
                WHERE is_active = TRUE
                ORDER BY created_at ASC
                """
            )
            return [PriceAlert.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def get_active_for_token(self, token_id: str) -> List[PriceAlert]:
        """Get all active alerts for a specific token."""
        conn = await self.db.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM price_alerts
                WHERE token_id = $1 AND is_active = TRUE
                """,
                token_id,
            )
            return [PriceAlert.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def get_alerts_for_market(
        self,
        user_id: int,
        market_condition_id: str,
        active_only: bool = True,
    ) -> List[PriceAlert]:
        """Get alerts for a specific market."""
        conn = await self.db.get_connection()
        try:
            if active_only:
                rows = await conn.fetch(
                    """
                    SELECT * FROM price_alerts
                    WHERE user_id = $1 AND market_condition_id = $2 AND is_active = TRUE
                    ORDER BY target_price ASC
                    """,
                    user_id, market_condition_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM price_alerts
                    WHERE user_id = $1 AND market_condition_id = $2
                    ORDER BY created_at DESC
                    """,
                    user_id, market_condition_id,
                )

            return [PriceAlert.from_row(row) for row in rows]
        finally:
            await self.db.release_connection(conn)

    async def update(
        self,
        alert_id: int,
        target_price: Optional[float] = None,
        direction: Optional[AlertDirection] = None,
        note: Optional[str] = None,
    ) -> Optional[PriceAlert]:
        """Update a price alert."""
        conn = await self.db.get_connection()
        try:
            updates = []
            params = []
            param_num = 1

            if target_price is not None:
                updates.append(f"target_price = ${param_num}")
                params.append(target_price)
                param_num += 1

            if direction is not None:
                updates.append(f"direction = ${param_num}")
                params.append(direction.value)
                param_num += 1

            if note is not None:
                updates.append(f"note = ${param_num}")
                params.append(note)
                param_num += 1

            if not updates:
                return await self.get_by_id(alert_id)

            params.append(alert_id)
            query = f"UPDATE price_alerts SET {', '.join(updates)} WHERE id = ${param_num}"

            await conn.execute(query, *params)

            return await self.get_by_id(alert_id)
        finally:
            await self.db.release_connection(conn)

    async def deactivate(self, alert_id: int) -> None:
        """Deactivate a price alert."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                "UPDATE price_alerts SET is_active = FALSE WHERE id = $1",
                alert_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def mark_triggered(self, alert_id: int) -> None:
        """Mark alert as triggered."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                """
                UPDATE price_alerts
                SET is_active = FALSE, triggered_at = $1
                WHERE id = $2
                """,
                datetime.utcnow(), alert_id,
            )
        finally:
            await self.db.release_connection(conn)

    async def delete(self, alert_id: int) -> bool:
        """Delete a price alert."""
        conn = await self.db.get_connection()
        try:
            result = await conn.execute(
                "DELETE FROM price_alerts WHERE id = $1",
                alert_id,
            )
            # Parse result like "DELETE 1" to get rowcount
            rowcount = int(result.split()[-1]) if result else 0
            return rowcount > 0
        finally:
            await self.db.release_connection(conn)

    async def delete_user_alerts(self, user_id: int) -> int:
        """Delete all alerts for a user."""
        conn = await self.db.get_connection()
        try:
            result = await conn.execute(
                "DELETE FROM price_alerts WHERE user_id = $1",
                user_id,
            )
            # Parse result like "DELETE 5" to get rowcount
            return int(result.split()[-1]) if result else 0
        finally:
            await self.db.release_connection(conn)

    async def count_user_alerts(self, user_id: int, active_only: bool = True) -> int:
        """Count alerts for a user."""
        conn = await self.db.get_connection()
        try:
            if active_only:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM price_alerts WHERE user_id = $1 AND is_active = TRUE",
                    user_id,
                )
            else:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM price_alerts WHERE user_id = $1",
                    user_id,
                )

            return count if count else 0
        finally:
            await self.db.release_connection(conn)

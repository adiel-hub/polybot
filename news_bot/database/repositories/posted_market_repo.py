"""Repository for posted market operations."""

from typing import Optional, List
from datetime import datetime
import json

from database.connection import Database
from news_bot.database.models.posted_market import PostedMarket


class PostedMarketRepository:
    """Repository for posted market operations."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        condition_id: str,
        question: str,
        event_id: Optional[str] = None,
        category: Optional[str] = None,
        article_title: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        market_created_at: Optional[datetime] = None,
        article_tokens_used: Optional[int] = None,
        research_sources: Optional[List[str]] = None,
    ) -> PostedMarket:
        """Create a new posted market record."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            INSERT INTO posted_markets (
                condition_id, event_id, question, category,
                article_title, telegram_message_id, market_created_at,
                article_tokens_used, research_sources
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                condition_id,
                event_id,
                question,
                category,
                article_title,
                telegram_message_id,
                market_created_at.isoformat() if market_created_at else None,
                article_tokens_used,
                json.dumps(research_sources) if research_sources else None,
            ),
        )
        await conn.commit()

        return await self.get_by_id(cursor.lastrowid)

    async def get_by_id(self, posted_id: int) -> Optional[PostedMarket]:
        """Get posted market by ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM posted_markets WHERE id = ?",
            (posted_id,),
        )
        row = await cursor.fetchone()
        if row:
            return PostedMarket.from_row(row)
        return None

    async def get_by_condition_id(self, condition_id: str) -> Optional[PostedMarket]:
        """Get posted market by Polymarket condition ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM posted_markets WHERE condition_id = ?",
            (condition_id,),
        )
        row = await cursor.fetchone()
        if row:
            return PostedMarket.from_row(row)
        return None

    async def exists(self, condition_id: str) -> bool:
        """Check if a market has already been posted."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT 1 FROM posted_markets WHERE condition_id = ?",
            (condition_id,),
        )
        row = await cursor.fetchone()
        return row is not None

    async def get_recent(self, limit: int = 20) -> List[PostedMarket]:
        """Get recently posted markets."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM posted_markets
            ORDER BY posted_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [PostedMarket.from_row(row) for row in rows]

    async def count_total(self) -> int:
        """Count total posted markets."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT COUNT(*) as count FROM posted_markets"
        )
        row = await cursor.fetchone()
        return row["count"] if row else 0

    async def count_today(self) -> int:
        """Count markets posted today."""
        conn = await self.db.get_connection()
        today = datetime.now().date().isoformat()
        cursor = await conn.execute(
            """
            SELECT COUNT(*) as count FROM posted_markets
            WHERE date(posted_at) = ?
            """,
            (today,),
        )
        row = await cursor.fetchone()
        return row["count"] if row else 0

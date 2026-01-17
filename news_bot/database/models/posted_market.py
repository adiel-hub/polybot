"""Posted market model for tracking which markets have been published."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import json


@dataclass
class PostedMarket:
    """Represents a market that has been posted to the news channel."""

    id: int
    condition_id: str
    event_id: Optional[str]
    question: str
    category: Optional[str]
    article_title: Optional[str]
    telegram_message_id: Optional[int]
    market_created_at: Optional[datetime]
    posted_at: datetime
    article_tokens_used: Optional[int]
    research_sources: List[str]

    @classmethod
    def from_row(cls, row: tuple) -> "PostedMarket":
        """Create PostedMarket from database row."""
        return cls(
            id=row[0],
            condition_id=row[1],
            event_id=row[2],
            question=row[3],
            category=row[4],
            article_title=row[5],
            telegram_message_id=row[6],
            market_created_at=datetime.fromisoformat(row[7]) if row[7] else None,
            posted_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now(),
            article_tokens_used=row[9],
            research_sources=json.loads(row[10]) if row[10] else [],
        )

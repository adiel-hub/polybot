"""Price alert model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class AlertDirection(str, Enum):
    """Direction for price alert trigger."""
    ABOVE = "ABOVE"  # Trigger when price goes above target
    BELOW = "BELOW"  # Trigger when price goes below target


@dataclass
class PriceAlert:
    """Price alert data model."""

    id: int
    user_id: int
    token_id: str
    market_condition_id: str
    market_question: Optional[str]
    outcome: str  # YES or NO
    target_price: float
    direction: AlertDirection
    is_active: bool
    triggered_at: Optional[datetime]
    created_at: datetime
    note: Optional[str]  # Optional user note for the alert

    @classmethod
    def from_row(cls, row) -> "PriceAlert":
        """Create PriceAlert from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            token_id=row["token_id"],
            market_condition_id=row["market_condition_id"],
            market_question=row["market_question"],
            outcome=row["outcome"],
            target_price=row["target_price"],
            direction=AlertDirection(row["direction"]),
            is_active=bool(row["is_active"]),
            triggered_at=row["triggered_at"],
            created_at=row["created_at"],
            note=row["note"],
        )

    @property
    def target_price_cents(self) -> float:
        """Get target price in cents (percentage)."""
        return self.target_price * 100

    @property
    def direction_emoji(self) -> str:
        """Get emoji for direction."""
        return "📈" if self.direction == AlertDirection.ABOVE else "📉"

    @property
    def direction_text(self) -> str:
        """Get human-readable direction text."""
        return "rises above" if self.direction == AlertDirection.ABOVE else "drops below"

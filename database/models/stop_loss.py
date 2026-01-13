"""Stop loss order model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class StopLoss:
    """Stop loss order data model."""

    id: int
    user_id: int
    position_id: int
    token_id: str
    trigger_price: float
    sell_percentage: float
    is_active: bool
    triggered_at: Optional[datetime]
    resulting_order_id: Optional[int]
    created_at: datetime

    @classmethod
    def from_row(cls, row) -> "StopLoss":
        """Create StopLoss from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            position_id=row["position_id"],
            token_id=row["token_id"],
            trigger_price=row["trigger_price"],
            sell_percentage=row["sell_percentage"],
            is_active=bool(row["is_active"]),
            triggered_at=row["triggered_at"],
            resulting_order_id=row["resulting_order_id"],
            created_at=row["created_at"],
        )

    @property
    def trigger_price_cents(self) -> float:
        """Get trigger price in cents (percentage)."""
        return self.trigger_price * 100

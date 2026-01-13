"""Order model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    FOK = "FOK"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class Outcome(str, Enum):
    YES = "YES"
    NO = "NO"


@dataclass
class Order:
    """Order data model."""

    id: int
    user_id: int
    polymarket_order_id: Optional[str]
    market_condition_id: str
    market_question: Optional[str]
    token_id: str
    side: OrderSide
    order_type: OrderType
    price: Optional[float]
    size: float
    filled_size: float
    status: OrderStatus
    outcome: Outcome
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    executed_at: Optional[datetime]

    @classmethod
    def from_row(cls, row) -> "Order":
        """Create Order from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            polymarket_order_id=row["polymarket_order_id"],
            market_condition_id=row["market_condition_id"],
            market_question=row["market_question"],
            token_id=row["token_id"],
            side=OrderSide(row["side"]),
            order_type=OrderType(row["order_type"]),
            price=row["price"],
            size=row["size"],
            filled_size=row["filled_size"] or 0.0,
            status=OrderStatus(row["status"]),
            outcome=Outcome(row["outcome"]) if row["outcome"] else None,
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            executed_at=row["executed_at"],
        )

    @property
    def is_open(self) -> bool:
        """Check if order is still open."""
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)

    @property
    def fill_percentage(self) -> float:
        """Get fill percentage."""
        if self.size == 0:
            return 0.0
        return (self.filled_size / self.size) * 100

    @property
    def remaining_size(self) -> float:
        """Get remaining unfilled size."""
        return self.size - self.filled_size

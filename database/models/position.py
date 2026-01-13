"""Position model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Position:
    """Position data model."""

    id: int
    user_id: int
    market_condition_id: str
    market_question: Optional[str]
    token_id: str
    outcome: str  # YES or NO
    size: float
    average_entry_price: float
    current_price: Optional[float]
    unrealized_pnl: Optional[float]
    realized_pnl: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row) -> "Position":
        """Create Position from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            market_condition_id=row["market_condition_id"],
            market_question=row["market_question"],
            token_id=row["token_id"],
            outcome=row["outcome"],
            size=row["size"],
            average_entry_price=row["average_entry_price"],
            current_price=row["current_price"],
            unrealized_pnl=row["unrealized_pnl"],
            realized_pnl=row["realized_pnl"] or 0.0,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @property
    def cost_basis(self) -> float:
        """Get total cost basis."""
        return self.size * self.average_entry_price

    @property
    def current_value(self) -> float:
        """Get current position value."""
        if self.current_price is None:
            return self.cost_basis
        return self.size * self.current_price

    @property
    def pnl_percentage(self) -> float:
        """Get P&L percentage."""
        if self.cost_basis == 0:
            return 0.0
        if self.unrealized_pnl is None:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100

"""Copy trader model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CopyTrader:
    """Copy trader subscription data model."""

    id: int
    user_id: int
    trader_address: str
    trader_name: Optional[str]
    allocation: float  # Percentage of balance to use
    max_trade_size: Optional[float]
    is_active: bool
    total_trades_copied: int
    total_pnl: float
    last_trade_at: Optional[datetime]
    created_at: datetime

    @classmethod
    def from_row(cls, row) -> "CopyTrader":
        """Create CopyTrader from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            trader_address=row["trader_address"],
            trader_name=row["trader_name"],
            allocation=row["allocation"],
            max_trade_size=row["max_trade_size"],
            is_active=bool(row["is_active"]),
            total_trades_copied=row["total_trades_copied"] or 0,
            total_pnl=row["total_pnl"] or 0.0,
            last_trade_at=row["last_trade_at"],
            created_at=row["created_at"],
        )

    @property
    def short_address(self) -> str:
        """Get shortened trader address."""
        return f"{self.trader_address[:6]}...{self.trader_address[-4:]}"

    @property
    def display_name(self) -> str:
        """Get display name for trader."""
        if self.trader_name:
            return self.trader_name
        return self.short_address

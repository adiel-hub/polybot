"""Referral commission model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ReferralCommission:
    """Referral commission data model."""

    id: int
    referrer_id: int
    referee_id: int
    order_id: int
    tier: int  # 1, 2, or 3
    trade_amount: float
    trade_fee: float
    commission_rate: float
    commission_amount: float
    created_at: datetime

    @classmethod
    def from_row(cls, row) -> "ReferralCommission":
        """Create ReferralCommission from database row."""
        return cls(
            id=row["id"],
            referrer_id=row["referrer_id"],
            referee_id=row["referee_id"],
            order_id=row["order_id"],
            tier=row["tier"],
            trade_amount=float(row["trade_amount"]),
            trade_fee=float(row["trade_fee"]),
            commission_rate=float(row["commission_rate"]),
            commission_amount=float(row["commission_amount"]),
            created_at=row["created_at"],
        )

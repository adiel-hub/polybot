"""Withdrawal model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Withdrawal:
    """Withdrawal data model."""

    id: int
    user_id: int
    from_address: str
    to_address: str
    amount: float
    tx_hash: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    confirmed_at: Optional[datetime]

    @classmethod
    def from_row(cls, row) -> "Withdrawal":
        """Create Withdrawal from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            from_address=row["from_address"],
            to_address=row["to_address"],
            amount=row["amount"],
            tx_hash=row["tx_hash"],
            status=row["status"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            confirmed_at=row["confirmed_at"],
        )

    @property
    def short_tx_hash(self) -> str:
        """Get shortened transaction hash."""
        if not self.tx_hash:
            return "Pending..."
        return f"{self.tx_hash[:10]}...{self.tx_hash[-6:]}"

    @property
    def short_to_address(self) -> str:
        """Get shortened destination address."""
        return f"{self.to_address[:6]}...{self.to_address[-4:]}"

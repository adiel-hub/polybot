"""Deposit model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Deposit:
    """Deposit data model."""

    id: int
    user_id: int
    wallet_address: str
    tx_hash: str
    amount: float
    block_number: int
    status: str
    detected_at: datetime

    @classmethod
    def from_row(cls, row) -> "Deposit":
        """Create Deposit from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            wallet_address=row["wallet_address"],
            tx_hash=row["tx_hash"],
            amount=row["amount"],
            block_number=row["block_number"],
            status=row["status"],
            detected_at=row["detected_at"],
        )

    @property
    def short_tx_hash(self) -> str:
        """Get shortened transaction hash."""
        return f"{self.tx_hash[:10]}...{self.tx_hash[-6:]}"

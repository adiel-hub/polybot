"""Wallet model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Wallet:
    """Wallet data model."""

    id: int
    user_id: int
    address: str
    encrypted_private_key: bytes
    encryption_salt: bytes
    usdc_balance: float
    last_balance_check: Optional[datetime]
    api_key_encrypted: Optional[bytes]
    api_secret_encrypted: Optional[bytes]
    api_passphrase_encrypted: Optional[bytes]
    created_at: datetime

    @classmethod
    def from_row(cls, row) -> "Wallet":
        """Create Wallet from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            address=row["address"],
            encrypted_private_key=row["encrypted_private_key"],
            encryption_salt=row["encryption_salt"],
            usdc_balance=row["usdc_balance"] or 0.0,
            last_balance_check=row["last_balance_check"],
            api_key_encrypted=row["api_key_encrypted"],
            api_secret_encrypted=row["api_secret_encrypted"],
            api_passphrase_encrypted=row["api_passphrase_encrypted"],
            created_at=row["created_at"],
        )

    @property
    def short_address(self) -> str:
        """Get shortened wallet address."""
        return f"{self.address[:6]}...{self.address[-4:]}"

    @property
    def has_api_credentials(self) -> bool:
        """Check if wallet has Polymarket API credentials."""
        return all([
            self.api_key_encrypted,
            self.api_secret_encrypted,
            self.api_passphrase_encrypted,
        ])

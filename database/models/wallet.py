"""Wallet model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Wallet:
    """Wallet data model."""

    id: int
    user_id: int
    address: str  # Primary address (Safe for SAFE type, EOA for EOA type)
    eoa_address: Optional[str]  # Signer address (for Safe wallets)
    wallet_type: str  # "EOA" or "SAFE"
    safe_deployed: bool  # Whether Safe contract is deployed
    usdc_approved: bool  # Whether USDC allowance is set for CTF Exchange
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
        # Handle both dict-like and sqlite3.Row objects
        # sqlite3.Row doesn't have .get() method, so use try/except for optional fields
        try:
            eoa_address = row["eoa_address"]
        except (KeyError, IndexError):
            eoa_address = None

        try:
            wallet_type = row["wallet_type"] or "EOA"
        except (KeyError, IndexError):
            wallet_type = "EOA"

        try:
            safe_deployed = bool(row["safe_deployed"])
        except (KeyError, IndexError):
            safe_deployed = False

        try:
            usdc_approved = bool(row["usdc_approved"])
        except (KeyError, IndexError):
            usdc_approved = False

        return cls(
            id=row["id"],
            user_id=row["user_id"],
            address=row["address"],
            eoa_address=eoa_address,
            wallet_type=wallet_type,
            safe_deployed=safe_deployed,
            usdc_approved=usdc_approved,
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

    @property
    def is_safe_wallet(self) -> bool:
        """Check if this is a Safe wallet."""
        return self.wallet_type == "SAFE"

    @property
    def signer_address(self) -> str:
        """Get the signer address (EOA that signs transactions)."""
        return self.eoa_address if self.eoa_address else self.address

    @property
    def funder_address(self) -> str:
        """Get the funder address (holds funds, used for CLOB)."""
        return self.address

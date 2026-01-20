"""Wallet repository for database operations."""

from typing import Optional, List
from datetime import datetime

from database.connection import Database
from database.models import Wallet


class WalletRepository:
    """Repository for wallet operations."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        user_id: int,
        address: str,
        encrypted_private_key: bytes,
        encryption_salt: bytes,
        eoa_address: Optional[str] = None,
        wallet_type: str = "EOA",
    ) -> Wallet:
        """Create a new wallet."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            INSERT INTO wallets (user_id, address, eoa_address, wallet_type, encrypted_private_key, encryption_salt)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, address, eoa_address, wallet_type, encrypted_private_key, encryption_salt),
        )
        await conn.commit()

        return await self.get_by_id(cursor.lastrowid)

    async def get_by_id(self, wallet_id: int) -> Optional[Wallet]:
        """Get wallet by ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM wallets WHERE id = ?",
            (wallet_id,),
        )
        row = await cursor.fetchone()
        if row:
            return Wallet.from_row(row)
        return None

    async def get_by_user_id(self, user_id: int) -> Optional[Wallet]:
        """Get wallet by user ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM wallets WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            return Wallet.from_row(row)
        return None

    async def get_by_address(self, address: str) -> Optional[Wallet]:
        """Get wallet by address."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM wallets WHERE LOWER(address) = LOWER(?)",
            (address,),
        )
        row = await cursor.fetchone()
        if row:
            return Wallet.from_row(row)
        return None

    async def update_balance(self, wallet_id: int, new_balance: float) -> None:
        """Update wallet USDC balance."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE wallets
            SET usdc_balance = ?,
                last_balance_check = ?
            WHERE id = ?
            """,
            (new_balance, datetime.utcnow(), wallet_id),
        )
        await conn.commit()

    async def add_balance(self, wallet_id: int, amount: float) -> None:
        """Add amount to wallet balance."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE wallets
            SET usdc_balance = usdc_balance + ?,
                last_balance_check = ?
            WHERE id = ?
            """,
            (amount, datetime.utcnow(), wallet_id),
        )
        await conn.commit()

    async def subtract_balance(self, wallet_id: int, amount: float) -> None:
        """Subtract amount from wallet balance."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE wallets
            SET usdc_balance = usdc_balance - ?,
                last_balance_check = ?
            WHERE id = ?
            """,
            (amount, datetime.utcnow(), wallet_id),
        )
        await conn.commit()

    async def update_api_credentials(
        self,
        wallet_id: int,
        api_key_encrypted: bytes,
        api_secret_encrypted: bytes,
        api_passphrase_encrypted: bytes,
    ) -> None:
        """Update Polymarket API credentials."""
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE wallets
            SET api_key_encrypted = ?,
                api_secret_encrypted = ?,
                api_passphrase_encrypted = ?
            WHERE id = ?
            """,
            (api_key_encrypted, api_secret_encrypted, api_passphrase_encrypted, wallet_id),
        )
        await conn.commit()

    async def get_all_active(self) -> List[Wallet]:
        """Get all wallets for active users."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT w.* FROM wallets w
            JOIN users u ON w.user_id = u.id
            WHERE u.is_active = 1
            """
        )
        rows = await cursor.fetchall()
        return [Wallet.from_row(row) for row in rows]

    async def get_all_addresses(self) -> List[str]:
        """Get all wallet addresses."""
        conn = await self.db.get_connection()
        cursor = await conn.execute("SELECT address FROM wallets")
        rows = await cursor.fetchall()
        return [row["address"] for row in rows]

    async def mark_safe_deployed(self, wallet_id: int) -> None:
        """Mark Safe wallet as deployed."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE wallets SET safe_deployed = 1 WHERE id = ?",
            (wallet_id,),
        )
        await conn.commit()

    async def reset_safe_deployed(self, wallet_id: int) -> None:
        """Reset Safe deployed flag (e.g., if on-chain state doesn't match)."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE wallets SET safe_deployed = 0 WHERE id = ?",
            (wallet_id,),
        )
        await conn.commit()

    async def mark_usdc_approved(self, wallet_id: int) -> None:
        """Mark wallet as having all required approvals set for Polymarket trading."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE wallets SET usdc_approved = 1 WHERE id = ?",
            (wallet_id,),
        )
        await conn.commit()

    async def reset_usdc_approved(self, wallet_id: int) -> None:
        """Reset USDC approval flag (e.g., to force re-approval)."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE wallets SET usdc_approved = 0 WHERE id = ?",
            (wallet_id,),
        )
        await conn.commit()

    async def get_undeployed_safe_wallets(self) -> List[Wallet]:
        """Get all Safe wallets that haven't been deployed yet."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM wallets WHERE wallet_type = 'SAFE' AND safe_deployed = 0"
        )
        rows = await cursor.fetchall()
        return [Wallet.from_row(row) for row in rows]

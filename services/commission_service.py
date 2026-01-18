"""Operator commission service for platform fee collection."""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from web3 import Web3
from eth_account import Account

from database.connection import Database
from database.models import Wallet
from config import settings
from config.constants import USDC_E_ADDRESS, USDC_DECIMALS

logger = logging.getLogger(__name__)

# ERC20 transfer ABI
ERC20_TRANSFER_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
]


@dataclass
class CommissionCalculation:
    """Result of commission calculation."""
    original_amount: float
    commission_rate: float
    commission_amount: float
    net_trade_amount: float


@dataclass
class TransferResult:
    """Result of commission transfer."""
    success: bool
    tx_hash: Optional[str] = None
    error: Optional[str] = None


class CommissionService:
    """Service for calculating and collecting operator commissions on trades."""

    def __init__(self, db: Database):
        self.db = db
        self.commission_rate = settings.operator_commission_rate
        self.min_commission = settings.min_commission_amount
        self.operator_wallet = settings.operator_wallet_address

        # Initialize Web3 for transfers
        self.w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
        self.usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_E_ADDRESS),
            abi=ERC20_TRANSFER_ABI,
        )

        # Gas sponsor for commission transfers
        if settings.gas_sponsor_private_key:
            self.gas_sponsor_account = Account.from_key(settings.gas_sponsor_private_key)
        else:
            self.gas_sponsor_account = None

    def is_enabled(self) -> bool:
        """Check if commission collection is enabled."""
        return bool(self.operator_wallet and self.commission_rate > 0)

    def calculate_commission(
        self,
        trade_amount: float,
        user_id: Optional[int] = None,
    ) -> CommissionCalculation:
        """
        Calculate commission for a trade.

        Args:
            trade_amount: Trade amount in USDC
            user_id: Optional user ID for custom rates (future use)

        Returns:
            CommissionCalculation with all amounts
        """
        # Get rate (could be customized per user tier in future)
        rate = self._get_user_rate(user_id)

        # Calculate commission
        commission = trade_amount * rate

        # Apply minimum threshold - skip if below minimum
        if commission < self.min_commission:
            commission = 0.0

        # Net amount after commission
        net_amount = trade_amount - commission

        return CommissionCalculation(
            original_amount=trade_amount,
            commission_rate=rate,
            commission_amount=commission,
            net_trade_amount=net_amount,
        )

    def _get_user_rate(self, user_id: Optional[int]) -> float:
        """Get commission rate for user (for future tiered pricing)."""
        # Future: query user's tier/subscription level for different rates
        return self.commission_rate

    async def transfer_commission(
        self,
        from_private_key: str,
        amount: float,
    ) -> TransferResult:
        """
        Transfer commission USDC from user wallet to operator wallet.

        Args:
            from_private_key: User's wallet private key
            amount: Commission amount in USDC

        Returns:
            TransferResult with tx_hash or error
        """
        if not self.operator_wallet:
            return TransferResult(
                success=False,
                error="Operator wallet not configured",
            )

        if amount <= 0:
            return TransferResult(
                success=False,
                error="Invalid commission amount",
            )

        try:
            # Get sender account
            sender_account = Account.from_key(from_private_key)
            sender_address = sender_account.address

            # Convert to token units (6 decimals for USDC)
            amount_units = int(amount * (10 ** USDC_DECIMALS))

            # Check sender balance
            balance = self.usdc_contract.functions.balanceOf(sender_address).call()
            if balance < amount_units:
                return TransferResult(
                    success=False,
                    error=f"Insufficient USDC balance for commission",
                )

            # Check POL balance for gas
            pol_balance = self.w3.eth.get_balance(sender_address)
            min_gas_wei = self.w3.to_wei(0.005, "ether")  # ~0.005 POL for transfer

            if pol_balance < min_gas_wei:
                # Try to sponsor gas
                if self.gas_sponsor_account:
                    sponsor_result = await self._sponsor_gas(sender_address)
                    if not sponsor_result.success:
                        logger.warning(f"Gas sponsorship failed: {sponsor_result.error}")
                        # Continue anyway - might have just enough
                else:
                    logger.warning("Insufficient POL for commission transfer gas")

            # Build transfer transaction
            nonce = self.w3.eth.get_transaction_count(sender_address)
            gas_price = self.w3.eth.gas_price

            tx_data = self.usdc_contract.functions.transfer(
                Web3.to_checksum_address(self.operator_wallet),
                amount_units,
            )

            # Estimate gas
            try:
                estimated_gas = tx_data.estimate_gas({"from": sender_address})
            except Exception:
                estimated_gas = 100000  # Default gas for ERC20 transfer

            # Build transaction
            tx = tx_data.build_transaction({
                "from": sender_address,
                "nonce": nonce,
                "gas": int(estimated_gas * 1.2),
                "gasPrice": gas_price,
                "chainId": settings.chain_id,
            })

            # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, from_private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            logger.info(
                f"Commission transfer sent: ${amount:.4f} USDC "
                f"from {sender_address[:10]}... to {self.operator_wallet[:10]}... "
                f"TX: {tx_hash.hex()}"
            )

            return TransferResult(
                success=True,
                tx_hash=tx_hash.hex(),
            )

        except Exception as e:
            logger.error(f"Commission transfer failed: {e}")
            return TransferResult(
                success=False,
                error=str(e),
            )

    async def _sponsor_gas(self, to_address: str, amount_pol: float = 0.01) -> TransferResult:
        """Sponsor POL for gas to user wallet."""
        if not self.gas_sponsor_account:
            return TransferResult(success=False, error="No gas sponsor configured")

        try:
            nonce = self.w3.eth.get_transaction_count(self.gas_sponsor_account.address)
            gas_price = self.w3.eth.gas_price

            tx = {
                "from": self.gas_sponsor_account.address,
                "to": Web3.to_checksum_address(to_address),
                "value": self.w3.to_wei(amount_pol, "ether"),
                "nonce": nonce,
                "gas": 21000,
                "gasPrice": gas_price,
                "chainId": settings.chain_id,
            }

            signed_tx = self.w3.eth.account.sign_transaction(tx, self.gas_sponsor_account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Wait briefly for gas to arrive
            import asyncio
            await asyncio.sleep(3)

            return TransferResult(success=True, tx_hash=tx_hash.hex())

        except Exception as e:
            logger.error(f"Gas sponsorship failed: {e}")
            return TransferResult(success=False, error=str(e))

    async def record_commission(
        self,
        user_id: int,
        order_id: int,
        trade_type: str,
        calculation: CommissionCalculation,
        tx_hash: Optional[str] = None,
        status: str = "PENDING",
    ) -> int:
        """
        Record a commission in the database.

        Args:
            user_id: User ID
            order_id: Order ID
            trade_type: "BUY" or "SELL"
            calculation: Commission calculation result
            tx_hash: Blockchain transaction hash
            status: Commission status

        Returns:
            Commission record ID
        """
        conn = await self.db.get_connection()

        if tx_hash:
            status = "TRANSFERRED"
            transferred_at = datetime.utcnow().isoformat()
        else:
            transferred_at = None

        cursor = await conn.execute(
            """
            INSERT INTO operator_commissions
            (user_id, order_id, trade_type, trade_amount, commission_rate,
             commission_amount, net_trade_amount, tx_hash, status, transferred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                order_id,
                trade_type,
                calculation.original_amount,
                calculation.commission_rate,
                calculation.commission_amount,
                calculation.net_trade_amount,
                tx_hash,
                status,
                transferred_at,
            ),
        )
        await conn.commit()

        logger.info(
            f"Commission recorded: ${calculation.commission_amount:.4f} "
            f"from user {user_id} order {order_id} [{status}]"
        )

        return cursor.lastrowid

    async def update_commission_status(
        self,
        commission_id: int,
        status: str,
        tx_hash: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update commission record status."""
        conn = await self.db.get_connection()

        if status == "TRANSFERRED" and tx_hash:
            await conn.execute(
                """
                UPDATE operator_commissions
                SET status = ?, tx_hash = ?, transferred_at = ?
                WHERE id = ?
                """,
                (status, tx_hash, datetime.utcnow().isoformat(), commission_id),
            )
        elif status == "FAILED" and error_message:
            await conn.execute(
                """
                UPDATE operator_commissions
                SET status = ?, error_message = ?
                WHERE id = ?
                """,
                (status, error_message, commission_id),
            )
        else:
            await conn.execute(
                "UPDATE operator_commissions SET status = ? WHERE id = ?",
                (status, commission_id),
            )

        await conn.commit()
        return True

    async def get_pending_commissions(self) -> list:
        """Get all pending commission transfers for retry."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM operator_commissions
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_total_collected(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get total commissions collected.

        Returns:
            {
                "total_amount": 1234.56,
                "total_trades": 500,
                "total_transferred": 1200.00,
                "total_pending": 34.56,
            }
        """
        conn = await self.db.get_connection()

        query = """
            SELECT
                SUM(commission_amount) as total_amount,
                COUNT(*) as total_trades,
                SUM(CASE WHEN status = 'TRANSFERRED' THEN commission_amount ELSE 0 END) as total_transferred,
                SUM(CASE WHEN status = 'PENDING' THEN commission_amount ELSE 0 END) as total_pending
            FROM operator_commissions
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)

        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()

        return {
            "total_amount": row["total_amount"] or 0.0,
            "total_trades": row["total_trades"] or 0,
            "total_transferred": row["total_transferred"] or 0.0,
            "total_pending": row["total_pending"] or 0.0,
        }

    async def get_user_commissions(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list:
        """Get commission history for a specific user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM operator_commissions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

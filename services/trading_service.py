"""Trading service for order management."""

import logging
from typing import Optional, Dict, Any, List

from database.connection import Database
from database.repositories import (
    OrderRepository,
    PositionRepository,
    WalletRepository,
)
from database.models import Order, Position
from core.polymarket import PolymarketCLOB
from core.wallet import KeyEncryption

logger = logging.getLogger(__name__)


class TradingService:
    """Service for trading operations."""

    def __init__(
        self,
        db: Database,
        encryption: KeyEncryption,
    ):
        self.db = db
        self.order_repo = OrderRepository(db)
        self.position_repo = PositionRepository(db)
        self.wallet_repo = WalletRepository(db)
        self.encryption = encryption

    async def _get_clob_client(self, user_id: int) -> Optional[PolymarketCLOB]:
        """Get CLOB client for user."""
        wallet = await self.wallet_repo.get_by_user_id(user_id)
        if not wallet:
            return None

        private_key = self.encryption.decrypt(
            wallet.encrypted_private_key,
            wallet.encryption_salt,
        )

        client = PolymarketCLOB(
            private_key=private_key,
            funder_address=wallet.address,
        )

        # Initialize API credentials if we have them stored
        if wallet.has_api_credentials:
            api_key = self.encryption.decrypt(
                wallet.api_key_encrypted,
                wallet.encryption_salt,
            )
            api_secret = self.encryption.decrypt(
                wallet.api_secret_encrypted,
                wallet.encryption_salt,
            )
            api_passphrase = self.encryption.decrypt(
                wallet.api_passphrase_encrypted,
                wallet.encryption_salt,
            )
            client.set_api_credentials(api_key, api_secret, api_passphrase)
        else:
            # Initialize and store credentials
            await client.initialize()

            if client.api_credentials:
                creds = client.api_credentials
                enc_key, _ = self.encryption.encrypt(creds["api_key"])
                enc_secret, _ = self.encryption.encrypt(creds["api_secret"])
                enc_pass, _ = self.encryption.encrypt(creds["api_passphrase"])

                await self.wallet_repo.update_api_credentials(
                    wallet.id,
                    enc_key,
                    enc_secret,
                    enc_pass,
                )

        return client

    async def place_order(
        self,
        user_id: int,
        market_condition_id: str,
        token_id: str,
        outcome: str,
        order_type: str,
        amount: float,
        price: Optional[float] = None,
        market_question: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place a trading order.

        Args:
            user_id: User ID
            market_condition_id: Market condition ID
            token_id: Token ID to trade
            outcome: "YES" or "NO"
            order_type: "MARKET" or "LIMIT"
            amount: Amount to spend (market) or shares (limit)
            price: Limit price (required for limit orders)
            market_question: Market question for display

        Returns:
            Dict with order_id, status, error
        """
        # Check balance
        wallet = await self.wallet_repo.get_by_user_id(user_id)
        if not wallet:
            return {"success": False, "error": "Wallet not found"}

        if wallet.usdc_balance < amount and order_type == "MARKET":
            return {"success": False, "error": "Insufficient balance"}

        # Create order record
        db_order = await self.order_repo.create(
            user_id=user_id,
            market_condition_id=market_condition_id,
            token_id=token_id,
            side="BUY",
            order_type=order_type.upper(),
            size=amount,
            outcome=outcome,
            price=price,
            market_question=market_question,
        )

        try:
            # Get CLOB client
            client = await self._get_clob_client(user_id)
            if not client:
                await self.order_repo.update_status(
                    db_order.id,
                    "FAILED",
                    error_message="Failed to initialize trading client",
                )
                return {"success": False, "error": "Trading client error"}

            # Place order
            if order_type.upper() == "MARKET":
                result = await client.place_market_order(
                    token_id=token_id,
                    amount=amount,
                    side="BUY",
                )
            else:
                if price is None:
                    await self.order_repo.update_status(
                        db_order.id,
                        "FAILED",
                        error_message="Price required for limit order",
                    )
                    return {"success": False, "error": "Price required for limit order"}

                result = await client.place_limit_order(
                    token_id=token_id,
                    price=price,
                    size=amount,
                    side="BUY",
                )

            if result.success:
                # Update order with Polymarket ID
                await self.order_repo.update_polymarket_id(
                    db_order.id,
                    result.order_id,
                )
                await self.order_repo.update_status(
                    db_order.id,
                    result.status or "OPEN",
                )

                # If market order filled, update position and balance
                if order_type.upper() == "MARKET" and result.status == "FILLED":
                    # Deduct from balance
                    await self.wallet_repo.subtract_balance(wallet.id, amount)

                    # Create/update position
                    # Calculate shares bought (amount / price)
                    best_price = await client.get_best_price(token_id, "BUY")
                    if best_price:
                        shares = amount / best_price
                        await self.position_repo.create_or_update(
                            user_id=user_id,
                            market_condition_id=market_condition_id,
                            token_id=token_id,
                            outcome=outcome,
                            size=shares,
                            average_entry_price=best_price,
                            market_question=market_question,
                        )

                return {
                    "success": True,
                    "order_id": result.order_id,
                    "status": result.status,
                    "db_order_id": db_order.id,
                }
            else:
                await self.order_repo.update_status(
                    db_order.id,
                    "FAILED",
                    error_message=result.error,
                )
                return {"success": False, "error": result.error}

        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            await self.order_repo.update_status(
                db_order.id,
                "FAILED",
                error_message=str(e),
            )
            return {"success": False, "error": str(e)}

    async def cancel_order(self, user_id: int, order_id: int) -> bool:
        """Cancel an open order."""
        order = await self.order_repo.get_by_id(order_id)
        if not order or order.user_id != user_id:
            return False

        if not order.polymarket_order_id:
            await self.order_repo.update_status(order_id, "CANCELLED")
            return True

        client = await self._get_clob_client(user_id)
        if not client:
            return False

        success = await client.cancel_order(order.polymarket_order_id)

        if success:
            await self.order_repo.update_status(order_id, "CANCELLED")

        return success

    async def get_open_orders(self, user_id: int) -> List[Order]:
        """Get open orders for user."""
        return await self.order_repo.get_open_orders(user_id)

    async def get_user_orders(
        self,
        user_id: int,
        limit: int = 20,
    ) -> List[Order]:
        """Get recent orders for user."""
        return await self.order_repo.get_user_orders(user_id, limit=limit)

    async def get_positions(self, user_id: int) -> List[Position]:
        """Get positions for user."""
        return await self.position_repo.get_user_positions(user_id)

    async def get_portfolio_value(self, user_id: int) -> float:
        """Get total portfolio value."""
        return await self.position_repo.get_total_value(user_id)

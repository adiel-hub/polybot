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
from config.constants import MIN_ORDER_AMOUNT

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

        # Cache CLOB clients per user_id to avoid reinitializing on every trade
        self._clob_clients: Dict[int, PolymarketCLOB] = {}

        # Import ReferralService here to avoid circular dependency
        from services.referral_service import ReferralService
        self.referral_service = ReferralService(db)

        # Commission service for operator fees
        from services.commission_service import CommissionService
        self.commission_service = CommissionService(db)

    async def _get_clob_client(self, user_id: int) -> Optional[PolymarketCLOB]:
        """
        Get CLOB client for user.

        Priority:
        1. Return from memory cache if available
        2. Load from DB (API credentials) and cache
        3. Initialize new credentials, save to DB, and cache (fallback)
        """
        # 1. Return cached client if available
        if user_id in self._clob_clients:
            return self._clob_clients[user_id]

        wallet = await self.wallet_repo.get_by_user_id(user_id)
        if not wallet:
            return None

        private_key = self.encryption.decrypt(
            wallet.encrypted_private_key,
            wallet.encryption_salt,
        )

        # Create CLOB client - use funder_address (EOA) for trading
        client = PolymarketCLOB(
            private_key=private_key,
            funder_address=wallet.funder_address or wallet.address,
        )

        # 2. Load API credentials from DB if available
        if wallet.has_api_credentials:
            try:
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
                logger.info(f"CLOB client loaded from DB for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to decrypt API credentials: {e}")
                # Fall through to initialize new credentials
                wallet.api_key_encrypted = None  # Force re-initialization

        # 3. Initialize and save to DB if no credentials loaded
        if not wallet.has_api_credentials or client._api_creds is None:
            logger.info(f"Initializing new CLOB credentials for user {user_id}")
            await client.initialize()

            if client.api_credentials:
                creds = client.api_credentials
                enc_key = self.encryption.encrypt_with_salt(creds["api_key"], wallet.encryption_salt)
                enc_secret = self.encryption.encrypt_with_salt(creds["api_secret"], wallet.encryption_salt)
                enc_pass = self.encryption.encrypt_with_salt(creds["api_passphrase"], wallet.encryption_salt)

                await self.wallet_repo.update_api_credentials(
                    wallet.id,
                    enc_key,
                    enc_secret,
                    enc_pass,
                )
                logger.info(f"CLOB credentials saved to DB for user {user_id}")

        # Cache the client
        self._clob_clients[user_id] = client

        return client

    def invalidate_clob_client(self, user_id: int) -> None:
        """Remove cached CLOB client (e.g., if credentials need refresh)."""
        if user_id in self._clob_clients:
            del self._clob_clients[user_id]
            logger.info(f"CLOB client cache invalidated for user {user_id}")

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
        # Calculate order value for validation
        if order_type.upper() == "MARKET":
            order_value = amount
        else:
            # Limit order: amount is shares, total cost = shares * price
            order_value = amount * price if price else amount

        # Validate minimum order amount (Polymarket requires $1 minimum)
        if order_value < MIN_ORDER_AMOUNT:
            return {
                "success": False,
                "error": f"Minimum order is ${MIN_ORDER_AMOUNT:.0f}. Your order: ${order_value:.2f}",
            }

        # Check balance
        wallet = await self.wallet_repo.get_by_user_id(user_id)
        if not wallet:
            return {"success": False, "error": "Wallet not found"}

        logger.info(f"[PLACE ORDER] User {user_id}: address={wallet.address[:10]}...")

        # Get real-time balance from blockchain
        from core.blockchain.balance import get_balance_service
        balance_service = get_balance_service()
        current_balance = balance_service.get_balance(wallet.address)

        if current_balance < amount and order_type == "MARKET":
            return {
                "success": False,
                "error": f"Insufficient balance: ${current_balance:.2f} < ${amount:.2f}"
            }

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

                    # Process referral commissions (instant on trade)
                    try:
                        await self.referral_service.process_trade_commission(
                            user_id=user_id,
                            order_id=db_order.id,
                            trade_amount=amount,
                        )
                    except Exception as e:
                        # Don't fail the order if commission processing fails
                        logger.error(f"Failed to process referral commission: {e}")

                    # Process operator commission (transfer to operator wallet)
                    await self._process_operator_commission(
                        user_id=user_id,
                        order_id=db_order.id,
                        trade_amount=amount,
                        trade_type="BUY",
                        wallet=wallet,
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
            logger.error(f"Order placement failed: {e}", exc_info=True)
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

    async def sell_position(
        self,
        user_id: int,
        position_id: int,
        token_id: str,
        size: float,
        market_condition_id: str,
    ) -> Dict[str, Any]:
        """
        Sell shares from a position.

        Args:
            user_id: User ID
            position_id: Position ID
            token_id: Token ID to sell
            size: Number of shares to sell
            market_condition_id: Market condition ID

        Returns:
            Dict with order_id, status, error
        """
        # Get position to verify ownership and size
        position = await self.position_repo.get_by_id(position_id)
        if not position or position.user_id != user_id:
            return {"success": False, "error": "Position not found"}

        if size > position.size:
            return {"success": False, "error": "Insufficient shares"}

        # Get wallet
        wallet = await self.wallet_repo.get_by_user_id(user_id)
        if not wallet:
            return {"success": False, "error": "Wallet not found"}

        logger.info(
            f"[SELL POSITION] User {user_id}: address={wallet.address[:10]}..."
        )
        logger.info(
            f"[SELL POSITION] token_id={token_id[:20]}..., size={size}, "
            f"position.size={position.size}, outcome={position.outcome}"
        )

        # Create sell order record
        db_order = await self.order_repo.create(
            user_id=user_id,
            market_condition_id=market_condition_id,
            token_id=token_id,
            side="SELL",
            order_type="MARKET",
            size=size,
            outcome=position.outcome,
            market_question=position.market_question,
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

            # Check CTF balance/allowance before selling
            logger.info(f"[SELL] Checking CTF balance/allowance for token {token_id[:20]}...")
            ctf_info = await client.check_ctf_balance_allowance(token_id)
            if ctf_info:
                # Balance is in raw units (6 decimals for CTF tokens)
                ctf_balance_raw = float(ctf_info.get("balance", 0))
                ctf_balance_shares = ctf_balance_raw / 1_000_000  # Convert to shares
                ctf_allowances = ctf_info.get("allowances", {})
                logger.info(
                    f"[SELL] CTF info: balance_raw={ctf_balance_raw}, balance_shares={ctf_balance_shares:.6f}, "
                    f"allowances={len(ctf_allowances)}, trying to sell={size}"
                )

                # Validate we have enough shares
                if ctf_balance_shares < size:
                    logger.error(
                        f"[SELL] Insufficient CTF balance! Have {ctf_balance_shares:.6f} shares, "
                        f"trying to sell {size:.6f} shares. Updating position to match on-chain."
                    )
                    # Update position in DB to match actual on-chain balance
                    if ctf_balance_shares > 0:
                        await self.position_repo.update_size(position_id, ctf_balance_shares)
                        logger.info(f"[SELL] Updated position {position_id} size to {ctf_balance_shares:.6f}")

                    await self.order_repo.update_status(
                        db_order.id,
                        "FAILED",
                        error_message=f"Insufficient shares: have {ctf_balance_shares:.4f}, need {size:.4f}",
                    )
                    return {
                        "success": False,
                        "error": f"Insufficient shares. You have {ctf_balance_shares:.4f} shares, but tried to sell {size:.4f}. Position has been updated.",
                    }

            # Place sell market order
            logger.info(f"[SELL] Placing market order: token={token_id[:20]}..., amount={size}, side=SELL")
            result = await client.place_market_order(
                token_id=token_id,
                amount=size,
                side="SELL",
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

                # If filled, update position and add to balance
                if result.status == "FILLED":
                    # Get sell price
                    sell_price = await client.get_best_price(token_id, "SELL")
                    if sell_price:
                        # Reduce position
                        await self.position_repo.reduce_position(
                            position_id,
                            size,
                            sell_price,
                        )

                        # Calculate proceeds and commission
                        wallet = await self.wallet_repo.get_by_user_id(user_id)
                        if wallet:
                            proceeds = size * sell_price

                            # Process operator commission on sell proceeds
                            commission_calc = await self._process_operator_commission(
                                user_id=user_id,
                                order_id=db_order.id,
                                trade_amount=proceeds,
                                trade_type="SELL",
                                wallet=wallet,
                            )

                            # Add NET proceeds to balance (after commission)
                            if commission_calc:
                                net_proceeds = commission_calc.net_trade_amount
                            else:
                                net_proceeds = proceeds

                            await self.wallet_repo.add_balance(wallet.id, net_proceeds)

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
            logger.error(f"Sell order failed: {e}")
            await self.order_repo.update_status(
                db_order.id,
                "FAILED",
                error_message=str(e),
            )
            return {"success": False, "error": str(e)}

    async def _process_operator_commission(
        self,
        user_id: int,
        order_id: int,
        trade_amount: float,
        trade_type: str,
        wallet,
    ):
        """
        Process operator commission for a filled trade.

        Calculates commission, transfers USDC to operator wallet, and records it.

        Args:
            user_id: User ID
            order_id: Order ID
            trade_amount: Trade amount in USDC
            trade_type: "BUY" or "SELL"
            wallet: User's wallet object

        Returns:
            CommissionCalculation or None if commission not applicable
        """
        try:
            # Check if commission is enabled
            if not self.commission_service.is_enabled():
                logger.debug("Operator commission not enabled (no wallet configured)")
                return None

            # Calculate commission
            commission_calc = self.commission_service.calculate_commission(trade_amount)

            # Skip if commission is below minimum threshold
            if commission_calc.commission_amount <= 0:
                logger.debug(f"Commission below minimum threshold for ${trade_amount:.2f} trade")
                return None

            logger.info(
                f"Processing operator commission: ${commission_calc.commission_amount:.4f} "
                f"({commission_calc.commission_rate * 100:.1f}%) on ${trade_amount:.2f} {trade_type}"
            )

            # Decrypt wallet private key for transfer
            private_key = self.encryption.decrypt(
                wallet.encrypted_private_key,
                wallet.encryption_salt,
            )

            # Transfer commission to operator wallet
            transfer_result = await self.commission_service.transfer_commission(
                from_private_key=private_key,
                amount=commission_calc.commission_amount,
            )

            if transfer_result.success:
                # Record successful commission transfer
                await self.commission_service.record_commission(
                    user_id=user_id,
                    order_id=order_id,
                    trade_type=trade_type,
                    calculation=commission_calc,
                    tx_hash=transfer_result.tx_hash,
                    status="TRANSFERRED",
                )
                logger.info(
                    f"Commission transferred: ${commission_calc.commission_amount:.4f} "
                    f"TX: {transfer_result.tx_hash}"
                )
            else:
                # Record failed commission (for retry later)
                commission_id = await self.commission_service.record_commission(
                    user_id=user_id,
                    order_id=order_id,
                    trade_type=trade_type,
                    calculation=commission_calc,
                    status="PENDING",
                )
                logger.warning(
                    f"Commission transfer failed, recorded as pending: "
                    f"${commission_calc.commission_amount:.4f} - {transfer_result.error}"
                )

            return commission_calc

        except Exception as e:
            # Don't fail the trade if commission processing fails
            logger.error(f"Failed to process operator commission: {e}")
            return None

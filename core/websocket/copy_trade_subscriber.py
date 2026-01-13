"""Copy trade subscriber for monitoring followed traders via WebSocket."""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Set

from database.connection import Database
from database.repositories import (
    CopyTraderRepository,
    UserRepository,
    WalletRepository,
)
from services import TradingService
from core.wallet import KeyEncryption
from core.websocket.manager import WebSocketManager

logger = logging.getLogger(__name__)


class CopyTradeSubscriber:
    """
    Subscribes to Polymarket user channel to monitor followed traders.

    Replaces the polling-based copy_trade_sync.py job with real-time trade detection.
    When a followed trader makes a trade, automatically mirrors it for followers.
    """

    def __init__(
        self,
        ws_manager: WebSocketManager,
        db: Database,
        encryption: KeyEncryption,
        user_ws_url: str,
        bot_send_message: Optional[Callable] = None,
    ):
        self.ws_manager = ws_manager
        self.db = db
        self.encryption = encryption
        self.user_ws_url = user_ws_url
        self.bot_send_message = bot_send_message

        # Track followed traders: trader_address -> list of subscriptions
        self._followed_traders: Dict[str, list] = {}
        # Track processed trade IDs to avoid duplicates
        self._processed_trades: Set[str] = set()

    async def start(self) -> None:
        """Start the copy trade subscriber."""
        # Register with WebSocket manager
        self.ws_manager.register_connection(
            name="polymarket_user",
            url=self.user_ws_url,
            message_handler=self._handle_user_message,
        )

        # Load initial subscriptions
        await self._refresh_subscriptions()
        logger.info("Copy trade subscriber started")

    async def _handle_user_message(
        self,
        connection_name: str,
        data: Dict[str, Any],
    ) -> None:
        """Handle incoming user WebSocket messages."""
        event_type = data.get("event_type") or data.get("type")

        # Handle trade events (order filled)
        if event_type in ("trade", "order_filled", "fill"):
            await self._handle_trade_event(data)

    async def _handle_trade_event(self, data: Dict[str, Any]) -> None:
        """Process a trade event from a followed trader."""
        try:
            # Extract trade details
            trader_address = data.get("maker") or data.get("user") or data.get("owner")
            trade_id = data.get("id") or data.get("trade_id") or data.get("order_id")

            if not trader_address:
                return

            # Normalize address
            trader_address = trader_address.lower()

            # Check if this trader is being followed
            if trader_address not in self._followed_traders:
                return

            # Skip if already processed
            if trade_id and trade_id in self._processed_trades:
                return

            if trade_id:
                self._processed_trades.add(trade_id)
                # Keep processed set bounded
                if len(self._processed_trades) > 10000:
                    self._processed_trades = set(list(self._processed_trades)[-5000:])

            # Extract trade parameters
            token_id = data.get("asset_id") or data.get("token_id")
            market_condition_id = data.get("market") or data.get("condition_id")
            side = data.get("side", "BUY")
            outcome = data.get("outcome", "YES")
            amount = float(data.get("size", 0) or data.get("amount", 0))
            price = float(data.get("price", 0))
            market_question = data.get("question") or data.get("title")

            if not token_id or amount <= 0:
                return

            # Calculate value (what the trader spent)
            trade_value = amount * price if price > 0 else amount

            logger.info(
                f"Trade detected from followed trader {trader_address[:10]}...: "
                f"{side} {amount:.2f} at {price:.2f}"
            )

            # Mirror trade for all followers
            subscriptions = self._followed_traders.get(trader_address, [])
            for subscription in subscriptions:
                if subscription.get("is_active"):
                    await self._mirror_trade(
                        subscription=subscription,
                        token_id=token_id,
                        market_condition_id=market_condition_id,
                        outcome=outcome,
                        trade_value=trade_value,
                        market_question=market_question,
                    )

        except Exception as e:
            logger.error(f"Failed to handle trade event: {e}")

    async def _mirror_trade(
        self,
        subscription: Dict[str, Any],
        token_id: str,
        market_condition_id: str,
        outcome: str,
        trade_value: float,
        market_question: Optional[str],
    ) -> None:
        """Mirror a trade for a follower."""
        try:
            wallet_repo = WalletRepository(self.db)
            user_repo = UserRepository(self.db)
            copy_repo = CopyTraderRepository(self.db)
            trading_service = TradingService(self.db, self.encryption)

            user_id = subscription["user_id"]

            # Get follower's wallet
            wallet = await wallet_repo.get_by_user_id(user_id)
            if not wallet:
                return

            # Calculate trade size based on allocation
            available_balance = wallet.usdc_balance
            max_trade = available_balance * (subscription["allocation"] / 100)

            if subscription.get("max_trade_size"):
                max_trade = min(max_trade, subscription["max_trade_size"])

            # Trade the smaller of: original trade value or max allowed
            trade_amount = min(trade_value, max_trade)

            if trade_amount < 1:  # Min trade $1
                logger.debug(f"Trade amount too small for user {user_id}: ${trade_amount:.2f}")
                return

            # Place mirror trade
            result = await trading_service.place_order(
                user_id=user_id,
                market_condition_id=market_condition_id,
                token_id=token_id,
                outcome=outcome,
                order_type="MARKET",
                amount=trade_amount,
                market_question=market_question,
            )

            if result.get("success"):
                # Record the copied trade
                await copy_repo.record_trade(subscription["id"])

                # Notify user
                if self.bot_send_message:
                    user = await user_repo.get_by_id(user_id)
                    if user:
                        await self.bot_send_message(
                            chat_id=user.telegram_id,
                            text=(
                                f"*Trade Copied!*\n\n"
                                f"From: {subscription.get('display_name', 'Trader')}\n"
                                f"Market: {(market_question or '')[:40]}...\n"
                                f"Side: {outcome}\n"
                                f"Amount: ${trade_amount:.2f}\n\n"
                                f"Order ID: `{result.get('order_id', 'N/A')}`"
                            ),
                            parse_mode="Markdown",
                        )

                logger.info(
                    f"Copied trade for user {user_id}: "
                    f"${trade_amount:.2f} {outcome}"
                )
            else:
                logger.error(
                    f"Failed to copy trade for user {user_id}: {result.get('error')}"
                )

        except Exception as e:
            logger.error(f"Failed to mirror trade for subscription {subscription['id']}: {e}")

    async def _refresh_subscriptions(self) -> None:
        """Refresh the list of followed traders."""
        try:
            copy_repo = CopyTraderRepository(self.db)

            # Get unique trader addresses
            trader_addresses = await copy_repo.get_unique_traders()

            # Clear and rebuild
            self._followed_traders.clear()

            for trader_address in trader_addresses:
                normalized = trader_address.lower()
                followers = await copy_repo.get_followers_for_trader(trader_address)

                self._followed_traders[normalized] = [
                    {
                        "id": sub.id,
                        "user_id": sub.user_id,
                        "allocation": sub.allocation,
                        "max_trade_size": sub.max_trade_size,
                        "is_active": sub.is_active,
                        "display_name": sub.display_name,
                    }
                    for sub in followers
                ]

            # Subscribe to user channel for all followed traders
            if trader_addresses and self.ws_manager.is_connected("polymarket_user"):
                # Build subscription message for user channel
                subscription_message = {
                    "markets": trader_addresses,  # trader addresses to monitor
                    "type": "USER",
                }
                await self.ws_manager.subscribe(
                    "polymarket_user",
                    trader_addresses,
                    subscription_message,
                )

            logger.info(f"Following {len(trader_addresses)} traders for copy trading")

        except Exception as e:
            logger.error(f"Failed to refresh copy trade subscriptions: {e}")

    async def add_subscription(self, subscription) -> None:
        """Add a new copy trading subscription."""
        trader_address = subscription.trader_address.lower()

        if trader_address not in self._followed_traders:
            self._followed_traders[trader_address] = []

        self._followed_traders[trader_address].append({
            "id": subscription.id,
            "user_id": subscription.user_id,
            "allocation": subscription.allocation,
            "max_trade_size": subscription.max_trade_size,
            "is_active": subscription.is_active,
            "display_name": subscription.display_name,
        })

        # Subscribe to this trader's activity
        if self.ws_manager.is_connected("polymarket_user"):
            subscription_message = {
                "markets": [subscription.trader_address],
                "type": "USER",
            }
            await self.ws_manager.subscribe(
                "polymarket_user",
                [subscription.trader_address],
                subscription_message,
            )

    async def remove_subscription(self, subscription_id: int) -> None:
        """Remove a copy trading subscription."""
        for trader_address, subscriptions in self._followed_traders.items():
            self._followed_traders[trader_address] = [
                s for s in subscriptions if s["id"] != subscription_id
            ]

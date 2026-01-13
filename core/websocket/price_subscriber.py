"""Price subscriber for real-time market price updates."""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Set

from database.connection import Database
from database.repositories import (
    StopLossRepository,
    PositionRepository,
    UserRepository,
)
from services import TradingService
from core.wallet import KeyEncryption
from core.websocket.manager import WebSocketManager

logger = logging.getLogger(__name__)

# Polymarket WebSocket event types
EVENT_PRICE_CHANGE = "price_change"
EVENT_LAST_TRADE = "last_trade_price"


class PriceSubscriber:
    """
    Subscribes to Polymarket price feeds and handles stop loss triggers.

    Replaces the polling-based stop_loss_monitor.py and position_sync.py jobs.
    """

    def __init__(
        self,
        ws_manager: WebSocketManager,
        db: Database,
        encryption: KeyEncryption,
        market_ws_url: str,
        bot_send_message: Optional[Callable] = None,
    ):
        self.ws_manager = ws_manager
        self.db = db
        self.encryption = encryption
        self.market_ws_url = market_ws_url
        self.bot_send_message = bot_send_message

        # Track token prices and subscriptions
        self._token_prices: Dict[str, float] = {}
        self._active_stop_losses: Dict[str, list] = {}  # token_id -> list of stop losses
        self._monitored_positions: Set[str] = set()  # token_ids with active positions

    async def start(self) -> None:
        """Start the price subscriber."""
        # Register with WebSocket manager
        self.ws_manager.register_connection(
            name="polymarket_market",
            url=self.market_ws_url,
            message_handler=self._handle_market_message,
        )

        # Load initial subscriptions
        await self._refresh_subscriptions()
        logger.info("Price subscriber started")

    async def _handle_market_message(
        self,
        connection_name: str,
        data: Dict[str, Any],
    ) -> None:
        """Handle incoming market WebSocket messages."""
        event_type = data.get("event_type") or data.get("type")

        if event_type in (EVENT_PRICE_CHANGE, EVENT_LAST_TRADE):
            await self._handle_price_update(data)

    async def _handle_price_update(self, data: Dict[str, Any]) -> None:
        """Process price update and check stop losses."""
        token_id = data.get("asset_id") or data.get("token_id")
        price = data.get("price")

        if not token_id or price is None:
            return

        try:
            price = float(price)
        except (TypeError, ValueError):
            return

        # Update cached price
        old_price = self._token_prices.get(token_id)
        self._token_prices[token_id] = price

        # Update positions with new price
        await self._update_position_prices(token_id, price)

        # Check stop losses if price dropped
        if old_price is None or price <= old_price:
            await self._check_stop_losses(token_id, price)

    async def _update_position_prices(self, token_id: str, price: float) -> None:
        """Update position current prices in database."""
        if token_id not in self._monitored_positions:
            return

        try:
            position_repo = PositionRepository(self.db)
            # Get all positions for this token and update them
            conn = await self.db.get_connection()
            cursor = await conn.execute(
                "SELECT id FROM positions WHERE token_id = ? AND size > 0",
                (token_id,),
            )
            rows = await cursor.fetchall()

            for row in rows:
                await position_repo.update_current_price(row["id"], price)

        except Exception as e:
            logger.error(f"Failed to update position prices for {token_id}: {e}")

    async def _check_stop_losses(self, token_id: str, current_price: float) -> None:
        """Check if any stop losses should be triggered."""
        if token_id not in self._active_stop_losses:
            return

        stop_losses = self._active_stop_losses.get(token_id, [])

        for sl in stop_losses:
            if current_price <= sl["trigger_price"]:
                await self._trigger_stop_loss(sl, current_price)

    async def _trigger_stop_loss(
        self,
        sl: Dict[str, Any],
        current_price: float,
    ) -> None:
        """Execute a triggered stop loss."""
        logger.info(
            f"Stop loss {sl['id']} triggered: price {current_price} <= {sl['trigger_price']}"
        )

        try:
            stop_loss_repo = StopLossRepository(self.db)
            position_repo = PositionRepository(self.db)
            user_repo = UserRepository(self.db)
            trading_service = TradingService(self.db, self.encryption)

            # Get position
            position = await position_repo.get_by_id(sl["position_id"])
            if not position or position.size <= 0:
                await stop_loss_repo.deactivate(sl["id"])
                return

            # Calculate sell size
            sell_size = position.size * (sl["sell_percentage"] / 100)

            # Execute market sell order
            result = await trading_service.place_order(
                user_id=sl["user_id"],
                market_condition_id=position.market_condition_id,
                token_id=sl["token_id"],
                outcome=position.outcome,
                order_type="MARKET",
                amount=sell_size,
                market_question=position.market_question,
            )

            if result.get("success"):
                # Mark stop loss as triggered
                await stop_loss_repo.mark_triggered(
                    sl["id"],
                    resulting_order_id=result.get("db_order_id", 0),
                )

                # Update position
                await position_repo.reduce_position(
                    position.id,
                    sell_size,
                    current_price,
                )

                # Remove from active tracking
                if sl["token_id"] in self._active_stop_losses:
                    self._active_stop_losses[sl["token_id"]] = [
                        s for s in self._active_stop_losses[sl["token_id"]]
                        if s["id"] != sl["id"]
                    ]

                # Notify user
                await self._notify_user_stop_loss(
                    sl, position, current_price, sell_size, result
                )

            else:
                logger.error(f"Stop loss sell failed for {sl['id']}: {result.get('error')}")

        except Exception as e:
            logger.error(f"Failed to trigger stop loss {sl['id']}: {e}")

    async def _notify_user_stop_loss(
        self,
        sl: Dict[str, Any],
        position,
        current_price: float,
        sell_size: float,
        result: Dict[str, Any],
    ) -> None:
        """Send notification to user about triggered stop loss."""
        if not self.bot_send_message:
            return

        try:
            user_repo = UserRepository(self.db)
            user = await user_repo.get_by_id(sl["user_id"])

            if user:
                await self.bot_send_message(
                    chat_id=user.telegram_id,
                    text=(
                        f"*Stop Loss Triggered!*\n\n"
                        f"Market: {position.market_question[:40]}...\n"
                        f"Trigger Price: {sl['trigger_price'] * 100:.0f}c\n"
                        f"Current Price: {current_price * 100:.0f}c\n"
                        f"Sold: {sell_size:.2f} shares\n\n"
                        f"Order ID: `{result.get('order_id', 'N/A')}`"
                    ),
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"Failed to notify user {sl['user_id']}: {e}")

    async def _refresh_subscriptions(self) -> None:
        """Refresh subscriptions based on current stop losses and positions."""
        try:
            stop_loss_repo = StopLossRepository(self.db)
            position_repo = PositionRepository(self.db)

            # Get all active stop losses
            active_stop_losses = await stop_loss_repo.get_all_active()

            # Build token -> stop losses mapping
            self._active_stop_losses.clear()
            token_ids = set()

            for sl in active_stop_losses:
                token_id = sl.token_id
                token_ids.add(token_id)

                if token_id not in self._active_stop_losses:
                    self._active_stop_losses[token_id] = []

                self._active_stop_losses[token_id].append({
                    "id": sl.id,
                    "user_id": sl.user_id,
                    "position_id": sl.position_id,
                    "token_id": sl.token_id,
                    "trigger_price": sl.trigger_price,
                    "sell_percentage": sl.sell_percentage,
                })

            # Get all positions with size > 0 for price updates
            conn = await self.db.get_connection()
            cursor = await conn.execute(
                "SELECT DISTINCT token_id FROM positions WHERE size > 0"
            )
            rows = await cursor.fetchall()

            for row in rows:
                token_ids.add(row["token_id"])
                self._monitored_positions.add(row["token_id"])

            # Subscribe to all required tokens
            if token_ids and self.ws_manager.is_connected("polymarket_market"):
                await self.ws_manager.subscribe(
                    "polymarket_market",
                    list(token_ids),
                )

            logger.info(
                f"Subscribed to {len(token_ids)} tokens "
                f"({len(self._active_stop_losses)} with stop losses)"
            )

        except Exception as e:
            logger.error(f"Failed to refresh subscriptions: {e}")

    async def add_stop_loss(self, stop_loss) -> None:
        """Add a new stop loss to monitoring."""
        token_id = stop_loss.token_id

        if token_id not in self._active_stop_losses:
            self._active_stop_losses[token_id] = []

        self._active_stop_losses[token_id].append({
            "id": stop_loss.id,
            "user_id": stop_loss.user_id,
            "position_id": stop_loss.position_id,
            "token_id": stop_loss.token_id,
            "trigger_price": stop_loss.trigger_price,
            "sell_percentage": stop_loss.sell_percentage,
        })

        # Subscribe to this token if not already
        if self.ws_manager.is_connected("polymarket_market"):
            await self.ws_manager.subscribe("polymarket_market", [token_id])

    async def remove_stop_loss(self, stop_loss_id: int) -> None:
        """Remove a stop loss from monitoring."""
        for token_id, stop_losses in self._active_stop_losses.items():
            self._active_stop_losses[token_id] = [
                sl for sl in stop_losses if sl["id"] != stop_loss_id
            ]

    async def add_position(self, position) -> None:
        """Add a position for price monitoring."""
        token_id = position.token_id
        self._monitored_positions.add(token_id)

        if self.ws_manager.is_connected("polymarket_market"):
            await self.ws_manager.subscribe("polymarket_market", [token_id])

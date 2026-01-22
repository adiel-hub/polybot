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
from database.repositories.price_alert_repo import PriceAlertRepository
from database.models import AlertDirection
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
        bot_username: str = None,
    ):
        self.ws_manager = ws_manager
        self.db = db
        self.encryption = encryption
        self.market_ws_url = market_ws_url
        self.bot_send_message = bot_send_message
        self.bot_username = bot_username

        # Track token prices and subscriptions
        self._token_prices: Dict[str, float] = {}
        self._active_stop_losses: Dict[str, list] = {}  # token_id -> list of stop losses
        self._active_alerts: Dict[str, list] = {}  # token_id -> list of price alerts
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

        # Check price alerts (both directions)
        await self._check_alerts(token_id, price, old_price)

    async def _update_position_prices(self, token_id: str, price: float) -> None:
        """Update position current prices in database."""
        if token_id not in self._monitored_positions:
            return

        try:
            position_repo = PositionRepository(self.db)
            # Get all positions for this token and update them
            conn = await self.db.get_connection()
            rows = await conn.fetch(
                "SELECT id FROM positions WHERE token_id = $1 AND size > 0",
                token_id,
            )

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
                        f"🛡️ *Stop Loss Triggered!*\n\n"
                        f"📊 Market: {position.market_question[:40]}...\n"
                        f"🎯 Trigger Price: `{sl['trigger_price'] * 100:.0f}c`\n"
                        f"💰 Current Price: `{current_price * 100:.0f}c`\n"
                        f"📉 Sold: `{sell_size:.2f}` shares\n\n"
                        f"🔗 Order ID: `{result.get('order_id', 'N/A')}`"
                    ),
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"Failed to notify user {sl['user_id']}: {e}")

    async def _refresh_subscriptions(self) -> None:
        """Refresh subscriptions based on current stop losses, alerts and positions."""
        try:
            stop_loss_repo = StopLossRepository(self.db)
            alert_repo = PriceAlertRepository(self.db)
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

            # Get all active price alerts
            active_alerts = await alert_repo.get_all_active()

            # Build token -> alerts mapping
            self._active_alerts.clear()

            for alert in active_alerts:
                token_id = alert.token_id
                token_ids.add(token_id)

                if token_id not in self._active_alerts:
                    self._active_alerts[token_id] = []

                self._active_alerts[token_id].append({
                    "id": alert.id,
                    "user_id": alert.user_id,
                    "token_id": alert.token_id,
                    "market_condition_id": alert.market_condition_id,
                    "market_question": alert.market_question,
                    "outcome": alert.outcome,
                    "target_price": alert.target_price,
                    "direction": alert.direction,
                    "note": alert.note,
                })

            # Get all positions with size > 0 for price updates
            conn = await self.db.get_connection()
            rows = await conn.fetch(
                "SELECT DISTINCT token_id FROM positions WHERE size > 0"
            )

            for row in rows:
                token_ids.add(row["token_id"])
                self._monitored_positions.add(row["token_id"])

            # Subscribe to all required tokens
            if token_ids and self.ws_manager.is_connected("polymarket_market"):
                await self.ws_manager.subscribe(
                    "polymarket_market",
                    list(token_ids),
                )

            alert_count = sum(len(alerts) for alerts in self._active_alerts.values())
            logger.info(
                f"Subscribed to {len(token_ids)} tokens "
                f"({len(self._active_stop_losses)} with stop losses, {alert_count} alerts)"
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

    # ===== Price Alert Methods =====

    async def _check_alerts(
        self,
        token_id: str,
        current_price: float,
        old_price: Optional[float],
    ) -> None:
        """Check if any price alerts should be triggered."""
        if token_id not in self._active_alerts:
            return

        alerts = self._active_alerts.get(token_id, [])
        alerts_to_remove = []

        for alert in alerts:
            should_trigger = False

            if alert["direction"] == AlertDirection.ABOVE:
                # Trigger when price crosses above target
                if current_price >= alert["target_price"]:
                    if old_price is None or old_price < alert["target_price"]:
                        should_trigger = True
            else:  # BELOW
                # Trigger when price crosses below target
                if current_price <= alert["target_price"]:
                    if old_price is None or old_price > alert["target_price"]:
                        should_trigger = True

            if should_trigger:
                await self._trigger_alert(alert, current_price)
                alerts_to_remove.append(alert["id"])

        # Remove triggered alerts from tracking
        if alerts_to_remove:
            self._active_alerts[token_id] = [
                a for a in self._active_alerts[token_id]
                if a["id"] not in alerts_to_remove
            ]

    async def _trigger_alert(
        self,
        alert: Dict[str, Any],
        current_price: float,
    ) -> None:
        """Handle a triggered price alert."""
        logger.info(
            f"Price alert {alert['id']} triggered: "
            f"price {current_price} crossed {alert['target_price']} ({alert['direction'].value})"
        )

        try:
            # Mark alert as triggered in database
            alert_repo = PriceAlertRepository(self.db)
            await alert_repo.mark_triggered(alert["id"])

            # Notify user
            await self._notify_user_alert(alert, current_price)

        except Exception as e:
            logger.error(f"Failed to trigger alert {alert['id']}: {e}")

    async def _notify_user_alert(
        self,
        alert: Dict[str, Any],
        current_price: float,
    ) -> None:
        """Send notification to user about triggered price alert."""
        if not self.bot_send_message:
            return

        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            user_repo = UserRepository(self.db)
            user = await user_repo.get_by_id(alert["user_id"])

            if user:
                direction_emoji = "📈" if alert["direction"] == AlertDirection.ABOVE else "📉"
                direction_text = "rose above" if alert["direction"] == AlertDirection.ABOVE else "dropped below"

                market_question = alert.get("market_question", "Unknown Market")
                if len(market_question) > 50:
                    market_question = market_question[:50] + "..."

                message = (
                    f"🔔 *Price Alert Triggered!*\n\n"
                    f"📊 Market: _{market_question}_\n"
                    f"🎯 Outcome: *{alert['outcome']}*\n\n"
                    f"{direction_emoji} Price {direction_text} `{alert['target_price'] * 100:.1f}c`\n"
                    f"💰 Current Price: `{current_price * 100:.1f}c`\n"
                )

                if alert.get("note"):
                    message += f"\n📝 Note: _{alert['note']}_"

                # Build deep link to trade view
                reply_markup = None
                if self.bot_username and alert.get("market_condition_id"):
                    market_id = alert["market_condition_id"]
                    # Use short ID (first 8 chars) for deep link
                    short_id = market_id[:8] if len(market_id) > 8 else market_id
                    trade_link = f"https://t.me/{self.bot_username}?start=m_{short_id}"

                    keyboard = [
                        [InlineKeyboardButton("📈 Trade Now", url=trade_link)],
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                await self.bot_send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode="Markdown",
                    reply_markup=reply_markup,
                )

                logger.info(f"Alert notification sent to user {user.telegram_id}")

        except Exception as e:
            logger.error(f"Failed to notify user {alert['user_id']} about alert: {e}")

    async def add_alert(self, alert) -> None:
        """Add a new price alert to monitoring."""
        token_id = alert.token_id

        if token_id not in self._active_alerts:
            self._active_alerts[token_id] = []

        self._active_alerts[token_id].append({
            "id": alert.id,
            "user_id": alert.user_id,
            "token_id": alert.token_id,
            "market_condition_id": alert.market_condition_id,
            "market_question": alert.market_question,
            "outcome": alert.outcome,
            "target_price": alert.target_price,
            "direction": alert.direction,
            "note": alert.note,
        })

        # Subscribe to this token if not already
        if self.ws_manager.is_connected("polymarket_market"):
            await self.ws_manager.subscribe("polymarket_market", [token_id])

        logger.info(f"Added alert {alert.id} for token {token_id}")

    async def remove_alert(self, alert_id: int) -> None:
        """Remove a price alert from monitoring."""
        for token_id, alerts in self._active_alerts.items():
            self._active_alerts[token_id] = [
                a for a in alerts if a["id"] != alert_id
            ]

        logger.info(f"Removed alert {alert_id} from monitoring")

    def get_current_price(self, token_id: str) -> Optional[float]:
        """Get the current cached price for a token."""
        return self._token_prices.get(token_id)

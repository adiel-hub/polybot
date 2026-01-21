"""WebSocket service setup and lifecycle management."""

import logging
from telegram.ext import Application

from config import settings
from database.connection import Database
from core.wallet import KeyEncryption
from core.websocket.manager import WebSocketManager
from core.websocket.price_subscriber import PriceSubscriber
from core.websocket.copy_trade_subscriber import CopyTradeSubscriber
from core.websocket.order_fill_subscriber import OrderFillSubscriber
from core.websocket.resolution_subscriber import ResolutionSubscriber
from services.claim_service import ClaimService

logger = logging.getLogger(__name__)


class WebSocketService:
    """
    Central WebSocket service that manages all real-time subscriptions.

    Note: Deposit detection is now handled by Alchemy webhooks (see run_all.py),
    not WebSocket subscriptions. This dramatically reduces Alchemy compute costs.
    """

    def __init__(
        self,
        db: Database,
        encryption: KeyEncryption,
        bot_send_message,
        bot_username: str = None,
    ):
        self.db = db
        self.encryption = encryption
        self.bot_send_message = bot_send_message
        self.bot_username = bot_username

        # Core components
        self.ws_manager = WebSocketManager()
        self.price_subscriber: PriceSubscriber = None
        self.copy_trade_subscriber: CopyTradeSubscriber = None
        self.order_fill_subscriber: OrderFillSubscriber = None
        self.resolution_subscriber: ResolutionSubscriber = None
        self.claim_service: ClaimService = None

    async def start(self) -> None:
        """Initialize and start all WebSocket subscriptions."""
        logger.info("Starting WebSocket service...")

        # Initialize price subscriber (stop loss + position sync)
        self.price_subscriber = PriceSubscriber(
            ws_manager=self.ws_manager,
            db=self.db,
            encryption=self.encryption,
            market_ws_url=settings.polymarket_ws_market_url,
            bot_send_message=self.bot_send_message,
            bot_username=self.bot_username,
        )
        await self.price_subscriber.start()

        # Note: Deposit detection is now handled by Alchemy webhooks
        # See run_all.py -> run_webhook_server() for the new implementation
        # This saves millions of Alchemy compute units per day

        # Initialize copy trade subscriber
        self.copy_trade_subscriber = CopyTradeSubscriber(
            ws_manager=self.ws_manager,
            db=self.db,
            encryption=self.encryption,
            user_ws_url=settings.polymarket_ws_user_url,
            bot_send_message=self.bot_send_message,
        )
        await self.copy_trade_subscriber.start()

        # Initialize order fill subscriber (for limit order commission collection)
        self.order_fill_subscriber = OrderFillSubscriber(
            ws_manager=self.ws_manager,
            db=self.db,
            encryption=self.encryption,
            user_ws_url=settings.polymarket_ws_user_url,
            bot_send_message=self.bot_send_message,
        )
        await self.order_fill_subscriber.start()

        # Initialize claim service for auto-claim
        self.claim_service = ClaimService(
            db=self.db,
            bot_send_message=self.bot_send_message,
        )

        # Initialize resolution subscriber (market resolution detection)
        self.resolution_subscriber = ResolutionSubscriber(
            db=self.db,
            poll_interval=getattr(settings, "resolution_check_interval", 300),
            on_resolution_callback=self._handle_market_resolution,
        )
        await self.resolution_subscriber.start()

        # Start the WebSocket manager (connects all registered connections)
        await self.ws_manager.start()

        logger.info("WebSocket service started successfully")

    async def _handle_market_resolution(
        self,
        condition_id: str,
        winning_outcome: str,
    ) -> None:
        """
        Handle market resolution by triggering auto-claims.

        Called by ResolutionSubscriber when a market resolves.

        Args:
            condition_id: Resolved market condition ID
            winning_outcome: "YES" or "NO"
        """
        if not self.claim_service:
            logger.warning("Claim service not initialized, skipping auto-claim")
            return

        try:
            logger.info(
                f"Processing auto-claims for market {condition_id[:16]}... "
                f"(winner: {winning_outcome})"
            )
            results = await self.claim_service.handle_market_resolution(
                condition_id=condition_id,
                winning_outcome=winning_outcome,
            )

            successful = sum(1 for r in results if r.success)
            logger.info(
                f"Auto-claim complete: {successful}/{len(results)} positions claimed "
                f"for market {condition_id[:16]}..."
            )

            # Also retry any pending claims from previous failures
            await self._retry_pending_claims()

        except Exception as e:
            logger.error(f"Auto-claim failed for market {condition_id[:16]}...: {e}")

    async def _retry_pending_claims(self) -> None:
        """Retry pending claims that previously failed."""
        if not self.claim_service:
            return

        try:
            results = await self.claim_service.retry_pending_claims()
            if results:
                successful = sum(1 for r in results if r.success)
                logger.info(f"Retry claims complete: {successful}/{len(results)} succeeded")
        except Exception as e:
            logger.error(f"Retry pending claims failed: {e}")

    async def stop(self) -> None:
        """Stop all WebSocket connections."""
        logger.info("Stopping WebSocket service...")

        if self.resolution_subscriber:
            await self.resolution_subscriber.stop()

        if self.claim_service:
            await self.claim_service.close()

        await self.ws_manager.stop()

        logger.info("WebSocket service stopped")

    # Convenience methods to interact with subscribers

    async def add_stop_loss(self, stop_loss) -> None:
        """Add a stop loss to real-time monitoring."""
        if self.price_subscriber:
            await self.price_subscriber.add_stop_loss(stop_loss)

    async def remove_stop_loss(self, stop_loss_id: int) -> None:
        """Remove a stop loss from monitoring."""
        if self.price_subscriber:
            await self.price_subscriber.remove_stop_loss(stop_loss_id)

    async def add_position(self, position) -> None:
        """Add a position for price monitoring."""
        if self.price_subscriber:
            await self.price_subscriber.add_position(position)

    async def add_copy_subscription(self, subscription) -> None:
        """Add a copy trading subscription."""
        if self.copy_trade_subscriber:
            await self.copy_trade_subscriber.add_subscription(subscription)

    async def remove_copy_subscription(self, subscription_id: int) -> None:
        """Remove a copy trading subscription."""
        if self.copy_trade_subscriber:
            await self.copy_trade_subscriber.remove_subscription(subscription_id)

    async def add_alert(self, alert) -> None:
        """Add a price alert to real-time monitoring."""
        if self.price_subscriber:
            await self.price_subscriber.add_alert(alert)

    async def remove_alert(self, alert_id: int) -> None:
        """Remove a price alert from monitoring."""
        if self.price_subscriber:
            await self.price_subscriber.remove_alert(alert_id)

    def get_current_price(self, token_id: str) -> float:
        """Get current cached price for a token."""
        if self.price_subscriber:
            return self.price_subscriber.get_current_price(token_id)
        return None

    async def add_order_to_monitor(self, order_id: int, polymarket_order_id: str) -> None:
        """Add a limit order for fill monitoring (commission collection)."""
        if self.order_fill_subscriber:
            await self.order_fill_subscriber.add_order_to_monitor(order_id, polymarket_order_id)

    async def remove_order_from_monitor(self, polymarket_order_id: str) -> None:
        """Remove a limit order from fill monitoring."""
        if self.order_fill_subscriber:
            await self.order_fill_subscriber.remove_order_from_monitor(polymarket_order_id)


async def setup_websocket_service(application: Application) -> WebSocketService:
    """
    Create and configure the WebSocket service.

    This replaces setup_jobs() and provides real-time updates instead of polling.
    """
    db = application.bot_data["db"]
    encryption = application.bot_data["encryption"]

    # Get bot username for deep links
    bot_username = (await application.bot.get_me()).username

    # Create bot send_message wrapper
    async def send_message(chat_id: int, text: str, parse_mode: str = None, reply_markup=None):
        await application.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    # Create and start WebSocket service
    ws_service = WebSocketService(
        db=db,
        encryption=encryption,
        bot_send_message=send_message,
        bot_username=bot_username,
    )

    await ws_service.start()

    # Store in bot_data for access in handlers
    application.bot_data["ws_service"] = ws_service

    logger.info("WebSocket service configured and started")

    return ws_service

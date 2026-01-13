"""WebSocket service setup and lifecycle management."""

import logging
from telegram.ext import Application

from config import settings
from database.connection import Database
from core.wallet import KeyEncryption
from core.websocket.manager import WebSocketManager
from core.websocket.price_subscriber import PriceSubscriber
from core.websocket.deposit_subscriber import DepositSubscriber
from core.websocket.copy_trade_subscriber import CopyTradeSubscriber

logger = logging.getLogger(__name__)


class WebSocketService:
    """
    Central WebSocket service that manages all real-time subscriptions.

    Replaces the polling-based jobs with WebSocket-based real-time updates.
    """

    def __init__(
        self,
        db: Database,
        encryption: KeyEncryption,
        bot_send_message,
    ):
        self.db = db
        self.encryption = encryption
        self.bot_send_message = bot_send_message

        # Core components
        self.ws_manager = WebSocketManager()
        self.price_subscriber: PriceSubscriber = None
        self.deposit_subscriber: DepositSubscriber = None
        self.copy_trade_subscriber: CopyTradeSubscriber = None

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
        )
        await self.price_subscriber.start()

        # Initialize deposit subscriber (Alchemy WebSocket)
        if settings.alchemy_ws_url:
            self.deposit_subscriber = DepositSubscriber(
                db=self.db,
                alchemy_ws_url=settings.alchemy_ws_url,
                bot_send_message=self.bot_send_message,
            )
            await self.deposit_subscriber.start()
        else:
            logger.warning(
                "ALCHEMY_API_KEY not configured - deposit detection disabled. "
                "Set ALCHEMY_API_KEY in .env for real-time deposit notifications."
            )

        # Initialize copy trade subscriber
        self.copy_trade_subscriber = CopyTradeSubscriber(
            ws_manager=self.ws_manager,
            db=self.db,
            encryption=self.encryption,
            user_ws_url=settings.polymarket_ws_user_url,
            bot_send_message=self.bot_send_message,
        )
        await self.copy_trade_subscriber.start()

        # Start the WebSocket manager (connects all registered connections)
        await self.ws_manager.start()

        logger.info("WebSocket service started successfully")

    async def stop(self) -> None:
        """Stop all WebSocket connections."""
        logger.info("Stopping WebSocket service...")

        if self.deposit_subscriber:
            await self.deposit_subscriber.stop()

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

    async def add_wallet(self, address: str) -> None:
        """Add a wallet for deposit monitoring."""
        if self.deposit_subscriber:
            await self.deposit_subscriber.add_wallet(address)

    async def add_copy_subscription(self, subscription) -> None:
        """Add a copy trading subscription."""
        if self.copy_trade_subscriber:
            await self.copy_trade_subscriber.add_subscription(subscription)

    async def remove_copy_subscription(self, subscription_id: int) -> None:
        """Remove a copy trading subscription."""
        if self.copy_trade_subscriber:
            await self.copy_trade_subscriber.remove_subscription(subscription_id)


async def setup_websocket_service(application: Application) -> WebSocketService:
    """
    Create and configure the WebSocket service.

    This replaces setup_jobs() and provides real-time updates instead of polling.
    """
    db = application.bot_data["db"]
    encryption = application.bot_data["encryption"]

    # Create bot send_message wrapper
    async def send_message(chat_id: int, text: str, parse_mode: str = None):
        await application.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
        )

    # Create and start WebSocket service
    ws_service = WebSocketService(
        db=db,
        encryption=encryption,
        bot_send_message=send_message,
    )

    await ws_service.start()

    # Store in bot_data for access in handlers
    application.bot_data["ws_service"] = ws_service

    logger.info("WebSocket service configured and started")

    return ws_service

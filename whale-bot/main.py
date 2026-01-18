"""Polymarket Whale Alert Bot - Main Entry Point."""

import asyncio
import logging
import sys

from telegram.ext import Application

from config import LOG_LEVEL, WHALE_THRESHOLD, POLL_INTERVAL, POLYBOT_USERNAME, TELEGRAM_BOT_TOKEN
from monitors.whale_monitor import WhaleMonitor, WhaleTrade
from services.alert_service import AlertService

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class WhaleAlertBot:
    """Main bot class coordinating monitor and alerts."""

    def __init__(self):
        self.alert_service = AlertService()
        self.monitor = WhaleMonitor(on_whale_detected=self._on_whale_detected)
        self.application: Application = None

    async def _on_whale_detected(self, trade: WhaleTrade) -> None:
        """Handle detected whale trade."""
        logger.info(
            f"Whale detected: ${trade.value:,.2f} on {trade.market_title[:50]}"
        )
        await self.alert_service.send_whale_alert(trade)

    async def _run_monitor(self) -> None:
        """Run the whale monitor as background task."""
        try:
            await self.monitor.start()
        except Exception as e:
            logger.error(f"Monitor error: {e}")

    async def post_init(self, application: Application) -> None:
        """Called after application is initialized."""
        logger.info("=" * 50)
        logger.info("Polymarket Whale Alert Bot Starting")
        logger.info(f"Threshold: ${WHALE_THRESHOLD:,.0f}")
        logger.info(f"Poll Interval: {POLL_INTERVAL}s")
        logger.info(f"Subscribed chats: {self.alert_service.chat_count}")
        if POLYBOT_USERNAME:
            logger.info(f"PolyBot Deep Links: @{POLYBOT_USERNAME}")
        logger.info("=" * 50)

        # Send startup message to existing chats
        await self.alert_service.send_startup_message()

        # Start whale monitor in background
        asyncio.create_task(self._run_monitor())

    async def post_shutdown(self, application: Application) -> None:
        """Called when application is shutting down."""
        logger.info("Shutting down...")
        await self.monitor.stop()
        await self.alert_service.send_shutdown_message()
        logger.info("Shutdown complete")

    def run(self) -> None:
        """Run the bot."""
        # Build application
        self.application = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )

        # Setup command handlers
        self.alert_service.setup_handlers(self.application)

        # Run the bot
        logger.info("Starting Telegram bot...")
        self.application.run_polling(drop_pending_updates=True)


def main():
    """Main entry point."""
    bot = WhaleAlertBot()
    bot.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

#!/usr/bin/env python3
"""Entry point for the PolyBot Telegram bot."""

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables before importing settings
load_dotenv()

from config import settings
from database.connection import Database
from bot.application import create_application
from core.websocket.setup import setup_websocket_service


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    """Initialize and run the bot."""
    logger.info("Starting PolyBot...")

    # Ensure data directory exists
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)

    # Initialize database
    db = Database(settings.database_path)
    await db.initialize()
    logger.info("Database initialized")

    # Create and run bot application
    app = await create_application(db)

    # Setup WebSocket service for real-time updates
    ws_service = await setup_websocket_service(app)
    logger.info("WebSocket service started")

    logger.info("Bot is running. Press Ctrl+C to stop.")

    # Run the bot
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)

        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            # Stop WebSocket service
            await ws_service.stop()
            await app.updater.stop()
            await app.stop()
            await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise

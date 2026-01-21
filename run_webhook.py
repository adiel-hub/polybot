#!/usr/bin/env python3
"""
Webhook server for Alchemy deposit notifications.

Run this alongside the main bot to receive deposit webhooks from Alchemy.
This is more cost-effective than the WebSocket approach as Alchemy only
sends events for registered addresses.

Usage:
    python run_webhook.py

Requirements:
    1. Create an Address Activity webhook at https://dashboard.alchemy.com/webhooks
    2. Set the webhook URL to your server (e.g., https://yourdomain.com/webhook/alchemy)
    3. Copy the signing key to ALCHEMY_WEBHOOK_SIGNING_KEY in .env
    4. Copy the webhook ID to ALCHEMY_WEBHOOK_ID in .env
    5. Copy your auth token to ALCHEMY_AUTH_TOKEN in .env

Note: For local development, use ngrok to expose the webhook:
    ngrok http 8080
"""

import asyncio
import logging
import os
from pathlib import Path

from aiohttp import web
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from config import settings

# Render uses PORT env var
PORT = int(os.environ.get("PORT", settings.webhook_port))
from database.connection import Database
from core.webhook import AlchemyWebhookHandler, AlchemyWebhookManager, create_webhook_app

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    """Run the webhook server."""
    logger.info("Starting Alchemy Webhook Server...")

    # Check required settings
    if not settings.alchemy_webhook_signing_key:
        logger.warning(
            "ALCHEMY_WEBHOOK_SIGNING_KEY not set. "
            "Webhook signature verification will be skipped."
        )

    # Initialize database
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    db = Database(settings.database_path)
    await db.initialize()
    logger.info("Database initialized")

    # Create webhook handler
    handler = AlchemyWebhookHandler(
        db=db,
        signing_key=settings.alchemy_webhook_signing_key,
        # Note: bot_send_message will be None - we'll use a different approach
        # to notify users since this runs separately from the bot
    )

    # Load existing wallet addresses
    await handler.load_wallet_addresses()

    # Optionally sync addresses with Alchemy webhook
    if settings.alchemy_auth_token and settings.alchemy_webhook_id:
        manager = AlchemyWebhookManager(
            auth_token=settings.alchemy_auth_token,
            webhook_id=settings.alchemy_webhook_id,
        )
        # Sync all addresses to webhook
        from database.repositories import WalletRepository
        wallet_repo = WalletRepository(db)
        addresses = await wallet_repo.get_all_addresses()
        if addresses:
            await manager.sync_addresses(addresses)
            logger.info(f"Synced {len(addresses)} addresses with Alchemy webhook")
        await manager.close()

    # Create and run web app
    app = create_webhook_app(handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logger.info(f"Webhook server running on port {PORT}")
    logger.info(f"Webhook endpoint: http://0.0.0.0:{PORT}/webhook/alchemy")
    logger.info("Waiting for webhooks...")

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Webhook server stopped by user")
    except Exception as e:
        logger.error(f"Webhook server crashed: {e}")
        raise

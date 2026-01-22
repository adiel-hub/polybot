#!/usr/bin/env python3
"""
Run all Poly bots in a single process with unified logging.

Runs:
- PolyBot (main trading bot)
- Polynews Bot (market news articles)
- Whale Alert Bot (large trade alerts)

Usage: python run_all.py
"""

import asyncio
import logging
import sys
import signal
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables before importing settings
load_dotenv()

# Configure unified logging with colors and prefixes
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors and bot prefixes."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    BOT_COLORS = {
        'polybot': '\033[94m',      # Blue
        'polynews': '\033[95m',     # Magenta
        'whalebot': '\033[96m',     # Cyan
    }

    def format(self, record):
        # Add color based on log level
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Color the bot name if present
        name = record.name.lower()
        for bot_name, color in self.BOT_COLORS.items():
            if bot_name in name:
                record.name = f"{color}{record.name}{self.RESET}"
                break

        return super().format(record)


def setup_logging():
    """Setup unified logging for all bots."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter(
        fmt="%(asctime)s │ %(name)-30s │ %(levelname)-8s │ %(message)s",
        datefmt="%H:%M:%S"
    ))

    # Configure root logger
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Reduce noise from httpx/httpcore
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


# ============== PolyBot (Main Trading Bot) ==============

async def run_polybot():
    """Run the main PolyBot trading bot."""
    logger = logging.getLogger("polybot.main")

    try:
        from config import settings
        from database.connection import Database
        from bot.application import create_application
        from core.websocket.setup import setup_websocket_service

        logger.info("Starting PolyBot...")

        # Initialize database
        db = Database(settings.database_url)
        await db.initialize()
        logger.info("Database initialized")

        # Create and run bot application
        app = await create_application(db)

        # Setup WebSocket service for real-time updates
        ws_service = await setup_websocket_service(app)
        logger.info("WebSocket service started")

        logger.info("PolyBot is running!")

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
                await ws_service.stop()
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
                logger.info("PolyBot stopped")

    except Exception as e:
        logger.error(f"PolyBot error: {e}", exc_info=True)
        raise


# ============== Polynews Bot ==============

async def run_polynews():
    """Run the Polynews article bot."""
    logger = logging.getLogger("polynews.main")

    try:
        from config import settings
        from news_bot.settings import news_settings
        from database.connection import Database
        from core.polymarket.gamma_client import GammaMarketClient
        from news_bot.database.repositories.posted_market_repo import PostedMarketRepository
        from news_bot.services.market_monitor import MarketMonitorService
        from news_bot.services.web_researcher import WebResearcherService
        from news_bot.services.article_generator import ArticleGeneratorService
        from news_bot.services.telegram_publisher import TelegramPublisherService
        from news_bot.scheduler.job_manager import JobManager

        logger.info("Starting Polynews Bot...")

        # Validate settings
        if not news_settings.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY not set - Polynews Bot disabled")
            return

        if not (news_settings.news_bot_token or settings.telegram_bot_token):
            logger.warning("No bot token for Polynews - disabled")
            return

        # Wait for main bot to initialize the database first
        await asyncio.sleep(2)

        # Initialize database
        db = Database(settings.database_url)
        await db.initialize()

        # Initialize services
        posted_repo = PostedMarketRepository(db)
        gamma_client = GammaMarketClient()

        market_monitor = MarketMonitorService(
            gamma_client=gamma_client,
            posted_repo=posted_repo,
            min_volume=news_settings.min_market_volume,
            min_liquidity=news_settings.min_market_liquidity,
        )

        web_researcher = WebResearcherService(
            tavily_api_key=news_settings.tavily_api_key,
        )

        article_generator = ArticleGeneratorService(
            api_key=news_settings.anthropic_api_key,
            model=news_settings.claude_model,
            max_tokens=news_settings.article_max_tokens,
        )

        bot_token = news_settings.news_bot_token or settings.telegram_bot_token
        telegram_publisher = TelegramPublisherService(
            bot_token=bot_token,
            channel_ids=news_settings.news_channel_ids,
            trading_bot_username=news_settings.trading_bot_username,
        )

        job_manager = JobManager()

        async def poll_and_publish():
            """Poll for new markets and publish articles."""
            try:
                logger.info("Polling for new markets...")
                # Use trending markets (which have volume) instead of newest
                # This avoids empty crypto minute-markets
                markets = await market_monitor.get_trending_unposted(
                    limit=news_settings.max_markets_per_poll * 2
                )

                if not markets:
                    logger.info("No new markets to post")
                    return

                logger.info(f"Found {len(markets)} new markets")

                processed = 0
                for market in markets:
                    if processed >= news_settings.max_markets_per_poll:
                        break

                    try:
                        research = await web_researcher.research_topic(market)
                        article = article_generator.generate_article(market=market, research=research)
                        results = await telegram_publisher.publish_article(article=article, market=market)

                        successful_ids = [mid for mid in results.values() if mid is not None]
                        if successful_ids:
                            await posted_repo.create(
                                condition_id=market.condition_id,
                                event_id=market.event_id,
                                question=market.question,
                                category=market.category,
                                article_title=article.title,
                                telegram_message_id=successful_ids[0],
                                article_tokens_used=article.tokens_used,
                                research_sources=[s.url for s in research.sources],
                            )
                            processed += 1
                            await asyncio.sleep(3)
                    except Exception as e:
                        logger.error(f"Error processing market: {e}")

                logger.info(f"Posted {processed} articles")

            except Exception as e:
                logger.error(f"Poll error: {e}")

        job_manager.set_poll_callback(poll_and_publish)
        job_manager.start(interval_minutes=news_settings.poll_interval_minutes)

        logger.info(f"Polynews Bot running! Poll interval: {news_settings.poll_interval_minutes}min")

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            job_manager.stop()
            await gamma_client.close()
            await web_researcher.close()
            await db.close()
            logger.info("Polynews Bot stopped")

    except Exception as e:
        logger.error(f"Polynews error: {e}", exc_info=True)


# ============== Whale Alert Bot ==============

def _load_whale_bot_modules():
    """
    Load whale-bot modules using importlib to avoid path conflicts.

    The whale-bot has modules named 'config', 'monitors', 'services', 'utils'
    which conflict with polybot's packages. We use importlib to load them
    directly from files and patch sys.modules so internal imports work.

    IMPORTANT: We temporarily patch 'config' during loading, then restore
    the original to avoid breaking PolyBot's config imports.
    """
    import importlib.util
    whale_bot_dir = Path(__file__).parent / "whale-bot"

    # Save original config module if it exists
    original_config = sys.modules.get('config')

    # Step 1: Temporarily patch 'config' with whale_bot_config
    import whale_bot_config
    sys.modules['config'] = whale_bot_config

    try:
        # Step 2: Load whale_monitor and patch it as 'monitors.whale_monitor'
        monitor_spec = importlib.util.spec_from_file_location(
            "monitors.whale_monitor",
            whale_bot_dir / "monitors" / "whale_monitor.py"
        )
        whale_monitor_module = importlib.util.module_from_spec(monitor_spec)
        sys.modules['monitors.whale_monitor'] = whale_monitor_module
        monitor_spec.loader.exec_module(whale_monitor_module)

        # Step 3: Load formatting and patch it as 'utils.formatting'
        formatting_spec = importlib.util.spec_from_file_location(
            "utils.formatting",
            whale_bot_dir / "utils" / "formatting.py"
        )
        formatting_module = importlib.util.module_from_spec(formatting_spec)
        sys.modules['utils.formatting'] = formatting_module
        formatting_spec.loader.exec_module(formatting_module)

        # Step 4: Load alert_service (now its imports will resolve correctly)
        alert_spec = importlib.util.spec_from_file_location(
            "services.alert_service",
            whale_bot_dir / "services" / "alert_service.py"
        )
        alert_module = importlib.util.module_from_spec(alert_spec)
        sys.modules['services.alert_service'] = alert_module
        alert_spec.loader.exec_module(alert_module)

        return {
            'WhaleMonitor': whale_monitor_module.WhaleMonitor,
            'WhaleTrade': whale_monitor_module.WhaleTrade,
            'AlertService': alert_module.AlertService,
        }
    finally:
        # Restore original config module so PolyBot imports work correctly
        if original_config is not None:
            sys.modules['config'] = original_config
        else:
            # Remove the whale_bot_config patch if config wasn't loaded before
            del sys.modules['config']


async def run_whalebot():
    """Run the Whale Alert bot."""
    logger = logging.getLogger("whalebot.main")

    # Stagger startup to avoid resource contention
    await asyncio.sleep(1)

    try:
        # Load whale-bot modules with proper patching
        modules = _load_whale_bot_modules()
        WhaleMonitor = modules['WhaleMonitor']
        WhaleTrade = modules['WhaleTrade']
        AlertService = modules['AlertService']

        from whale_bot_config import (
            WHALE_THRESHOLD, POLL_INTERVAL,
            POLYBOT_USERNAME, TELEGRAM_BOT_TOKEN
        )
        from telegram.ext import Application

        if not TELEGRAM_BOT_TOKEN:
            logger.warning("WHALE_BOT_TOKEN not set - Whale Bot disabled")
            return

        logger.info("Starting Whale Alert Bot...")

        alert_service = AlertService()

        async def on_whale_detected(trade: WhaleTrade):
            logger.info(f"🐋 Whale: ${trade.value:,.2f} on {trade.market_title[:50]}")
            await alert_service.send_whale_alert(trade)

        monitor = WhaleMonitor(on_whale_detected=on_whale_detected)

        application = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
        )

        alert_service.setup_handlers(application)

        async with application:
            await application.initialize()
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True)

            # Start the rate-limited queue processor
            await alert_service.start_queue_processor()

            logger.info(f"Whale Bot running! Threshold: ${WHALE_THRESHOLD:,.0f}")

            # Start monitor
            monitor_task = asyncio.create_task(monitor.start())

            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            finally:
                await monitor.stop()
                monitor_task.cancel()
                await alert_service.stop_queue_processor()
                await application.updater.stop()
                await application.stop()
                await application.shutdown()
                logger.info("Whale Bot stopped")

    except ImportError as e:
        logger.warning(f"Whale Bot dependencies not found: {e}")
    except Exception as e:
        logger.error(f"Whale Bot error: {e}", exc_info=True)


# ============== Webhook Server ==============

async def run_webhook_server():
    """Run the webhook server for deposit notifications and health checks.

    This server MUST always run when deployed to Render (or similar platforms)
    because web services require a port to be bound for health checks.
    """
    import os
    from aiohttp import web

    logger = logging.getLogger("webhook.main")

    try:
        from config import settings
        from database.connection import Database

        logger.info("Starting Webhook Server...")

        # Use PORT env var (for Render) or settings
        port = int(os.environ.get("PORT", settings.webhook_port))

        # Check if Alchemy webhook is configured
        alchemy_configured = bool(settings.alchemy_webhook_signing_key)

        if alchemy_configured:
            from core.webhook import AlchemyWebhookHandler, AlchemyWebhookManager, create_webhook_app

            # Initialize database
            db = Database(settings.database_url)
            await db.initialize()

            # Create webhook handler
            handler = AlchemyWebhookHandler(
                db=db,
                signing_key=settings.alchemy_webhook_signing_key,
            )

            # Load existing wallet addresses
            await handler.load_wallet_addresses()

            # Sync addresses with Alchemy if configured
            if settings.alchemy_auth_token and settings.alchemy_webhook_id:
                manager = AlchemyWebhookManager(
                    auth_token=settings.alchemy_auth_token,
                    webhook_id=settings.alchemy_webhook_id,
                )
                from database.repositories import WalletRepository
                wallet_repo = WalletRepository(db)
                addresses = await wallet_repo.get_all_addresses()
                if addresses:
                    await manager.sync_addresses(addresses)
                    logger.info(f"Synced {len(addresses)} addresses with Alchemy webhook")
                await manager.close()

            # Create web app with Alchemy webhook handler
            app = create_webhook_app(handler)
            logger.info("Alchemy webhook handler configured")
        else:
            # Create minimal web app with just health check endpoint
            # This ensures Render can verify the service is running
            logger.info("Alchemy webhook not configured - running minimal health server")
            logger.info("Set ALCHEMY_WEBHOOK_SIGNING_KEY to enable deposit webhooks")

            app = web.Application()

        # Add health check endpoint (if not already added by create_webhook_app)
        async def health_check(request):
            return web.json_response({
                "status": "healthy",
                "service": "polybot",
                "webhook_enabled": alchemy_configured,
            })

        # Only add health check if not already registered (to avoid duplicate route error)
        if not alchemy_configured:
            app.router.add_get("/health", health_check)

        # Always add root path health check for Render
        app.router.add_get("/", health_check)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

        logger.info(f"Webhook server running on port {port}")
        if alchemy_configured:
            logger.info(f"Endpoints: /webhook/alchemy, /health")
        else:
            logger.info(f"Endpoints: /health (webhook disabled)")

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await runner.cleanup()
            logger.info("Webhook server stopped")

    except ImportError as e:
        logger.warning(f"Webhook dependencies not available: {e}")
    except Exception as e:
        logger.error(f"Webhook server error: {e}", exc_info=True)


# ============== Main Runner ==============

async def main():
    """Run all bots concurrently."""
    setup_logging()
    logger = logging.getLogger("runner")

    logger.info("=" * 60)
    logger.info("  POLY BOTS LAUNCHER")
    logger.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    logger.info("")

    # Create tasks for all bots
    tasks = [
        asyncio.create_task(run_polybot(), name="polybot"),
        asyncio.create_task(run_polynews(), name="polynews"),
        asyncio.create_task(run_whalebot(), name="whalebot"),
        asyncio.create_task(run_webhook_server(), name="webhook"),
    ]

    # Handle shutdown gracefully
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal...")
        for task in tasks:
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Wait for all tasks
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for task, result in zip(tasks, results):
            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                logger.error(f"{task.get_name()} failed: {result}")
    except Exception as e:
        logger.error(f"Runner error: {e}")
    finally:
        logger.info("All bots stopped")


# Create config wrapper for whale-bot to avoid import conflicts
def create_whale_bot_config():
    """Create whale bot config module from environment."""
    config_path = Path(__file__).parent / "whale_bot_config.py"

    if not config_path.exists():
        config_content = '''"""Whale bot configuration loaded from environment."""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("WHALE_BOT_TOKEN", "")
WHALE_THRESHOLD = float(os.getenv("WHALE_THRESHOLD", "10000"))
POLL_INTERVAL = int(os.getenv("WHALE_POLL_INTERVAL", "30"))
POLYBOT_USERNAME = os.getenv("POLYBOT_USERNAME", "")
LOG_LEVEL = os.getenv("WHALE_LOG_LEVEL", "INFO")
'''
        config_path.write_text(config_content)


if __name__ == "__main__":
    create_whale_bot_config()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")

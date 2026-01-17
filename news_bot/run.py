#!/usr/bin/env python3
"""
Entry point for the Polymarket News Bot.

Run with: python -m news_bot.run
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class PolynewsBot:
    """
    Main application class for the Polymarket News Bot.

    Coordinates all services and manages the application lifecycle.
    """

    def __init__(self):
        """Initialize the bot with empty service references."""
        self.db: Database = None
        self.gamma_client: GammaMarketClient = None
        self.posted_repo: PostedMarketRepository = None
        self.market_monitor: MarketMonitorService = None
        self.web_researcher: WebResearcherService = None
        self.article_generator: ArticleGeneratorService = None
        self.telegram_publisher: TelegramPublisherService = None
        self.job_manager: JobManager = None

    async def initialize(self) -> None:
        """Initialize all services and components."""
        logger.info("Initializing Polynews Bot...")

        # Validate required settings
        self._validate_settings()

        # Initialize database
        db_path = Path(settings.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = Database(str(db_path))
        await self.db.initialize()
        logger.info(f"Database initialized at {db_path}")

        # Initialize repository
        self.posted_repo = PostedMarketRepository(self.db)

        # Initialize Gamma client (reuse from main bot)
        self.gamma_client = GammaMarketClient()

        # Initialize services
        self.market_monitor = MarketMonitorService(
            gamma_client=self.gamma_client,
            posted_repo=self.posted_repo,
            min_volume=news_settings.min_market_volume,
            min_liquidity=news_settings.min_market_liquidity,
        )

        self.web_researcher = WebResearcherService(
            tavily_api_key=news_settings.tavily_api_key,
        )

        self.article_generator = ArticleGeneratorService(
            api_key=news_settings.anthropic_api_key,
            model=news_settings.claude_model,
            max_tokens=news_settings.article_max_tokens,
        )

        # Use news bot token if set, otherwise fall back to main bot token
        bot_token = news_settings.news_bot_token or settings.telegram_bot_token
        self.telegram_publisher = TelegramPublisherService(
            bot_token=bot_token,
            channel_id=news_settings.news_channel_id,
            trading_bot_username=news_settings.trading_bot_username,
        )

        # Initialize scheduler
        self.job_manager = JobManager()
        self.job_manager.set_poll_callback(self.poll_and_publish)

        logger.info("All services initialized")

    def _validate_settings(self) -> None:
        """Validate required settings are configured."""
        errors = []

        if not news_settings.news_channel_id:
            errors.append("NEWS_CHANNEL_ID is required")

        if not news_settings.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is required")

        if not (news_settings.news_bot_token or settings.telegram_bot_token):
            errors.append("NEWS_BOT_TOKEN or TELEGRAM_BOT_TOKEN is required")

        if errors:
            for error in errors:
                logger.error(error)
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        # Warn about optional settings
        if not news_settings.tavily_api_key:
            logger.warning(
                "TAVILY_API_KEY not set - articles will be generated without web research"
            )

        if not news_settings.trading_bot_username:
            logger.warning(
                "TRADING_BOT_USERNAME not set - Trade button will not appear in articles"
            )

    async def poll_and_publish(self) -> None:
        """
        Main job: poll for new markets and publish articles.

        This is called by the scheduler at regular intervals.
        """
        try:
            logger.info("=" * 50)
            logger.info("Starting market poll...")

            # Get unposted markets
            markets = await self.market_monitor.get_unposted_markets(
                limit=news_settings.max_markets_per_poll * 2  # Fetch extra for filtering
            )

            if not markets:
                logger.info("No new markets to post")
                return

            logger.info(f"Found {len(markets)} new markets to process")

            # Process up to max_markets_per_poll
            processed = 0
            for market in markets:
                if processed >= news_settings.max_markets_per_poll:
                    break

                success = await self._process_market(market)
                if success:
                    processed += 1
                    # Rate limit between posts
                    await asyncio.sleep(3)

            logger.info(f"Successfully posted {processed} articles")

        except Exception as e:
            logger.error(f"Error in poll_and_publish: {e}", exc_info=True)

    async def _process_market(self, market) -> bool:
        """
        Process a single market: research, generate, publish.

        Args:
            market: Market to process

        Returns:
            True if successfully published, False otherwise
        """
        try:
            logger.info(f"Processing: {market.question[:60]}...")

            # Research the topic
            research = await self.web_researcher.research_topic(market)
            logger.info(
                f"Research complete: {len(research.sources)} sources, "
                f"summary length: {len(research.summary)}"
            )

            # Generate article
            article = self.article_generator.generate_article(
                market=market,
                research=research,
            )
            logger.info(
                f"Article generated: {len(article.body)} chars, "
                f"{article.tokens_used} tokens"
            )

            # Publish to Telegram
            message_id = await self.telegram_publisher.publish_article(
                article=article,
                market=market,
            )

            if message_id:
                # Record as posted
                await self.posted_repo.create(
                    condition_id=market.condition_id,
                    event_id=market.event_id,
                    question=market.question,
                    category=market.category,
                    article_title=article.title,
                    telegram_message_id=message_id,
                    article_tokens_used=article.tokens_used,
                    research_sources=[s.url for s in research.sources],
                )
                logger.info(f"Published and recorded: message_id={message_id}")
                return True
            else:
                logger.error("Failed to publish article to Telegram")
                return False

        except Exception as e:
            logger.error(f"Error processing market {market.condition_id}: {e}", exc_info=True)
            return False

    async def run(self) -> None:
        """Run the bot main loop."""
        await self.initialize()

        # Start the scheduler
        self.job_manager.start(
            interval_minutes=news_settings.poll_interval_minutes
        )

        logger.info("=" * 50)
        logger.info("Polynews Bot is running!")
        logger.info(f"Channel: {news_settings.news_channel_id}")
        logger.info(f"Poll interval: {news_settings.poll_interval_minutes} minutes")
        logger.info(f"Min volume: ${news_settings.min_market_volume:,.0f}")
        logger.info(f"Min liquidity: ${news_settings.min_market_liquidity:,.0f}")
        logger.info("=" * 50)

        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shutdown all services."""
        logger.info("Shutting down...")

        if self.job_manager:
            self.job_manager.stop()

        if self.gamma_client:
            await self.gamma_client.close()

        if self.web_researcher:
            await self.web_researcher.close()

        if self.db:
            await self.db.close()

        logger.info("Shutdown complete")


async def main():
    """Main entry point."""
    bot = PolynewsBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

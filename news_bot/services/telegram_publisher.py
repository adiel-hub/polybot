"""Telegram publisher service for posting articles to channel."""

import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from core.polymarket.gamma_client import Market
from news_bot.services.article_generator import GeneratedArticle

logger = logging.getLogger(__name__)


class TelegramPublisherService:
    """
    Publishes news articles to a Telegram channel.

    Handles message formatting and posting via Telegram Bot API.
    """

    def __init__(self, bot_token: str, channel_id: str):
        """
        Initialize the publisher.

        Args:
            bot_token: Telegram bot token
            channel_id: Target channel ID or @username
        """
        self.bot = Bot(token=bot_token)
        self.channel_id = channel_id

    async def publish_article(
        self,
        article: GeneratedArticle,
        market: Market,
    ) -> Optional[int]:
        """
        Publish an article to the Telegram channel.

        Args:
            article: Generated article to publish
            market: Market data for additional info

        Returns:
            Telegram message ID if successful, None otherwise
        """
        try:
            # Format the complete message
            message = self._format_message(article, market)

            # Send to channel
            sent_message = await self.bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )

            logger.info(
                f"Published article to {self.channel_id}: "
                f"message_id={sent_message.message_id}"
            )

            return sent_message.message_id

        except TelegramError as e:
            logger.error(f"Failed to publish article: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error publishing article: {e}")
            return None

    def _format_message(
        self,
        article: GeneratedArticle,
        market: Market,
    ) -> str:
        """
        Format the complete message for Telegram.

        Args:
            article: Generated article
            market: Market data

        Returns:
            Formatted message text with HTML
        """
        # Build Polymarket URL
        polymarket_url = ""
        if market.slug:
            polymarket_url = f"https://polymarket.com/event/{market.slug}"
        elif market.event_id:
            polymarket_url = f"https://polymarket.com/event/{market.event_id}"

        # Build the message
        parts = []

        # Title as header
        if article.title:
            parts.append(f"<b>{article.title}</b>\n")

        # Article body
        parts.append(article.body)

        # Market link section
        parts.append("\n\n━━━━━━━━━━━━━━━━")

        # Quick stats
        stats_line = (
            f"📊 <b>Market:</b> YES {market.yes_price * 100:.0f}% | "
            f"NO {market.no_price * 100:.0f}%"
        )
        parts.append(stats_line)

        if market.total_volume >= 1000:
            volume_str = f"${market.total_volume / 1000:.0f}K"
        else:
            volume_str = f"${market.total_volume:.0f}"
        parts.append(f"💰 <b>Volume:</b> {volume_str}")

        # Polymarket link
        if polymarket_url:
            parts.append(f"\n🔗 <a href=\"{polymarket_url}\">Trade on Polymarket</a>")

        return "\n".join(parts)

    async def send_test_message(self, text: str) -> bool:
        """
        Send a test message to verify channel access.

        Args:
            text: Test message text

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            return True
        except TelegramError as e:
            logger.error(f"Test message failed: {e}")
            return False

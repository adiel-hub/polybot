"""Telegram publisher service for posting articles to channels."""

import logging
from typing import Optional, List, Dict

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError

from core.polymarket.gamma_client import Market
from news_bot.services.article_generator import GeneratedArticle
from utils.short_id import generate_short_id

logger = logging.getLogger(__name__)


class TelegramPublisherService:
    """
    Publishes news articles to multiple Telegram channels/groups.

    Handles message formatting and posting via Telegram Bot API.
    Can broadcast to multiple channels or discover channels automatically.
    """

    def __init__(
        self,
        bot_token: str,
        channel_ids: str = "",
        trading_bot_username: str = "",
    ):
        """
        Initialize the publisher.

        Args:
            bot_token: Telegram bot token
            channel_ids: Comma-separated list of channel IDs or @usernames
                        Leave empty to use registered channels from database
            trading_bot_username: Username of the trading bot for deep links
        """
        self.bot = Bot(token=bot_token)
        self.trading_bot_username = trading_bot_username

        # Parse channel IDs from comma-separated string
        self._channel_ids: List[str] = []
        if channel_ids:
            self._channel_ids = [
                cid.strip() for cid in channel_ids.split(",")
                if cid.strip()
            ]

        # Track registered channels (channels can register themselves)
        self._registered_channels: set = set()

    @property
    def channel_ids(self) -> List[str]:
        """Get list of all channels to broadcast to."""
        # Combine configured channels and registered channels
        all_channels = set(self._channel_ids) | self._registered_channels
        return list(all_channels)

    def register_channel(self, channel_id: str) -> None:
        """
        Register a channel to receive broadcasts.

        Args:
            channel_id: Channel ID or @username to register
        """
        self._registered_channels.add(channel_id)
        logger.info(f"Registered channel for broadcasts: {channel_id}")

    def unregister_channel(self, channel_id: str) -> None:
        """
        Unregister a channel from broadcasts.

        Args:
            channel_id: Channel ID or @username to unregister
        """
        self._registered_channels.discard(channel_id)
        logger.info(f"Unregistered channel from broadcasts: {channel_id}")

    async def publish_article(
        self,
        article: GeneratedArticle,
        market: Market,
    ) -> Dict[str, Optional[int]]:
        """
        Publish an article to all registered channels.

        Args:
            article: Generated article to publish
            market: Market data for additional info

        Returns:
            Dict mapping channel_id to message_id (or None if failed)
        """
        results = {}

        channels = self.channel_ids
        if not channels:
            logger.warning("No channels configured for broadcasting")
            return results

        # Format the message once
        message = self._format_message(article, market)
        keyboard = self._build_keyboard(market)

        # Send to all channels
        for channel_id in channels:
            try:
                sent_message = await self.bot.send_message(
                    chat_id=channel_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                )
                results[channel_id] = sent_message.message_id
                logger.info(
                    f"Published article to {channel_id}: "
                    f"message_id={sent_message.message_id}"
                )
            except TelegramError as e:
                logger.error(f"Failed to publish to {channel_id}: {e}")
                results[channel_id] = None
            except Exception as e:
                logger.error(f"Unexpected error publishing to {channel_id}: {e}")
                results[channel_id] = None

        # Log summary
        successful = sum(1 for v in results.values() if v is not None)
        logger.info(f"Published to {successful}/{len(channels)} channels")

        return results

    def _build_keyboard(self, market: Market) -> Optional[InlineKeyboardMarkup]:
        """
        Build inline keyboard with Trade and View buttons.

        Args:
            market: Market data

        Returns:
            InlineKeyboardMarkup with buttons or None
        """
        buttons = []

        # Trade button - deep link to trading bot
        if self.trading_bot_username:
            short_id = generate_short_id(market.condition_id)
            trade_url = f"https://t.me/{self.trading_bot_username}?start=m_{short_id}"
            buttons.append(
                InlineKeyboardButton(
                    text="📈 Trade Now",
                    url=trade_url,
                )
            )

        # View on Polymarket button
        polymarket_url = ""
        if market.slug:
            polymarket_url = f"https://polymarket.com/event/{market.slug}"
        elif market.event_id:
            polymarket_url = f"https://polymarket.com/event/{market.event_id}"

        if polymarket_url:
            buttons.append(
                InlineKeyboardButton(
                    text="🔗 Polymarket",
                    url=polymarket_url,
                )
            )

        if buttons:
            return InlineKeyboardMarkup([buttons])
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
        parts = []

        # Title as header
        if article.title:
            parts.append(f"<b>{article.title}</b>\n")

        # Article body
        parts.append(article.body)

        # Market stats section
        parts.append("\n\n━━━━━━━━━━━━━━━━")

        # Quick stats
        stats_line = (
            f"📊 <b>Market:</b> YES {market.yes_price * 100:.0f}% | "
            f"NO {market.no_price * 100:.0f}%"
        )
        parts.append(stats_line)

        if market.total_volume >= 1000000:
            volume_str = f"${market.total_volume / 1000000:.1f}M"
        elif market.total_volume >= 1000:
            volume_str = f"${market.total_volume / 1000:.0f}K"
        else:
            volume_str = f"${market.total_volume:.0f}"
        parts.append(f"💰 <b>Volume:</b> {volume_str}")

        return "\n".join(parts)

    async def send_test_message(self, text: str, channel_id: str = None) -> bool:
        """
        Send a test message to verify channel access.

        Args:
            text: Test message text
            channel_id: Specific channel to test (or first configured channel)

        Returns:
            True if successful, False otherwise
        """
        target = channel_id or (self.channel_ids[0] if self.channel_ids else None)
        if not target:
            logger.error("No channel configured for test message")
            return False

        try:
            await self.bot.send_message(
                chat_id=target,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            return True
        except TelegramError as e:
            logger.error(f"Test message to {target} failed: {e}")
            return False

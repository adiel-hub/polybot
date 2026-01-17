"""Tests for the Telegram publisher service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Message, Bot
from telegram.error import TelegramError

from core.polymarket.gamma_client import Market
from news_bot.services.article_generator import GeneratedArticle
from news_bot.services.telegram_publisher import TelegramPublisherService


@pytest.fixture
def mock_bot():
    """Create a mock Bot object."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def sample_market():
    """Create a sample market for testing."""
    return Market(
        condition_id="0x1234567890abcdef",
        question="Will Bitcoin reach $100,000 by end of 2025?",
        description="A prediction market on Bitcoin's price",
        category="crypto",
        image_url="https://example.com/btc.png",
        yes_token_id="token_yes",
        no_token_id="token_no",
        yes_price=0.65,
        no_price=0.35,
        volume_24h=50000,
        total_volume=500000,
        liquidity=100000,
        end_date="2025-12-31",
        is_active=True,
        slug="bitcoin-100k-2025",
        event_id="event1",
    )


@pytest.fixture
def sample_article():
    """Create a sample article for testing."""
    return GeneratedArticle(
        title="Bitcoin Eyes $100K as Market Momentum Builds",
        body="Bitcoin continues its strong rally as institutional investors pile in. "
             "Analysts predict the cryptocurrency could reach new all-time highs.",
        tokens_used=500,
    )


class TestTelegramPublisherService:
    """Tests for TelegramPublisherService."""

    def test_init_parses_channel_ids(self):
        """Test that channel IDs are correctly parsed from comma-separated string."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@channel1, -1001234567890, @channel2",
            trading_bot_username="TestBot",
        )

        assert len(publisher._channel_ids) == 3
        assert "@channel1" in publisher._channel_ids
        assert "-1001234567890" in publisher._channel_ids
        assert "@channel2" in publisher._channel_ids

    def test_init_handles_empty_channel_ids(self):
        """Test handling of empty channel IDs."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="",
        )

        assert len(publisher._channel_ids) == 0

    def test_init_handles_whitespace_only(self):
        """Test handling of whitespace-only channel IDs."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="  ,  ,  ",
        )

        assert len(publisher._channel_ids) == 0

    def test_register_channel(self):
        """Test channel registration."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@channel1",
        )

        publisher.register_channel("@channel2")

        assert "@channel1" in publisher.channel_ids
        assert "@channel2" in publisher.channel_ids

    def test_unregister_channel(self):
        """Test channel unregistration."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="",
        )

        publisher.register_channel("@channel1")
        publisher.register_channel("@channel2")
        publisher.unregister_channel("@channel1")

        assert "@channel1" not in publisher.channel_ids
        assert "@channel2" in publisher.channel_ids

    def test_channel_ids_combines_configured_and_registered(self):
        """Test that channel_ids property combines both sources."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@channel1",
        )

        publisher.register_channel("@channel2")

        channel_ids = publisher.channel_ids
        assert len(channel_ids) == 2
        assert "@channel1" in channel_ids
        assert "@channel2" in channel_ids

    def test_channel_ids_no_duplicates(self):
        """Test that duplicate channels are not included."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@channel1",
        )

        publisher.register_channel("@channel1")  # Same as configured

        assert len(publisher.channel_ids) == 1

    def test_format_message_includes_title(self, sample_article, sample_market):
        """Test that formatted message includes article title."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@test",
        )

        message = publisher._format_message(sample_article, sample_market)

        assert sample_article.title in message
        assert "<b>" in message  # HTML formatting

    def test_format_message_includes_body(self, sample_article, sample_market):
        """Test that formatted message includes article body."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@test",
        )

        message = publisher._format_message(sample_article, sample_market)

        assert sample_article.body in message

    def test_format_message_includes_market_stats(self, sample_article, sample_market):
        """Test that formatted message includes market statistics."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@test",
        )

        message = publisher._format_message(sample_article, sample_market)

        assert "65%" in message  # YES price
        assert "35%" in message  # NO price
        assert "$500" in message  # Volume (abbreviated)

    def test_format_message_formats_large_volume(self, sample_article, sample_market):
        """Test volume formatting for large numbers."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@test",
        )

        # Test millions
        sample_market.total_volume = 2500000
        message = publisher._format_message(sample_article, sample_market)
        assert "$2.5M" in message

        # Test thousands
        sample_market.total_volume = 75000
        message = publisher._format_message(sample_article, sample_market)
        assert "$75K" in message

    def test_build_keyboard_includes_trade_button(self, sample_market):
        """Test that keyboard includes Trade button when bot username is set."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@test",
            trading_bot_username="TestTradingBot",
        )

        keyboard = publisher._build_keyboard(sample_market)

        assert keyboard is not None
        buttons = keyboard.inline_keyboard[0]
        trade_button = next((b for b in buttons if "Trade" in b.text), None)
        assert trade_button is not None
        assert "t.me/TestTradingBot" in trade_button.url
        assert "start=m_" in trade_button.url

    def test_build_keyboard_includes_polymarket_button(self, sample_market):
        """Test that keyboard includes Polymarket button."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@test",
        )

        keyboard = publisher._build_keyboard(sample_market)

        assert keyboard is not None
        buttons = keyboard.inline_keyboard[0]
        poly_button = next((b for b in buttons if "Polymarket" in b.text), None)
        assert poly_button is not None
        assert "polymarket.com" in poly_button.url
        assert sample_market.slug in poly_button.url

    def test_build_keyboard_without_trading_bot(self, sample_market):
        """Test keyboard when no trading bot username is set."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@test",
            trading_bot_username="",
        )

        keyboard = publisher._build_keyboard(sample_market)

        # Should still have Polymarket button
        assert keyboard is not None
        buttons = keyboard.inline_keyboard[0]
        assert len(buttons) == 1  # Only Polymarket button
        assert "Polymarket" in buttons[0].text

    def test_build_keyboard_uses_event_id_fallback(self, sample_market):
        """Test keyboard uses event_id when slug is not available."""
        sample_market.slug = None
        sample_market.event_id = "event123"

        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="@test",
        )

        keyboard = publisher._build_keyboard(sample_market)

        buttons = keyboard.inline_keyboard[0]
        poly_button = next((b for b in buttons if "Polymarket" in b.text), None)
        assert "event123" in poly_button.url

    @pytest.mark.asyncio
    async def test_publish_article_to_multiple_channels(self, sample_article, sample_market, mock_bot):
        """Test publishing to multiple channels."""
        mock_message = MagicMock(spec=Message)
        mock_message.message_id = 123
        mock_bot.send_message.return_value = mock_message

        with patch("news_bot.services.telegram_publisher.Bot", return_value=mock_bot):
            publisher = TelegramPublisherService(
                bot_token="test_token",
                channel_ids="@channel1,@channel2,@channel3",
            )

            results = await publisher.publish_article(sample_article, sample_market)

            assert len(results) == 3
            assert results["@channel1"] == 123
            assert results["@channel2"] == 123
            assert results["@channel3"] == 123
            assert mock_bot.send_message.call_count == 3

    @pytest.mark.asyncio
    async def test_publish_article_handles_partial_failure(self, sample_article, sample_market, mock_bot):
        """Test that publishing continues even if some channels fail."""
        mock_message = MagicMock(spec=Message)
        mock_message.message_id = 123

        async def mock_send(chat_id, **kwargs):
            if chat_id == "@channel2":
                raise TelegramError("Channel not found")
            return mock_message

        mock_bot.send_message.side_effect = mock_send

        with patch("news_bot.services.telegram_publisher.Bot", return_value=mock_bot):
            publisher = TelegramPublisherService(
                bot_token="test_token",
                channel_ids="@channel1,@channel2,@channel3",
            )

            results = await publisher.publish_article(sample_article, sample_market)

            assert results["@channel1"] == 123
            assert results["@channel2"] is None  # Failed
            assert results["@channel3"] == 123

    @pytest.mark.asyncio
    async def test_publish_article_no_channels(self, sample_article, sample_market):
        """Test publishing when no channels are configured."""
        publisher = TelegramPublisherService(
            bot_token="test_token",
            channel_ids="",
        )

        results = await publisher.publish_article(sample_article, sample_market)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_send_test_message_success(self, mock_bot):
        """Test sending a test message successfully."""
        with patch("news_bot.services.telegram_publisher.Bot", return_value=mock_bot):
            publisher = TelegramPublisherService(
                bot_token="test_token",
                channel_ids="@test_channel",
            )

            result = await publisher.send_test_message("Hello, test!")

            assert result is True
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_test_message_failure(self, mock_bot):
        """Test handling of test message failure."""
        mock_bot.send_message.side_effect = TelegramError("Access denied")

        with patch("news_bot.services.telegram_publisher.Bot", return_value=mock_bot):
            publisher = TelegramPublisherService(
                bot_token="test_token",
                channel_ids="@test_channel",
            )

            result = await publisher.send_test_message("Hello, test!")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_test_message_no_channel(self, mock_bot):
        """Test sending test message when no channel is configured."""
        with patch("news_bot.services.telegram_publisher.Bot", return_value=mock_bot):
            publisher = TelegramPublisherService(
                bot_token="test_token",
                channel_ids="",
            )

            result = await publisher.send_test_message("Hello!")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_test_message_specific_channel(self, mock_bot):
        """Test sending test message to a specific channel."""
        with patch("news_bot.services.telegram_publisher.Bot", return_value=mock_bot):
            publisher = TelegramPublisherService(
                bot_token="test_token",
                channel_ids="@default_channel",
            )

            await publisher.send_test_message("Hello!", channel_id="@specific_channel")

            mock_bot.send_message.assert_called_once()
            call_args = mock_bot.send_message.call_args
            assert call_args.kwargs["chat_id"] == "@specific_channel"

"""Tests for formatting.py."""

import pytest
from datetime import datetime

from utils.formatting import (
    generate_short_id,
    shorten_address,
    format_whale_alert,
    create_deep_link,
    format_amount,
)
from monitors.whale_monitor import WhaleTrade


class TestGenerateShortId:
    """Tests for generate_short_id function."""

    def test_generate_short_id_basic(self):
        """Test basic short ID generation."""
        condition_id = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        short_id = generate_short_id(condition_id)

        assert len(short_id) == 8
        assert short_id.isalnum()

    def test_generate_short_id_deterministic(self):
        """Test that same input produces same output."""
        condition_id = "0xabcdef1234567890"

        id1 = generate_short_id(condition_id)
        id2 = generate_short_id(condition_id)

        assert id1 == id2

    def test_generate_short_id_different_inputs(self):
        """Test that different inputs produce different outputs."""
        id1 = generate_short_id("0xabc123")
        id2 = generate_short_id("0xdef456")

        assert id1 != id2

    def test_generate_short_id_with_0x_prefix(self):
        """Test handling of 0x prefix."""
        with_prefix = generate_short_id("0xabcdef")
        without_prefix = generate_short_id("abcdef")

        assert with_prefix == without_prefix

    def test_generate_short_id_case_insensitive(self):
        """Test case insensitivity."""
        lower = generate_short_id("0xabcdef")
        upper = generate_short_id("0xABCDEF")

        assert lower == upper

    def test_generate_short_id_custom_length(self):
        """Test custom length parameter."""
        short_id = generate_short_id("0xabcdef", length=12)

        assert len(short_id) == 12


class TestShortenAddress:
    """Tests for shorten_address function."""

    def test_shorten_address_basic(self):
        """Test basic address shortening."""
        address = "0x1234567890abcdef1234567890abcdef12345678"
        shortened = shorten_address(address)

        assert shortened == "0x1234...5678"

    def test_shorten_address_custom_chars(self):
        """Test custom character count."""
        address = "0x1234567890abcdef1234567890abcdef12345678"
        shortened = shorten_address(address, chars=8)

        assert shortened == "0x123456...5678"

    def test_shorten_address_short_input(self):
        """Test with short address."""
        address = "0x1234"
        shortened = shorten_address(address)

        assert shortened == "0x1234"

    def test_shorten_address_empty(self):
        """Test with empty address."""
        shortened = shorten_address("")

        assert shortened == "Unknown"

    def test_shorten_address_none(self):
        """Test with None address."""
        shortened = shorten_address(None)

        assert shortened == "Unknown"


class TestFormatWhaleAlert:
    """Tests for format_whale_alert function."""

    def test_format_whale_alert_buy(self, sample_whale_trade):
        """Test formatting BUY trade alert."""
        message = format_whale_alert(sample_whale_trade)

        assert "WHALE ALERT" in message
        assert "Polymarket" in message
        assert "Will Bitcoin reach $100k" in message
        assert "BUYING" in message
        assert "Yes" in message
        assert "65%" in message
        assert "$32,500.00" in message
        assert "50,000" in message
        assert sample_whale_trade.trader_address in message

    def test_format_whale_alert_sell(self):
        """Test formatting SELL trade alert."""
        trade = WhaleTrade(
            trader_address="0x1234567890abcdef1234567890abcdef12345678",
            trader_name=None,
            market_title="Test Market",
            condition_id="0xabc",
            outcome="No",
            side="SELL",
            size=10000.0,
            price=0.40,
            value=4000.0,
            tx_hash=None,
            timestamp=datetime(2026, 1, 18, 12, 0, 0),
            market_slug=None,
            market_icon=None,
        )

        message = format_whale_alert(trade)

        assert "SELLING" in message
        assert "No" in message
        assert "40%" in message

    def test_format_whale_alert_with_trader_name(self, sample_whale_trade):
        """Test formatting with trader name."""
        message = format_whale_alert(sample_whale_trade)

        assert "WhaleTrader" in message

    def test_format_whale_alert_without_trader_name(self):
        """Test formatting without trader name."""
        trade = WhaleTrade(
            trader_address="0x1234567890abcdef1234567890abcdef12345678",
            trader_name=None,
            market_title="Test Market",
            condition_id="0xabc",
            outcome="Yes",
            side="BUY",
            size=10000.0,
            price=0.50,
            value=5000.0,
            tx_hash=None,
            timestamp=datetime(2026, 1, 18, 12, 0, 0),
            market_slug=None,
            market_icon=None,
        )

        message = format_whale_alert(trade)

        # Should still have trader address
        assert "0x1234" in message

    def test_format_whale_alert_timestamp(self, sample_whale_trade):
        """Test timestamp formatting."""
        message = format_whale_alert(sample_whale_trade)

        assert "2026-01-18" in message
        assert "12:30:00" in message

    def test_format_whale_alert_markdown(self, sample_whale_trade):
        """Test Markdown formatting."""
        message = format_whale_alert(sample_whale_trade)

        # Check for Markdown elements
        assert "*" in message  # Bold
        assert "_" in message  # Italic
        assert "`" in message  # Code


class TestCreateDeepLink:
    """Tests for create_deep_link function."""

    def test_create_deep_link_basic(self):
        """Test basic deep link creation."""
        condition_id = "0xabcdef1234567890"
        bot_username = "TestPolyBot"

        link = create_deep_link(condition_id, bot_username)

        assert link.startswith("https://t.me/TestPolyBot?start=m_")
        assert len(link) > len("https://t.me/TestPolyBot?start=m_")

    def test_create_deep_link_format(self):
        """Test deep link format."""
        condition_id = "0xabcdef"
        bot_username = "MyBot"

        link = create_deep_link(condition_id, bot_username)

        # Should be: https://t.me/MyBot?start=m_{short_id}
        assert "https://t.me/MyBot?start=m_" in link

    def test_create_deep_link_deterministic(self):
        """Test that same input produces same deep link."""
        condition_id = "0xabcdef1234567890"
        bot_username = "TestBot"

        link1 = create_deep_link(condition_id, bot_username)
        link2 = create_deep_link(condition_id, bot_username)

        assert link1 == link2


class TestFormatAmount:
    """Tests for format_amount function."""

    def test_format_amount_basic(self):
        """Test basic amount formatting."""
        formatted = format_amount(1234.56)

        assert formatted == "$1,234.56"

    def test_format_amount_large(self):
        """Test large amount formatting."""
        formatted = format_amount(1234567.89)

        assert formatted == "$1,234,567.89"

    def test_format_amount_small(self):
        """Test small amount formatting."""
        formatted = format_amount(0.50)

        assert formatted == "$0.50"

    def test_format_amount_zero(self):
        """Test zero amount formatting."""
        formatted = format_amount(0)

        assert formatted == "$0.00"

    def test_format_amount_rounding(self):
        """Test amount rounding."""
        formatted = format_amount(1234.567)

        assert formatted == "$1,234.57"

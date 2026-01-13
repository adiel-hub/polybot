"""Tests for formatting utilities.

Tests the formatter functions used for displaying data
in Telegram bot messages.
"""

import pytest

from utils.formatters import (
    format_price,
    format_amount,
    format_pnl,
    format_percentage,
    format_address,
    format_tx_hash,
)


class TestFormatPrice:
    """Tests for format_price function."""

    def test_format_price_fifty_cents(self):
        """Test formatting 0.50 as cents."""
        result = format_price(0.50)
        assert result == "50.0c"

    def test_format_price_low_price(self):
        """Test formatting low price."""
        result = format_price(0.05)
        assert result == "5.0c"

    def test_format_price_high_price(self):
        """Test formatting high price."""
        result = format_price(0.95)
        assert result == "95.0c"

    def test_format_price_with_decimal(self):
        """Test formatting price with decimal."""
        result = format_price(0.657)
        assert result == "65.7c"

    def test_format_price_minimum(self):
        """Test formatting minimum price."""
        result = format_price(0.01)
        assert result == "1.0c"


class TestFormatAmount:
    """Tests for format_amount function."""

    def test_format_amount_small(self):
        """Test formatting small amount (< $1000)."""
        result = format_amount(100.50)
        assert result == "$100.50"

    def test_format_amount_zero(self):
        """Test formatting zero amount."""
        result = format_amount(0)
        assert result == "$0.00"

    def test_format_amount_thousands(self):
        """Test formatting thousands with K suffix."""
        result = format_amount(5000)
        assert result == "$5.0K"

    def test_format_amount_thousands_with_decimal(self):
        """Test formatting thousands with decimal K suffix."""
        result = format_amount(5500)
        assert result == "$5.5K"

    def test_format_amount_millions(self):
        """Test formatting millions with M suffix."""
        result = format_amount(2000000)
        assert result == "$2.00M"

    def test_format_amount_millions_with_decimal(self):
        """Test formatting millions with decimal M suffix."""
        result = format_amount(1500000)
        assert result == "$1.50M"

    def test_format_amount_at_thousand_boundary(self):
        """Test formatting at $1000 boundary."""
        result = format_amount(1000)
        assert result == "$1.0K"

    def test_format_amount_just_under_thousand(self):
        """Test formatting just under $1000."""
        result = format_amount(999.99)
        assert result == "$999.99"

    def test_format_amount_at_million_boundary(self):
        """Test formatting at $1M boundary."""
        result = format_amount(1000000)
        assert result == "$1.00M"


class TestFormatPnl:
    """Tests for format_pnl function."""

    def test_format_positive_pnl(self):
        """Test formatting positive PnL with + sign."""
        result = format_pnl(50.25)
        assert result == "+$50.25"

    def test_format_negative_pnl(self):
        """Test formatting negative PnL."""
        result = format_pnl(-30.50)
        # Format includes sign before dollar sign: $-30.50
        assert result == "$-30.50"

    def test_format_zero_pnl(self):
        """Test formatting zero PnL (shows + sign)."""
        result = format_pnl(0)
        assert result == "+$0.00"

    def test_format_large_positive_pnl(self):
        """Test formatting large positive PnL."""
        result = format_pnl(10000.00)
        assert result == "+$10000.00"

    def test_format_large_negative_pnl(self):
        """Test formatting large negative PnL."""
        result = format_pnl(-5000.00)
        assert result == "$-5000.00"


class TestFormatPercentage:
    """Tests for format_percentage function."""

    def test_format_positive_percentage(self):
        """Test formatting positive percentage with + sign."""
        result = format_percentage(25.5)
        assert result == "+25.5%"

    def test_format_negative_percentage(self):
        """Test formatting negative percentage."""
        result = format_percentage(-15.2)
        assert result == "-15.2%"

    def test_format_zero_percentage(self):
        """Test formatting zero percentage (shows + sign)."""
        result = format_percentage(0)
        assert result == "+0.0%"

    def test_format_large_percentage(self):
        """Test formatting large percentage."""
        result = format_percentage(150.0)
        assert result == "+150.0%"


class TestFormatAddress:
    """Tests for format_address function."""

    def test_format_address_shortened(self):
        """Test that address is shortened correctly."""
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD"
        result = format_address(address)

        # Should show first 6 chars, ..., last 4 chars
        assert result == "0x742d...abCD"

    def test_format_address_preserves_case(self):
        """Test that address case is preserved."""
        address = "0xABCDEF1234567890ABCDEF1234567890ABCDEF12"
        result = format_address(address)

        assert result == "0xABCD...EF12"

    def test_format_address_lowercase(self):
        """Test formatting lowercase address."""
        address = "0xabcdef1234567890abcdef1234567890abcdef12"
        result = format_address(address)

        assert result == "0xabcd...ef12"


class TestFormatTxHash:
    """Tests for format_tx_hash function."""

    def test_format_tx_hash_shortened(self):
        """Test that transaction hash is shortened correctly."""
        tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        result = format_tx_hash(tx_hash)

        # Should show first 10 chars, ..., last 6 chars
        assert result == "0x12345678...abcdef"

    def test_format_tx_hash_preserves_case(self):
        """Test that tx hash case is preserved."""
        tx_hash = "0xABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234ABCDEF"
        result = format_tx_hash(tx_hash)

        assert result == "0xABCDEF12...ABCDEF"

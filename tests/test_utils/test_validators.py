"""Tests for validation utilities.

Tests the validator functions used for user input validation
including amounts, prices, addresses, and percentages.
"""

import pytest

from utils.validators import (
    validate_amount,
    validate_price,
    validate_address,
    validate_percentage,
    validate_withdrawal_amount,
)


class TestValidateAmount:
    """Tests for validate_amount function."""

    def test_valid_integer_amount(self):
        """Test validation of valid integer amount."""
        result = validate_amount("100")
        assert result == 100.0

    def test_valid_decimal_amount(self):
        """Test validation of valid decimal amount."""
        result = validate_amount("50.75")
        assert result == 50.75

    def test_valid_amount_with_whitespace(self):
        """Test validation strips whitespace."""
        result = validate_amount("  25.00  ")
        assert result == 25.0

    def test_amount_below_minimum(self):
        """Test that amount below minimum returns None."""
        result = validate_amount("0.001", min_val=0.01)
        assert result is None

    def test_amount_above_maximum(self):
        """Test that amount above maximum returns None."""
        result = validate_amount("150000", max_val=100000)
        assert result is None

    def test_amount_at_minimum_boundary(self):
        """Test that amount at minimum boundary is valid."""
        result = validate_amount("0.01", min_val=0.01)
        assert result == 0.01

    def test_amount_at_maximum_boundary(self):
        """Test that amount at maximum boundary is valid."""
        result = validate_amount("100000", max_val=100000)
        assert result == 100000.0

    def test_negative_amount(self):
        """Test that negative amount returns None."""
        result = validate_amount("-10")
        assert result is None

    def test_invalid_string(self):
        """Test that invalid string returns None."""
        result = validate_amount("not_a_number")
        assert result is None

    def test_empty_string(self):
        """Test that empty string returns None."""
        result = validate_amount("")
        assert result is None

    def test_custom_min_max(self):
        """Test custom min and max values."""
        result = validate_amount("5", min_val=1, max_val=10)
        assert result == 5.0

        result = validate_amount("0.5", min_val=1, max_val=10)
        assert result is None

        result = validate_amount("15", min_val=1, max_val=10)
        assert result is None


class TestValidatePrice:
    """Tests for validate_price function."""

    def test_valid_decimal_price(self):
        """Test validation of valid decimal price (0.01-0.99)."""
        result = validate_price("0.65")
        assert result == 0.65

    def test_valid_cents_price(self):
        """Test that price in cents is converted to decimal."""
        result = validate_price("45")
        assert result == 0.45

    def test_price_at_minimum_boundary(self):
        """Test price at minimum (0.01)."""
        result = validate_price("0.01")
        assert result == 0.01

        # Note: value of "1" is treated as decimal 1.0 (not cents)
        # since it's not > 1. This exceeds MAX_PRICE, so returns None.
        # Use "2" for 2 cents conversion test
        result = validate_price("2")  # 2 cents -> 0.02
        assert result == 0.02

    def test_price_at_maximum_boundary(self):
        """Test price at maximum (0.99)."""
        result = validate_price("0.99")
        assert result == 0.99

        result = validate_price("99")  # 99 cents
        assert result == 0.99

    def test_price_below_minimum(self):
        """Test that price below minimum returns None."""
        result = validate_price("0.001")
        assert result is None

    def test_price_above_maximum(self):
        """Test that price above maximum returns None."""
        result = validate_price("1.00")
        assert result is None

        result = validate_price("100")  # 100 cents = $1.00
        assert result is None

    def test_price_with_whitespace(self):
        """Test that whitespace is stripped."""
        result = validate_price("  0.50  ")
        assert result == 0.50

    def test_invalid_price_string(self):
        """Test that invalid string returns None."""
        result = validate_price("invalid")
        assert result is None


class TestValidateAddress:
    """Tests for validate_address function."""

    def test_valid_lowercase_address(self):
        """Test validation of valid lowercase address."""
        address = "0x742d35cc6634c0532925a3b844bc9e7595f1abcd"
        result = validate_address(address)
        assert result == address

    def test_valid_mixed_case_address_returns_lowercase(self):
        """Test that mixed case address is returned lowercase."""
        address = "0x742D35Cc6634C0532925a3b844Bc9e7595F1AbCd"
        result = validate_address(address)
        assert result == address.lower()

    def test_address_with_whitespace(self):
        """Test that whitespace is stripped."""
        address = "  0x742d35cc6634c0532925a3b844bc9e7595f1abcd  "
        result = validate_address(address)
        assert result == "0x742d35cc6634c0532925a3b844bc9e7595f1abcd"

    def test_address_missing_0x_prefix(self):
        """Test that address without 0x prefix returns None."""
        address = "742d35cc6634c0532925a3b844bc9e7595f1abcd"
        result = validate_address(address)
        assert result is None

    def test_address_too_short(self):
        """Test that short address returns None."""
        result = validate_address("0x1234")
        assert result is None

    def test_address_too_long(self):
        """Test that long address returns None."""
        address = "0x" + "a" * 50
        result = validate_address(address)
        assert result is None

    def test_address_with_invalid_characters(self):
        """Test that address with non-hex chars returns None."""
        address = "0xgggggggggggggggggggggggggggggggggggggggg"
        result = validate_address(address)
        assert result is None

    def test_empty_address(self):
        """Test that empty string returns None."""
        result = validate_address("")
        assert result is None


class TestValidatePercentage:
    """Tests for validate_percentage function."""

    def test_valid_percentage(self):
        """Test validation of valid percentage."""
        result = validate_percentage("50")
        assert result == 50.0

    def test_valid_decimal_percentage(self):
        """Test validation of decimal percentage."""
        result = validate_percentage("33.5")
        assert result == 33.5

    def test_percentage_at_minimum(self):
        """Test percentage at minimum boundary (1%)."""
        result = validate_percentage("1")
        assert result == 1.0

    def test_percentage_at_maximum(self):
        """Test percentage at maximum boundary (100%)."""
        result = validate_percentage("100")
        assert result == 100.0

    def test_percentage_below_minimum(self):
        """Test that percentage below minimum returns None."""
        result = validate_percentage("0.5")
        assert result is None

    def test_percentage_above_maximum(self):
        """Test that percentage above maximum returns None."""
        result = validate_percentage("101")
        assert result is None

    def test_percentage_with_whitespace(self):
        """Test that whitespace is stripped."""
        result = validate_percentage("  75  ")
        assert result == 75.0

    def test_invalid_percentage_string(self):
        """Test that invalid string returns None."""
        result = validate_percentage("invalid")
        assert result is None

    def test_custom_min_max(self):
        """Test custom min and max values."""
        result = validate_percentage("5", min_val=5, max_val=50)
        assert result == 5.0

        result = validate_percentage("4", min_val=5, max_val=50)
        assert result is None


class TestValidateWithdrawalAmount:
    """Tests for validate_withdrawal_amount function."""

    def test_valid_withdrawal(self):
        """Test validation of valid withdrawal amount."""
        result = validate_withdrawal_amount("50", balance=100)
        assert result == 50.0

    def test_withdrawal_equals_balance(self):
        """Test withdrawal equal to balance is valid."""
        result = validate_withdrawal_amount("100", balance=100)
        assert result == 100.0

    def test_withdrawal_exceeds_balance(self):
        """Test that withdrawal exceeding balance returns None."""
        result = validate_withdrawal_amount("150", balance=100)
        assert result is None

    def test_withdrawal_below_minimum(self):
        """Test that withdrawal below minimum returns None."""
        result = validate_withdrawal_amount("0.5", balance=100)  # MIN_WITHDRAWAL is 1.0
        assert result is None

    def test_withdrawal_above_maximum(self):
        """Test that withdrawal above maximum returns None."""
        result = validate_withdrawal_amount("15000", balance=20000)  # MAX is 10000
        assert result is None

    def test_invalid_withdrawal_string(self):
        """Test that invalid string returns None."""
        result = validate_withdrawal_amount("invalid", balance=100)
        assert result is None

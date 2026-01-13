"""Tests for Order model.

Tests the Order dataclass and related enums for order management.
"""

from datetime import datetime

import pytest

from database.models.order import (
    Order,
    OrderSide,
    OrderType,
    OrderStatus,
    Outcome,
)


class TestOrderEnums:
    """Tests for order-related enums."""

    def test_order_side_values(self):
        """Test OrderSide enum has correct values."""
        assert OrderSide.BUY.value == "BUY"
        assert OrderSide.SELL.value == "SELL"

    def test_order_type_values(self):
        """Test OrderType enum has correct values."""
        assert OrderType.MARKET.value == "MARKET"
        assert OrderType.LIMIT.value == "LIMIT"
        assert OrderType.FOK.value == "FOK"

    def test_order_status_values(self):
        """Test OrderStatus enum has all expected values."""
        expected_statuses = [
            "PENDING",
            "OPEN",
            "PARTIALLY_FILLED",
            "FILLED",
            "CANCELLED",
            "FAILED",
        ]
        actual_statuses = [s.value for s in OrderStatus]
        assert set(expected_statuses) == set(actual_statuses)

    def test_outcome_values(self):
        """Test Outcome enum has YES and NO."""
        assert Outcome.YES.value == "YES"
        assert Outcome.NO.value == "NO"


class TestOrderModel:
    """Tests for Order dataclass."""

    def _create_mock_row(self, **kwargs):
        """Create a dictionary that mimics a database row."""
        defaults = {
            "id": 1,
            "user_id": 10,
            "polymarket_order_id": "pm_order_123",
            "market_condition_id": "condition_abc",
            "market_question": "Will Bitcoin reach $100K?",
            "token_id": "token_yes_123",
            "side": "BUY",
            "order_type": "MARKET",
            "price": None,
            "size": 10.0,
            "filled_size": 0.0,
            "status": "PENDING",
            "outcome": "YES",
            "error_message": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "executed_at": None,
        }
        defaults.update(kwargs)
        return defaults

    def test_from_row_creates_order(self):
        """Test that from_row creates Order from database row."""
        row = self._create_mock_row()

        order = Order.from_row(row)

        assert order.id == 1
        assert order.user_id == 10
        assert order.polymarket_order_id == "pm_order_123"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.size == 10.0
        assert order.status == OrderStatus.PENDING
        assert order.outcome == Outcome.YES

    def test_from_row_handles_limit_order(self):
        """Test that from_row handles limit order with price."""
        row = self._create_mock_row(
            order_type="LIMIT", price=0.65, status="OPEN"
        )

        order = Order.from_row(row)

        assert order.order_type == OrderType.LIMIT
        assert order.price == 0.65
        assert order.status == OrderStatus.OPEN

    def test_from_row_handles_sell_order(self):
        """Test that from_row handles sell order."""
        row = self._create_mock_row(side="SELL", outcome="NO")

        order = Order.from_row(row)

        assert order.side == OrderSide.SELL
        assert order.outcome == Outcome.NO

    def test_from_row_handles_null_filled_size(self):
        """Test that from_row handles null filled_size."""
        row = self._create_mock_row(filled_size=None)

        order = Order.from_row(row)

        assert order.filled_size == 0.0

    def test_from_row_handles_null_outcome(self):
        """Test that from_row handles null outcome."""
        row = self._create_mock_row(outcome=None)

        order = Order.from_row(row)

        assert order.outcome is None

    def test_is_open_for_pending_order(self):
        """Test is_open returns True for PENDING status."""
        row = self._create_mock_row(status="PENDING")
        order = Order.from_row(row)

        assert order.is_open is True

    def test_is_open_for_open_order(self):
        """Test is_open returns True for OPEN status."""
        row = self._create_mock_row(status="OPEN")
        order = Order.from_row(row)

        assert order.is_open is True

    def test_is_open_for_partially_filled_order(self):
        """Test is_open returns True for PARTIALLY_FILLED status."""
        row = self._create_mock_row(status="PARTIALLY_FILLED")
        order = Order.from_row(row)

        assert order.is_open is True

    def test_is_open_for_filled_order(self):
        """Test is_open returns False for FILLED status."""
        row = self._create_mock_row(status="FILLED")
        order = Order.from_row(row)

        assert order.is_open is False

    def test_is_open_for_cancelled_order(self):
        """Test is_open returns False for CANCELLED status."""
        row = self._create_mock_row(status="CANCELLED")
        order = Order.from_row(row)

        assert order.is_open is False

    def test_is_open_for_failed_order(self):
        """Test is_open returns False for FAILED status."""
        row = self._create_mock_row(status="FAILED")
        order = Order.from_row(row)

        assert order.is_open is False

    def test_fill_percentage_zero_when_not_filled(self):
        """Test fill_percentage is 0 when nothing filled."""
        row = self._create_mock_row(size=10.0, filled_size=0.0)
        order = Order.from_row(row)

        assert order.fill_percentage == 0.0

    def test_fill_percentage_partial_fill(self):
        """Test fill_percentage calculates correctly for partial fill."""
        row = self._create_mock_row(size=10.0, filled_size=3.0)
        order = Order.from_row(row)

        assert order.fill_percentage == 30.0

    def test_fill_percentage_fully_filled(self):
        """Test fill_percentage is 100 when fully filled."""
        row = self._create_mock_row(size=10.0, filled_size=10.0)
        order = Order.from_row(row)

        assert order.fill_percentage == 100.0

    def test_fill_percentage_zero_size_order(self):
        """Test fill_percentage handles zero size order."""
        row = self._create_mock_row(size=0.0, filled_size=0.0)
        order = Order.from_row(row)

        assert order.fill_percentage == 0.0

    def test_remaining_size_nothing_filled(self):
        """Test remaining_size equals size when nothing filled."""
        row = self._create_mock_row(size=10.0, filled_size=0.0)
        order = Order.from_row(row)

        assert order.remaining_size == 10.0

    def test_remaining_size_partial_fill(self):
        """Test remaining_size calculates correctly for partial fill."""
        row = self._create_mock_row(size=10.0, filled_size=4.0)
        order = Order.from_row(row)

        assert order.remaining_size == 6.0

    def test_remaining_size_fully_filled(self):
        """Test remaining_size is 0 when fully filled."""
        row = self._create_mock_row(size=10.0, filled_size=10.0)
        order = Order.from_row(row)

        assert order.remaining_size == 0.0

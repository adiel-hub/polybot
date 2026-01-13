"""Tests for Gamma market data client.

Tests the Market dataclass parsing and GammaMarketClient functionality.
"""

import json
import pytest

from core.polymarket.gamma_client import Market


class TestMarketModel:
    """Tests for Market dataclass."""

    def test_from_api_with_complete_data(self, sample_market_data: dict):
        """Test creating Market from complete API data."""
        market = Market.from_api(sample_market_data)

        assert market.condition_id == "0xabcdef1234567890"
        assert market.question == "Will Bitcoin reach $100,000 by end of 2025?"
        assert market.description == "This market resolves to Yes if Bitcoin reaches $100,000."
        assert market.category == "crypto"
        assert market.yes_token_id == "token_yes_123"
        assert market.no_token_id == "token_no_456"
        assert market.yes_price == 0.65
        assert market.no_price == 0.35
        assert market.volume_24h == 50000.0
        assert market.total_volume == 1500000.0
        assert market.liquidity == 250000.0
        assert market.is_active is True

    def test_from_api_with_json_string_tokens(self):
        """Test parsing when clobTokenIds is a JSON string."""
        data = {
            "conditionId": "test_condition",
            "question": "Test Question?",
            "clobTokenIds": '["yes_token", "no_token"]',
            "outcomePrices": '["0.70", "0.30"]',
            "active": True,
            "closed": False,
        }

        market = Market.from_api(data)

        assert market.yes_token_id == "yes_token"
        assert market.no_token_id == "no_token"
        assert market.yes_price == 0.70
        assert market.no_price == 0.30

    def test_from_api_with_list_tokens(self):
        """Test parsing when clobTokenIds is already a list."""
        data = {
            "conditionId": "test_condition",
            "question": "Test Question?",
            "clobTokenIds": ["yes_token_list", "no_token_list"],
            "outcomePrices": [0.55, 0.45],
            "active": True,
            "closed": False,
        }

        market = Market.from_api(data)

        assert market.yes_token_id == "yes_token_list"
        assert market.no_token_id == "no_token_list"
        assert market.yes_price == 0.55
        assert market.no_price == 0.45

    def test_from_api_with_empty_tokens(self):
        """Test parsing with empty token arrays."""
        data = {
            "conditionId": "test_condition",
            "question": "Test Question?",
            "clobTokenIds": [],
            "outcomePrices": [],
            "active": True,
            "closed": False,
        }

        market = Market.from_api(data)

        assert market.yes_token_id == ""
        assert market.no_token_id == ""
        assert market.yes_price == 0.5  # Default
        assert market.no_price == 0.5  # Default

    def test_from_api_with_missing_tokens(self):
        """Test parsing with missing clobTokenIds field."""
        data = {
            "conditionId": "test_condition",
            "question": "Test Question?",
            "active": True,
            "closed": False,
        }

        market = Market.from_api(data)

        assert market.yes_token_id == ""
        assert market.no_token_id == ""

    def test_from_api_with_invalid_json_string(self):
        """Test parsing with invalid JSON string in clobTokenIds."""
        data = {
            "conditionId": "test_condition",
            "question": "Test Question?",
            "clobTokenIds": "not_valid_json",
            "outcomePrices": "also_not_valid",
            "active": True,
            "closed": False,
        }

        market = Market.from_api(data)

        # Should gracefully handle invalid JSON
        assert market.yes_token_id == ""
        assert market.yes_price == 0.5  # Default

    def test_from_api_uses_event_format(self):
        """Test parsing event format with nested markets array."""
        data = {
            "id": "event_123",
            "title": "Event Title",
            "category": "politics",
            "image": "https://example.com/image.png",
            "markets": [
                {
                    "conditionId": "nested_condition",
                    "question": "Nested Question?",
                    "clobTokenIds": ["yes", "no"],
                    "outcomePrices": [0.80, 0.20],
                    "volume24hr": 10000,
                }
            ],
        }

        market = Market.from_api(data)

        # Should use data from nested market
        assert market.condition_id == "nested_condition"
        assert market.question == "Nested Question?"
        assert market.yes_price == 0.80

    def test_from_api_closed_market(self):
        """Test parsing closed market sets is_active to False."""
        data = {
            "conditionId": "closed_market",
            "question": "Closed Question?",
            "active": True,
            "closed": True,
        }

        market = Market.from_api(data)

        assert market.is_active is False

    def test_from_api_inactive_market(self):
        """Test parsing inactive market sets is_active to False."""
        data = {
            "conditionId": "inactive_market",
            "question": "Inactive Question?",
            "active": False,
            "closed": False,
        }

        market = Market.from_api(data)

        assert market.is_active is False

    def test_from_api_handles_null_volume(self):
        """Test parsing handles null volume values."""
        data = {
            "conditionId": "test",
            "question": "Test?",
            "volume24hr": None,
            "volume": None,
            "liquidity": None,
            "active": True,
            "closed": False,
        }

        market = Market.from_api(data)

        assert market.volume_24h == 0.0
        assert market.total_volume == 0.0
        assert market.liquidity == 0.0

    def test_from_api_uses_id_as_fallback_condition_id(self):
        """Test that 'id' field is used as fallback for conditionId."""
        data = {
            "id": "fallback_id",
            "title": "Fallback Title",
            "active": True,
            "closed": False,
        }

        market = Market.from_api(data)

        assert market.condition_id == "fallback_id"
        assert market.question == "Fallback Title"

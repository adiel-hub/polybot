"""Tests for Gamma market data client.

Tests the Market dataclass parsing and GammaMarketClient functionality.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.polymarket.gamma_client import Market, GammaMarketClient


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


class TestGammaMarketClientLeaderboard:
    """Tests for GammaMarketClient leaderboard methods."""

    @pytest.fixture
    def client(self):
        """Create GammaMarketClient instance."""
        return GammaMarketClient()

    @pytest.fixture
    def mock_leaderboard_response(self):
        """Mock leaderboard API response."""
        return [
            {
                "rank": "1",
                "proxyWallet": "0x1234567890abcdef1234567890abcdef12345678",
                "userName": "TopTrader",
                "vol": 500000,
                "pnl": 15234.50,
                "profileImage": "https://example.com/avatar.jpg",
                "xUsername": "toptrader",
                "verifiedBadge": True,
            },
            {
                "rank": "2",
                "proxyWallet": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
                "userName": "ProTrader",
                "vol": 350000,
                "pnl": 8921.30,
                "profileImage": "",
                "xUsername": "",
                "verifiedBadge": False,
            },
        ]

    # Test get_top_traders
    @pytest.mark.asyncio
    async def test_get_top_traders_default_params(
        self, client, mock_leaderboard_response
    ):
        """Test get_top_traders with default parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_leaderboard_response

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_top_traders()

            assert len(result) == 2
            assert result[0]["address"] == "0x1234567890abcdef1234567890abcdef12345678"
            assert result[0]["name"] == "TopTrader"
            assert result[0]["pnl"] == 15234.50
            assert result[0]["volume"] == 500000.0
            assert result[0]["rank"] == 1
            assert result[0]["verified"] is True

            # Check API call
            mock_http_client.get.assert_called_once()
            call_args = mock_http_client.get.call_args
            assert "data-api.polymarket.com/v1/leaderboard" in call_args[0][0]
            assert call_args[1]["params"]["category"] == "OVERALL"
            assert call_args[1]["params"]["timePeriod"] == "WEEK"
            assert call_args[1]["params"]["orderBy"] == "PNL"
            assert call_args[1]["params"]["limit"] == 25
            assert call_args[1]["params"]["offset"] == 0

    @pytest.mark.asyncio
    async def test_get_top_traders_custom_params(self, client, mock_leaderboard_response):
        """Test get_top_traders with custom parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_leaderboard_response

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_top_traders(
                limit=50,
                offset=10,
                category="POLITICS",
                time_period="MONTH",
                order_by="VOL",
            )

            assert len(result) == 2
            call_args = mock_http_client.get.call_args
            assert call_args[1]["params"]["category"] == "POLITICS"
            assert call_args[1]["params"]["timePeriod"] == "MONTH"
            assert call_args[1]["params"]["orderBy"] == "VOL"
            assert call_args[1]["params"]["limit"] == 50
            assert call_args[1]["params"]["offset"] == 10

    @pytest.mark.asyncio
    async def test_get_top_traders_limits_max_limit(self, client):
        """Test get_top_traders caps limit at 50."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await client.get_top_traders(limit=100)

            call_args = mock_http_client.get.call_args
            assert call_args[1]["params"]["limit"] == 50  # Capped at 50

    @pytest.mark.asyncio
    async def test_get_top_traders_limits_max_offset(self, client):
        """Test get_top_traders caps offset at 1000."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await client.get_top_traders(offset=2000)

            call_args = mock_http_client.get.call_args
            assert call_args[1]["params"]["offset"] == 1000  # Capped at 1000

    @pytest.mark.asyncio
    async def test_get_top_traders_handles_non_200_status(self, client):
        """Test get_top_traders handles non-200 status code."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_top_traders()

            assert result == []

    @pytest.mark.asyncio
    async def test_get_top_traders_handles_exception(self, client):
        """Test get_top_traders handles exceptions."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(side_effect=Exception("Network error"))
            mock_get_client.return_value = mock_http_client

            result = await client.get_top_traders()

            assert result == []

    @pytest.mark.asyncio
    async def test_get_top_traders_parses_all_fields(
        self, client, mock_leaderboard_response
    ):
        """Test get_top_traders parses all fields correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_leaderboard_response

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_top_traders()

            trader = result[0]
            assert "address" in trader
            assert "name" in trader
            assert "pnl" in trader
            assert "volume" in trader
            assert "rank" in trader
            assert "profile_image" in trader
            assert "x_username" in trader
            assert "verified" in trader

    # Test get_trader_profile
    @pytest.mark.asyncio
    async def test_get_trader_profile_success(self, client):
        """Test get_trader_profile returns trader data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "rank": "5",
                "proxyWallet": "0x1234567890abcdef1234567890abcdef12345678",
                "userName": "SearchedTrader",
                "vol": 250000,
                "pnl": 5432.10,
                "profileImage": "https://example.com/pic.jpg",
                "xUsername": "searched",
                "verifiedBadge": True,
            }
        ]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_trader_profile(
                "0x1234567890abcdef1234567890abcdef12345678"
            )

            assert result is not None
            assert result["name"] == "SearchedTrader"
            assert result["pnl"] == 5432.10
            assert result["rank"] == 5

            # Check API was called with address
            call_args = mock_http_client.get.call_args
            assert (
                call_args[1]["params"]["user"]
                == "0x1234567890abcdef1234567890abcdef12345678"
            )

    @pytest.mark.asyncio
    async def test_get_trader_profile_normalizes_address(self, client):
        """Test get_trader_profile normalizes address to lowercase."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "rank": "5",
                "proxyWallet": "0x1234567890abcdef1234567890abcdef12345678",
                "userName": "Trader",
                "vol": 250000,
                "pnl": 5000,
            }
        ]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await client.get_trader_profile(
                "0X1234567890ABCDEF1234567890ABCDEF12345678"  # Uppercase
            )

            call_args = mock_http_client.get.call_args
            assert (
                call_args[1]["params"]["user"]
                == "0x1234567890abcdef1234567890abcdef12345678"  # Lowercase
            )

    @pytest.mark.asyncio
    async def test_get_trader_profile_not_found(self, client):
        """Test get_trader_profile returns None when not found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []  # Empty array

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_trader_profile("0xnotfound")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_trader_profile_handles_non_200_status(self, client):
        """Test get_trader_profile handles non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_trader_profile("0x1234")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_trader_profile_handles_exception(self, client):
        """Test get_trader_profile handles exceptions."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(side_effect=Exception("API error"))
            mock_get_client.return_value = mock_http_client

            result = await client.get_trader_profile("0x1234")

            assert result is None

"""Tests for leaderboard service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.leaderboard_service import LeaderboardService


class TestLeaderboardService:
    """Test LeaderboardService class."""

    @pytest.fixture
    def service(self):
        """Create LeaderboardService instance."""
        return LeaderboardService()

    @pytest.fixture
    def mock_traders(self):
        """Mock trader data from API."""
        return [
            {
                "address": "0x1234567890abcdef1234567890abcdef12345678",
                "name": "TopTrader",
                "pnl": 15234.50,
                "volume": 500000.0,
                "rank": 1,
                "profile_image": "https://example.com/avatar.jpg",
                "x_username": "toptrader",
                "verified": True,
            },
            {
                "address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
                "name": "ProTrader",
                "pnl": 8921.30,
                "volume": 350000.0,
                "rank": 2,
                "profile_image": "",
                "x_username": "",
                "verified": False,
            },
        ]

    # Test initialization
    def test_init_creates_gamma_client(self, service):
        """Test service initializes with GammaMarketClient."""
        assert service.gamma_client is not None

    def test_categories_list(self, service):
        """Test service has correct categories."""
        assert "OVERALL" in service.CATEGORIES
        assert "POLITICS" in service.CATEGORIES
        assert "SPORTS" in service.CATEGORIES
        assert "CRYPTO" in service.CATEGORIES
        assert len(service.CATEGORIES) == 10

    def test_time_periods_list(self, service):
        """Test service has correct time periods."""
        assert "DAY" in service.TIME_PERIODS
        assert "WEEK" in service.TIME_PERIODS
        assert "MONTH" in service.TIME_PERIODS
        assert "ALL" in service.TIME_PERIODS
        assert len(service.TIME_PERIODS) == 4

    def test_order_options_list(self, service):
        """Test service has correct order options."""
        assert "PNL" in service.ORDER_OPTIONS
        assert "VOL" in service.ORDER_OPTIONS
        assert len(service.ORDER_OPTIONS) == 2

    # Test get_top_traders
    @pytest.mark.asyncio
    async def test_get_top_traders_default_params(self, service, mock_traders):
        """Test get_top_traders with default parameters."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_traders)

        result = await service.get_top_traders()

        assert len(result) == 2
        assert result[0]["name"] == "TopTrader"
        assert result[0]["pnl"] == 15234.50
        service.gamma_client.get_top_traders.assert_called_once_with(
            limit=10,
            offset=0,
            category="OVERALL",
            time_period="WEEK",
            order_by="PNL",
        )

    @pytest.mark.asyncio
    async def test_get_top_traders_custom_params(self, service, mock_traders):
        """Test get_top_traders with custom parameters."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_traders)

        result = await service.get_top_traders(
            limit=25,
            offset=10,
            category="POLITICS",
            time_period="MONTH",
            order_by="VOL",
        )

        assert len(result) == 2
        service.gamma_client.get_top_traders.assert_called_once_with(
            limit=25,
            offset=10,
            category="POLITICS",
            time_period="MONTH",
            order_by="VOL",
        )

    @pytest.mark.asyncio
    async def test_get_top_traders_validates_category(self, service, mock_traders):
        """Test get_top_traders validates and corrects invalid category."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_traders)

        result = await service.get_top_traders(category="INVALID")

        # Should fall back to OVERALL
        service.gamma_client.get_top_traders.assert_called_once()
        call_args = service.gamma_client.get_top_traders.call_args
        assert call_args[1]["category"] == "OVERALL"

    @pytest.mark.asyncio
    async def test_get_top_traders_validates_time_period(self, service, mock_traders):
        """Test get_top_traders validates and corrects invalid time period."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_traders)

        result = await service.get_top_traders(time_period="INVALID")

        # Should fall back to WEEK
        call_args = service.gamma_client.get_top_traders.call_args
        assert call_args[1]["time_period"] == "WEEK"

    @pytest.mark.asyncio
    async def test_get_top_traders_validates_order_by(self, service, mock_traders):
        """Test get_top_traders validates and corrects invalid order_by."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_traders)

        result = await service.get_top_traders(order_by="INVALID")

        # Should fall back to PNL
        call_args = service.gamma_client.get_top_traders.call_args
        assert call_args[1]["order_by"] == "PNL"

    @pytest.mark.asyncio
    async def test_get_top_traders_handles_empty_result(self, service):
        """Test get_top_traders handles empty result."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=[])

        result = await service.get_top_traders()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_top_traders_handles_exception(self, service):
        """Test get_top_traders handles exceptions gracefully."""
        service.gamma_client.get_top_traders = AsyncMock(
            side_effect=Exception("API error")
        )

        result = await service.get_top_traders()

        assert result == []

    # Test get_trader_profile
    @pytest.mark.asyncio
    async def test_get_trader_profile_success(self, service):
        """Test get_trader_profile returns trader data."""
        mock_profile = {
            "address": "0x1234567890abcdef1234567890abcdef12345678",
            "name": "TopTrader",
            "pnl": 15234.50,
            "volume": 500000.0,
            "rank": 1,
            "profile_image": "https://example.com/avatar.jpg",
            "x_username": "toptrader",
            "verified": True,
        }
        service.gamma_client.get_trader_profile = AsyncMock(return_value=mock_profile)

        result = await service.get_trader_profile(
            "0x1234567890abcdef1234567890abcdef12345678"
        )

        assert result is not None
        assert result["name"] == "TopTrader"
        assert result["pnl"] == 15234.50
        assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_get_trader_profile_not_found(self, service):
        """Test get_trader_profile handles not found."""
        service.gamma_client.get_trader_profile = AsyncMock(return_value=None)

        result = await service.get_trader_profile("0xnotfound")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_trader_profile_handles_exception(self, service):
        """Test get_trader_profile handles exceptions."""
        service.gamma_client.get_trader_profile = AsyncMock(
            side_effect=Exception("API error")
        )

        result = await service.get_trader_profile("0x1234")

        assert result is None

    # Test search_traders_by_name
    @pytest.mark.asyncio
    async def test_search_traders_by_name_exact_match(self, service, mock_traders):
        """Test search_traders_by_name finds exact match."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_traders)

        result = await service.search_traders_by_name("TopTrader")

        assert len(result) == 1
        assert result[0]["name"] == "TopTrader"

    @pytest.mark.asyncio
    async def test_search_traders_by_name_case_insensitive(self, service, mock_traders):
        """Test search_traders_by_name is case insensitive."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_traders)

        result = await service.search_traders_by_name("toptrader")

        assert len(result) == 1
        assert result[0]["name"] == "TopTrader"

    @pytest.mark.asyncio
    async def test_search_traders_by_name_partial_match(self, service, mock_traders):
        """Test search_traders_by_name finds partial matches."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_traders)

        result = await service.search_traders_by_name("Trader")

        assert len(result) == 2  # Both have "Trader" in name

    @pytest.mark.asyncio
    async def test_search_traders_by_name_x_username(self, service, mock_traders):
        """Test search_traders_by_name searches x_username."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_traders)

        result = await service.search_traders_by_name("toptrader")

        assert len(result) == 1
        assert result[0]["x_username"] == "toptrader"

    @pytest.mark.asyncio
    async def test_search_traders_by_name_no_match(self, service, mock_traders):
        """Test search_traders_by_name returns empty for no match."""
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_traders)

        result = await service.search_traders_by_name("NonExistent")

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_search_traders_by_name_respects_limit(self, service):
        """Test search_traders_by_name respects limit parameter."""
        mock_many_traders = [
            {"name": f"Trader{i}", "x_username": "", "pnl": 1000, "volume": 10000}
            for i in range(20)
        ]
        service.gamma_client.get_top_traders = AsyncMock(return_value=mock_many_traders)

        result = await service.search_traders_by_name("Trader", limit=5)

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_search_traders_by_name_handles_exception(self, service):
        """Test search_traders_by_name handles exceptions."""
        service.gamma_client.get_top_traders = AsyncMock(
            side_effect=Exception("API error")
        )

        result = await service.search_traders_by_name("Test")

        assert result == []

    # Test helper methods
    def test_get_available_categories(self, service):
        """Test get_available_categories returns formatted list."""
        categories = service.get_available_categories()

        assert len(categories) == 10
        assert all("id" in cat and "name" in cat for cat in categories)
        assert any(cat["id"] == "OVERALL" for cat in categories)
        assert any(cat["id"] == "POLITICS" for cat in categories)

    def test_get_available_time_periods(self, service):
        """Test get_available_time_periods returns formatted list."""
        periods = service.get_available_time_periods()

        assert len(periods) == 4
        assert {"DAY": "24 Hours"} in periods
        assert {"WEEK": "7 Days"} in periods
        assert {"MONTH": "30 Days"} in periods
        assert {"ALL": "All Time"} in periods

    # Test close method
    @pytest.mark.asyncio
    async def test_close_calls_gamma_client_close(self, service):
        """Test close method calls gamma_client.close()."""
        service.gamma_client.close = AsyncMock()

        await service.close()

        service.gamma_client.close.assert_called_once()

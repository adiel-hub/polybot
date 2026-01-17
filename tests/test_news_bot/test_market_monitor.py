"""Tests for the market monitor service."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.polymarket.gamma_client import Market
from news_bot.services.market_monitor import MarketMonitorService


@pytest.fixture
def sample_markets():
    """Create sample market objects for testing."""
    return [
        Market(
            condition_id="market1",
            question="Will Bitcoin reach $100k?",
            description="Bitcoin price prediction",
            category="crypto",
            image_url="https://example.com/btc.png",
            yes_token_id="token1_yes",
            no_token_id="token1_no",
            yes_price=0.65,
            no_price=0.35,
            volume_24h=50000,
            total_volume=500000,
            liquidity=100000,
            end_date="2025-12-31",
            is_active=True,
            slug="bitcoin-100k",
            event_id="event1",
        ),
        Market(
            condition_id="market2",
            question="Will ETH reach $5k?",
            description="Ethereum price prediction",
            category="crypto",
            image_url="https://example.com/eth.png",
            yes_token_id="token2_yes",
            no_token_id="token2_no",
            yes_price=0.45,
            no_price=0.55,
            volume_24h=30000,
            total_volume=300000,
            liquidity=80000,
            end_date="2025-12-31",
            is_active=True,
            slug="eth-5k",
            event_id="event2",
        ),
        Market(
            condition_id="market3",
            question="Low volume market",
            description="Test low volume",
            category="test",
            image_url=None,
            yes_token_id="token3_yes",
            no_token_id="token3_no",
            yes_price=0.50,
            no_price=0.50,
            volume_24h=100,
            total_volume=500,  # Below threshold
            liquidity=200,  # Below threshold
            end_date="2025-12-31",
            is_active=True,
            slug="low-volume",
            event_id="event3",
        ),
    ]


@pytest.fixture
def mock_gamma_client(sample_markets):
    """Create a mock Gamma client."""
    client = MagicMock()
    client.get_new_markets = AsyncMock(return_value=sample_markets)
    client.get_trending_markets = AsyncMock(return_value=sample_markets)
    return client


@pytest.fixture
def mock_posted_repo():
    """Create a mock posted market repository."""
    repo = MagicMock()
    repo.exists = AsyncMock(return_value=False)
    return repo


@pytest.mark.asyncio
async def test_get_unposted_markets_filters_by_volume(
    mock_gamma_client, mock_posted_repo, sample_markets
):
    """Test that markets below volume threshold are filtered out."""
    monitor = MarketMonitorService(
        gamma_client=mock_gamma_client,
        posted_repo=mock_posted_repo,
        min_volume=1000,
        min_liquidity=500,
    )

    markets = await monitor.get_unposted_markets(limit=50)

    # market3 should be filtered out (volume=500, liquidity=200)
    assert len(markets) == 2
    assert all(m.total_volume >= 1000 for m in markets)
    assert all(m.liquidity >= 500 for m in markets)


@pytest.mark.asyncio
async def test_get_unposted_markets_filters_already_posted(
    mock_gamma_client, mock_posted_repo, sample_markets
):
    """Test that already posted markets are filtered out."""
    # Mark market1 as already posted
    mock_posted_repo.exists = AsyncMock(
        side_effect=lambda cid: cid == "market1"
    )

    monitor = MarketMonitorService(
        gamma_client=mock_gamma_client,
        posted_repo=mock_posted_repo,
        min_volume=1000,
        min_liquidity=500,
    )

    markets = await monitor.get_unposted_markets(limit=50)

    # market1 should be filtered out (already posted)
    # market3 should be filtered out (low volume)
    assert len(markets) == 1
    assert markets[0].condition_id == "market2"


@pytest.mark.asyncio
async def test_get_unposted_markets_handles_empty_response(
    mock_posted_repo,
):
    """Test handling of empty API response."""
    mock_gamma_client = MagicMock()
    mock_gamma_client.get_new_markets = AsyncMock(return_value=[])

    monitor = MarketMonitorService(
        gamma_client=mock_gamma_client,
        posted_repo=mock_posted_repo,
        min_volume=1000,
        min_liquidity=500,
    )

    markets = await monitor.get_unposted_markets(limit=50)

    assert len(markets) == 0


@pytest.mark.asyncio
async def test_get_unposted_markets_handles_api_error(
    mock_posted_repo,
):
    """Test handling of API errors."""
    mock_gamma_client = MagicMock()
    mock_gamma_client.get_new_markets = AsyncMock(
        side_effect=Exception("API Error")
    )

    monitor = MarketMonitorService(
        gamma_client=mock_gamma_client,
        posted_repo=mock_posted_repo,
        min_volume=1000,
        min_liquidity=500,
    )

    markets = await monitor.get_unposted_markets(limit=50)

    # Should return empty list on error, not raise exception
    assert len(markets) == 0

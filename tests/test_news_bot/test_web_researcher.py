"""Tests for the web researcher service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.polymarket.gamma_client import Market
from news_bot.services.web_researcher import WebResearcherService, ResearchResult


@pytest.fixture
def sample_market():
    """Create a sample market for testing."""
    return Market(
        condition_id="test_market",
        question="Will Bitcoin reach $100,000 by end of 2025?",
        description="A prediction market on Bitcoin's price",
        category="crypto",
        image_url=None,
        yes_token_id="token_yes",
        no_token_id="token_no",
        yes_price=0.65,
        no_price=0.35,
        volume_24h=50000,
        total_volume=500000,
        liquidity=100000,
        end_date="2025-12-31",
        is_active=True,
        slug="bitcoin-100k",
        event_id="event1",
    )


def test_build_search_query_removes_question_words(sample_market):
    """Test that betting-specific words are removed from query."""
    researcher = WebResearcherService(tavily_api_key="test_key")

    query = researcher._build_search_query(sample_market)

    # Should remove "Will" and question mark
    assert "Will" not in query or "will" not in query.lower().split()[0]
    assert not query.endswith("?")


def test_build_search_query_includes_category(sample_market):
    """Test that category is included in query."""
    researcher = WebResearcherService(tavily_api_key="test_key")

    query = researcher._build_search_query(sample_market)

    assert "crypto" in query.lower()
    assert "news" in query.lower()


def test_build_search_query_handles_dates():
    """Test that date patterns are handled."""
    researcher = WebResearcherService(tavily_api_key="test_key")

    market = Market(
        condition_id="test",
        question="Will Trump win by November 5, 2024?",
        description="",
        category="politics",
        image_url=None,
        yes_token_id="yes",
        no_token_id="no",
        yes_price=0.5,
        no_price=0.5,
        volume_24h=1000,
        total_volume=10000,
        liquidity=5000,
        end_date="2024-11-05",
        is_active=True,
    )

    query = researcher._build_search_query(market)

    # Date pattern should be removed or simplified
    assert "Trump" in query
    assert "politics" in query.lower()


@pytest.mark.asyncio
async def test_research_topic_without_api_key():
    """Test behavior when no API key is configured."""
    researcher = WebResearcherService(tavily_api_key="")

    market = Market(
        condition_id="test",
        question="Test question?",
        description="",
        category="test",
        image_url=None,
        yes_token_id="yes",
        no_token_id="no",
        yes_price=0.5,
        no_price=0.5,
        volume_24h=1000,
        total_volume=10000,
        liquidity=5000,
        end_date="2025-01-01",
        is_active=True,
    )

    result = await researcher.research_topic(market)

    # Should return empty result without error
    assert isinstance(result, ResearchResult)
    assert result.query == ""
    assert result.summary == ""
    assert len(result.sources) == 0


@pytest.mark.asyncio
async def test_research_topic_handles_api_error(sample_market):
    """Test handling of API errors."""
    researcher = WebResearcherService(tavily_api_key="test_key")

    # Mock the HTTP client to raise an error
    with patch.object(researcher, "_search_tavily", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = Exception("API Error")

        result = await researcher.research_topic(sample_market)

        # Should return result with empty data, not raise exception
        assert isinstance(result, ResearchResult)
        assert result.summary == ""
        assert len(result.sources) == 0


@pytest.mark.asyncio
async def test_research_topic_parses_response(sample_market):
    """Test parsing of Tavily API response."""
    researcher = WebResearcherService(tavily_api_key="test_key")

    mock_response = {
        "answer": "Bitcoin shows strong momentum heading into 2025.",
        "results": [
            {
                "title": "Bitcoin Analysis",
                "url": "https://example.com/btc",
                "content": "Bitcoin has been rallying strongly...",
            },
            {
                "title": "Crypto Market Update",
                "url": "https://example.com/crypto",
                "content": "The crypto market continues to grow...",
            },
        ],
    }

    with patch.object(researcher, "_search_tavily", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_response

        result = await researcher.research_topic(sample_market)

        assert result.summary == "Bitcoin shows strong momentum heading into 2025."
        assert len(result.sources) == 2
        assert result.sources[0].title == "Bitcoin Analysis"
        assert result.sources[0].url == "https://example.com/btc"

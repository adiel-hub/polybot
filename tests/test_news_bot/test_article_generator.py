"""Tests for the article generator service."""

import pytest
from unittest.mock import MagicMock, patch

from core.polymarket.gamma_client import Market
from news_bot.services.article_generator import ArticleGeneratorService, GeneratedArticle
from news_bot.services.web_researcher import ResearchResult, ResearchSource


@pytest.fixture
def sample_market():
    """Create a sample market for testing."""
    return Market(
        condition_id="test_market",
        question="Will Bitcoin reach $100,000 by end of 2025?",
        description="A prediction market on Bitcoin's price reaching $100,000",
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
def sample_research():
    """Create sample research results for testing."""
    return ResearchResult(
        query="Bitcoin price prediction 2025",
        summary="Bitcoin has shown strong momentum in 2024-2025, with analysts predicting potential new all-time highs.",
        sources=[
            ResearchSource(
                title="Bitcoin Price Analysis",
                url="https://example.com/btc-analysis",
                snippet="Bitcoin is trading near $80,000...",
            ),
            ResearchSource(
                title="Crypto Market Outlook",
                url="https://example.com/crypto-outlook",
                snippet="The crypto market continues to show strength...",
            ),
        ],
        context_snippets=[
            "Bitcoin institutional adoption continues to grow",
            "ETF inflows have been record-breaking",
        ],
    )


def test_build_prompt_includes_market_data(sample_market, sample_research):
    """Test that the prompt includes all market data."""
    generator = ArticleGeneratorService(
        api_key="test_key",
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
    )

    prompt = generator._build_prompt(sample_market, sample_research)

    assert sample_market.question in prompt
    assert "65.0%" in prompt  # YES price
    assert "35.0%" in prompt  # NO price
    assert "$500,000" in prompt  # Total volume
    assert "crypto" in prompt  # Category


def test_build_prompt_includes_research(sample_market, sample_research):
    """Test that the prompt includes research context."""
    generator = ArticleGeneratorService(
        api_key="test_key",
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
    )

    prompt = generator._build_prompt(sample_market, sample_research)

    assert sample_research.summary in prompt
    assert "Bitcoin Price Analysis" in prompt
    assert "https://example.com/btc-analysis" in prompt


def test_parse_article_extracts_headline():
    """Test headline extraction from generated content."""
    generator = ArticleGeneratorService(
        api_key="test_key",
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
    )

    content = """HEADLINE: Bitcoin Eyes $100K Amid Market Optimism

Bitcoin continues its strong rally as institutional investors pile in.
The cryptocurrency market shows no signs of slowing down."""

    title, body = generator._parse_article(content)

    assert title == "Bitcoin Eyes $100K Amid Market Optimism"
    assert "Bitcoin continues its strong rally" in body
    assert "HEADLINE:" not in body


def test_parse_article_handles_markdown_headline():
    """Test handling of markdown-formatted headlines."""
    generator = ArticleGeneratorService(
        api_key="test_key",
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
    )

    content = """**HEADLINE: Bitcoin Surges Past $90K**

The cryptocurrency has reached new heights."""

    title, body = generator._parse_article(content)

    assert "Bitcoin Surges Past $90K" in title
    assert "cryptocurrency has reached new heights" in body


def test_parse_article_handles_missing_headline():
    """Test handling when no headline marker is found."""
    generator = ArticleGeneratorService(
        api_key="test_key",
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
    )

    content = """Bitcoin continues to surge higher.

The market shows strong momentum."""

    title, body = generator._parse_article(content)

    # First line should be used as title
    assert title == "Bitcoin continues to surge higher."
    assert "market shows strong momentum" in body


def test_generate_fallback_article(sample_market):
    """Test fallback article generation."""
    generator = ArticleGeneratorService(
        api_key="test_key",
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
    )

    fallback = generator._generate_fallback_article(sample_market)

    assert sample_market.question in fallback
    assert "65%" in fallback  # YES price
    assert "35%" in fallback  # NO price
    assert "$500,000" in fallback  # Volume
    assert "#crypto" in fallback  # Hashtag from category

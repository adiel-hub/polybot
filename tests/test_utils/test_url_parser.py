"""Tests for URL parser utilities."""

import pytest

from utils.url_parser import (
    is_polymarket_url,
    extract_url_from_text,
    extract_slug_from_url,
)


class TestIsPolymarketUrl:
    """Test is_polymarket_url function."""

    def test_valid_event_url_with_https(self):
        """Test valid event URL with https protocol."""
        assert is_polymarket_url("https://polymarket.com/event/bitcoin-100k-2025")

    def test_valid_market_url_with_https(self):
        """Test valid market URL with https protocol."""
        assert is_polymarket_url("https://polymarket.com/market/fed-decision-october")

    def test_valid_url_with_http(self):
        """Test valid URL with http protocol."""
        assert is_polymarket_url("http://polymarket.com/event/test-market")

    def test_valid_url_without_protocol(self):
        """Test valid URL without protocol."""
        assert is_polymarket_url("polymarket.com/event/bitcoin-prediction")

    def test_valid_url_with_www(self):
        """Test valid URL with www subdomain."""
        assert is_polymarket_url("https://www.polymarket.com/event/test-event")

    def test_valid_url_with_query_params(self):
        """Test valid URL with query parameters."""
        assert is_polymarket_url("https://polymarket.com/event/test?tid=123&ref=abc")

    def test_url_embedded_in_text(self):
        """Test URL embedded in surrounding text."""
        assert is_polymarket_url("Check out this market: https://polymarket.com/event/cool-event")

    def test_url_with_hyphens_in_slug(self):
        """Test URL with multiple hyphens in slug."""
        assert is_polymarket_url("https://polymarket.com/event/will-btc-reach-100k-by-2025")

    def test_url_with_numbers_in_slug(self):
        """Test URL with numbers in slug."""
        assert is_polymarket_url("https://polymarket.com/market/2024-election-results")

    def test_invalid_domain(self):
        """Test URL with wrong domain."""
        assert not is_polymarket_url("https://example.com/event/test")

    def test_invalid_path_missing_event_or_market(self):
        """Test URL without /event/ or /market/ path."""
        assert not is_polymarket_url("https://polymarket.com/about")

    def test_empty_string(self):
        """Test empty string."""
        assert not is_polymarket_url("")

    def test_none_input(self):
        """Test None input doesn't crash."""
        assert not is_polymarket_url(None)

    def test_whitespace_only(self):
        """Test whitespace-only string."""
        assert not is_polymarket_url("   ")

    def test_case_insensitive_domain(self):
        """Test domain matching is case-insensitive."""
        assert is_polymarket_url("https://POLYMARKET.COM/event/test")

    def test_url_with_trailing_slash(self):
        """Test URL with trailing slash."""
        assert is_polymarket_url("https://polymarket.com/event/test-market/")


class TestExtractUrlFromText:
    """Test extract_url_from_text function."""

    def test_extract_url_with_https(self):
        """Test extracting URL with https protocol."""
        text = "Check this out: https://polymarket.com/event/bitcoin-100k"
        result = extract_url_from_text(text)
        assert result == "https://polymarket.com/event/bitcoin-100k"

    def test_extract_url_without_protocol(self):
        """Test extracting URL without protocol."""
        text = "Visit polymarket.com/market/test-market for details"
        result = extract_url_from_text(text)
        assert result == "polymarket.com/market/test-market"

    def test_extract_first_url_when_multiple(self):
        """Test only first URL is extracted when multiple present."""
        text = "https://polymarket.com/event/first and https://polymarket.com/event/second"
        result = extract_url_from_text(text)
        assert result == "https://polymarket.com/event/first"

    def test_extract_url_with_query_params(self):
        """Test URL with query parameters is extracted correctly."""
        text = "https://polymarket.com/event/test?tid=123"
        result = extract_url_from_text(text)
        # Should extract just the base URL without query params
        assert "polymarket.com/event/test" in result

    def test_extract_url_with_www(self):
        """Test URL with www subdomain."""
        text = "https://www.polymarket.com/market/crypto-prediction"
        result = extract_url_from_text(text)
        assert result == "https://www.polymarket.com/market/crypto-prediction"

    def test_no_url_in_text(self):
        """Test returns None when no URL present."""
        text = "This is just some random text without URLs"
        result = extract_url_from_text(text)
        assert result is None

    def test_empty_string(self):
        """Test empty string returns None."""
        assert extract_url_from_text("") is None

    def test_none_input(self):
        """Test None input returns None."""
        assert extract_url_from_text(None) is None

    def test_whitespace_trimmed(self):
        """Test whitespace is properly handled."""
        text = "  https://polymarket.com/event/test  "
        result = extract_url_from_text(text)
        assert result == "https://polymarket.com/event/test"

    def test_url_only(self):
        """Test extracting URL when it's the only content."""
        url = "https://polymarket.com/event/solo-url"
        result = extract_url_from_text(url)
        assert result == url


class TestExtractSlugFromUrl:
    """Test extract_slug_from_url function."""

    def test_extract_slug_from_event_url(self):
        """Test extracting slug from /event/ URL."""
        url = "https://polymarket.com/event/bitcoin-100k-2025"
        result = extract_slug_from_url(url)
        assert result == "bitcoin-100k-2025"

    def test_extract_slug_from_market_url(self):
        """Test extracting slug from /market/ URL."""
        url = "https://polymarket.com/market/fed-decision-october"
        result = extract_slug_from_url(url)
        assert result == "fed-decision-october"

    def test_extract_slug_with_query_params(self):
        """Test slug extraction ignores query parameters."""
        url = "https://polymarket.com/event/test-market?tid=123&ref=abc"
        result = extract_slug_from_url(url)
        assert result == "test-market"

    def test_extract_slug_without_protocol(self):
        """Test slug extraction from URL without protocol."""
        url = "polymarket.com/event/no-protocol-slug"
        result = extract_slug_from_url(url)
        assert result == "no-protocol-slug"

    def test_extract_slug_with_www(self):
        """Test slug extraction from URL with www."""
        url = "https://www.polymarket.com/market/www-test"
        result = extract_slug_from_url(url)
        assert result == "www-test"

    def test_extract_slug_with_http(self):
        """Test slug extraction from http URL."""
        url = "http://polymarket.com/event/http-test"
        result = extract_slug_from_url(url)
        assert result == "http-test"

    def test_extract_slug_with_trailing_slash(self):
        """Test slug extraction handles trailing slash."""
        url = "https://polymarket.com/event/trailing-slash/"
        result = extract_slug_from_url(url)
        assert result == "trailing-slash"

    def test_slug_with_numbers(self):
        """Test slug containing numbers."""
        url = "https://polymarket.com/event/2024-election-results"
        result = extract_slug_from_url(url)
        assert result == "2024-election-results"

    def test_slug_with_underscores(self):
        """Test slug containing underscores."""
        url = "https://polymarket.com/event/test_market_slug"
        result = extract_slug_from_url(url)
        assert result == "test_market_slug"

    def test_invalid_domain(self):
        """Test returns None for non-Polymarket domain."""
        url = "https://example.com/event/test-slug"
        result = extract_slug_from_url(url)
        assert result is None

    def test_invalid_path(self):
        """Test returns None for invalid path."""
        url = "https://polymarket.com/about/test-slug"
        result = extract_slug_from_url(url)
        assert result is None

    def test_empty_string(self):
        """Test empty string returns None."""
        assert extract_slug_from_url("") is None

    def test_none_input(self):
        """Test None input returns None."""
        assert extract_slug_from_url(None) is None

    def test_whitespace_trimmed(self):
        """Test whitespace is trimmed."""
        url = "  https://polymarket.com/event/trimmed-slug  "
        result = extract_slug_from_url(url)
        assert result == "trimmed-slug"

    def test_case_insensitive_domain(self):
        """Test domain matching is case-insensitive."""
        url = "https://POLYMARKET.COM/event/case-test"
        result = extract_slug_from_url(url)
        assert result == "case-test"

    def test_case_insensitive_path(self):
        """Test path matching is case-insensitive."""
        url = "https://polymarket.com/EVENT/caps-path"
        result = extract_slug_from_url(url)
        assert result == "caps-path"

    def test_malformed_url_missing_slug(self):
        """Test malformed URL with missing slug."""
        url = "https://polymarket.com/event/"
        result = extract_slug_from_url(url)
        assert result is None

    def test_very_long_slug(self):
        """Test handling of very long slugs."""
        url = "https://polymarket.com/event/this-is-a-very-long-slug-with-many-words-and-hyphens-2025"
        result = extract_slug_from_url(url)
        assert result == "this-is-a-very-long-slug-with-many-words-and-hyphens-2025"

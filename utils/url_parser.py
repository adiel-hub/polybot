"""URL parsing utilities for Polymarket links."""

import re
from typing import Optional


def is_polymarket_url(text: str) -> bool:
    """
    Check if text contains a Polymarket URL.

    Args:
        text: Input string to check

    Returns:
        True if text contains a valid Polymarket URL

    Examples:
        >>> is_polymarket_url("https://polymarket.com/event/bitcoin-100k")
        True
        >>> is_polymarket_url("Check this: polymarket.com/market/test")
        True
        >>> is_polymarket_url("https://example.com")
        False
    """
    if not text:
        return False

    # Pattern matches polymarket.com URLs with /event/ or /market/ paths
    pattern = r"(?:https?://)?(?:www\.)?polymarket\.com/(?:event|market)/[\w-]+"
    return bool(re.search(pattern, text.strip(), re.IGNORECASE))


def extract_url_from_text(text: str) -> Optional[str]:
    """
    Extract the first Polymarket URL from text.

    Args:
        text: Input string potentially containing a URL

    Returns:
        First valid Polymarket URL found, or None

    Examples:
        >>> extract_url_from_text("Check https://polymarket.com/event/test")
        'https://polymarket.com/event/test'
        >>> extract_url_from_text("polymarket.com/market/bitcoin")
        'polymarket.com/market/bitcoin'
    """
    if not text:
        return None

    pattern = r"((?:https?://)?(?:www\.)?polymarket\.com/(?:event|market)/[\w-]+)"
    match = re.search(pattern, text.strip(), re.IGNORECASE)

    return match.group(1) if match else None


def extract_slug_from_url(url: str) -> Optional[str]:
    """
    Extract the market slug from a Polymarket URL.

    Args:
        url: Polymarket URL (with or without protocol)

    Returns:
        Market slug (kebab-case identifier) or None if invalid

    Examples:
        >>> extract_slug_from_url("https://polymarket.com/event/bitcoin-100k-2025")
        'bitcoin-100k-2025'
        >>> extract_slug_from_url("polymarket.com/market/fed-decision?tid=123")
        'fed-decision'
        >>> extract_slug_from_url("https://example.com/event/test")
        None
    """
    if not url:
        return None

    # Clean up the URL
    url = url.strip()

    # Must be a polymarket.com URL
    if not re.search(r"(?:www\.)?polymarket\.com", url, re.IGNORECASE):
        return None

    # Extract slug from /event/{slug} or /market/{slug}
    # Slug is everything after /event/ or /market/ until query params or end
    pattern = r"polymarket\.com/(?:event|market)/([\w-]+)"
    match = re.search(pattern, url, re.IGNORECASE)

    if not match:
        return None

    slug = match.group(1)

    # Validate slug format (alphanumeric + hyphens only)
    if not re.match(r"^[\w-]+$", slug):
        return None

    return slug

"""Slug sanitization utility for Polymarket URLs."""
import re


def sanitize_slug(slug: str) -> str:
    """
    Remove all whitespace and control characters from a Polymarket slug.

    Args:
        slug: Raw slug from API (may contain newlines, tabs, etc.)

    Returns:
        Clean slug safe for URL construction, or empty string if invalid

    Examples:
        >>> sanitize_slug("trump-wins-2024")
        'trump-wins-2024'
        >>> sanitize_slug("market\\nwith\\nnewlines")
        'marketwithnewlines'
        >>> sanitize_slug("  spaced-slug  ")
        'spaced-slug'
        >>> sanitize_slug("slug-123-456")  # Removes trailing numbers
        'slug'
        >>> sanitize_slug("")
        ''
    """
    if not slug:
        return ""

    # Normalize to string and strip outer whitespace
    clean = str(slug).strip()

    # Remove ALL whitespace using join/split (most reliable method)
    # This handles spaces, tabs, newlines, carriage returns, etc.
    clean = ''.join(clean.split())

    # Remove any remaining control characters as backup
    # Only keep printable characters that are not whitespace
    clean = ''.join(c for c in clean if c.isprintable() and not c.isspace())

    # Remove trailing numeric patterns (token IDs like -1234-5678)
    clean = re.sub(r'(-\d+)+$', '', clean)

    # Validate result contains only alphanumeric, hyphens, underscores
    # Return empty string if validation fails
    if not clean or not all(c.isalnum() or c in '-_' for c in clean):
        return ""

    return clean

"""Polymarket web scraping utilities for direct market data extraction."""

import logging
import re
from typing import Optional, Dict, Any
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


async def scrape_market_from_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Scrape market data directly from Polymarket webpage.

    This is a fallback when the Gamma API doesn't have the market indexed.
    Extracts condition_id and other metadata from the page HTML.

    Args:
        url: Full Polymarket URL (e.g., https://polymarket.com/event/...)

    Returns:
        Dict with market data including condition_id, or None if failed

    Example:
        >>> data = await scrape_market_from_url("https://polymarket.com/event/test")
        >>> print(data["condition_id"])
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            html = response.text

            # Extract condition ID from various possible locations
            condition_id = None

            # Method 1: Look for condition_id in meta tags
            soup = BeautifulSoup(html, "html.parser")
            meta_tags = soup.find_all("meta", attrs={"property": re.compile(".*condition.*", re.I)})
            for tag in meta_tags:
                content = tag.get("content", "")
                if content and content.startswith("0x"):
                    condition_id = content
                    break

            # Method 2: Look for condition_id in script tags (Next.js data)
            if not condition_id:
                scripts = soup.find_all("script", attrs={"id": "__NEXT_DATA__"})
                for script in scripts:
                    text = script.string or ""
                    # Look for conditionId pattern
                    match = re.search(r'"conditionId"\s*:\s*"(0x[a-fA-F0-9]{64})"', text)
                    if match:
                        condition_id = match.group(1)
                        break

            # Method 3: Look for condition_id in any script tag
            if not condition_id:
                scripts = soup.find_all("script")
                for script in scripts:
                    text = script.string or ""
                    if "conditionId" in text or "condition_id" in text:
                        # Try to find hex string pattern
                        match = re.search(r'(0x[a-fA-F0-9]{64})', text)
                        if match:
                            condition_id = match.group(1)
                            break

            if not condition_id:
                logger.warning(f"Could not extract condition_id from {url}")
                return None

            # Try to extract other useful data
            market_data = {
                "condition_id": condition_id,
                "url": url,
            }

            # Try to extract question from title or og:title
            title_tag = soup.find("title")
            if title_tag:
                market_data["question"] = title_tag.string.strip()
            else:
                og_title = soup.find("meta", attrs={"property": "og:title"})
                if og_title:
                    market_data["question"] = og_title.get("content", "").strip()

            logger.info(f"Successfully scraped market data from {url}")
            logger.debug(f"Condition ID: {condition_id}")

            return market_data

    except Exception as e:
        logger.error(f"Failed to scrape market from {url}: {e}")
        return None

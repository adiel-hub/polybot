"""Market service for browsing and discovery."""

import logging
from typing import Optional, List, Dict, Any

from core.polymarket import GammaMarketClient, Market
from config.constants import MARKET_CATEGORIES

logger = logging.getLogger(__name__)


class MarketService:
    """Service for market data operations."""

    def __init__(self):
        self.gamma_client = GammaMarketClient()

        # Category tag mappings (would need to be fetched from API)
        self._category_tags: Dict[str, int] = {}

    async def get_markets_by_category(
        self,
        category: str,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Market]:
        """
        Get markets by category.

        Args:
            category: Category name (volume, trending, new, etc.)
            limit: Number of results
            offset: Pagination offset

        Returns:
            List of markets
        """
        if category == "volume":
            return await self.gamma_client.get_events(
                limit=limit,
                offset=offset,
                order="volume",
            )
        elif category == "trending":
            return await self.gamma_client.get_trending_markets(limit=limit)
        elif category == "new":
            return await self.gamma_client.get_new_markets(limit=limit)
        else:
            # Try to get by tag
            tag_id = self._category_tags.get(category)
            if tag_id:
                return await self.gamma_client.get_markets_by_tag(
                    tag_id=tag_id,
                    limit=limit,
                )
            else:
                # Default to trending
                return await self.gamma_client.get_trending_markets(limit=limit)

    async def search_markets(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Market]:
        """Search markets by keyword."""
        return await self.gamma_client.search_markets(query, limit=limit)

    async def get_market_detail(self, condition_id: str) -> Optional[Market]:
        """Get detailed market information."""
        return await self.gamma_client.get_market_by_condition_id(condition_id)

    async def get_market_by_slug(self, slug: str) -> Optional[Market]:
        """Get market by URL slug."""
        return await self.gamma_client.get_market_by_slug(slug)

    async def get_token_price(self, token_id: str) -> Optional[float]:
        """Get current price for a token."""
        return await self.gamma_client.get_market_price(token_id)

    async def get_categories(self) -> List[Dict[str, str]]:
        """Get available categories for browsing."""
        return [
            {"id": key, "name": name}
            for key, name in MARKET_CATEGORIES.items()
        ]

    async def initialize_categories(self) -> None:
        """Initialize category tag mappings from API."""
        try:
            tags = await self.gamma_client.get_tags()

            # Map common categories to tag IDs
            category_keywords = {
                "politics": ["politics", "election", "government"],
                "sports": ["sports", "nfl", "nba", "soccer"],
                "crypto": ["crypto", "bitcoin", "ethereum", "defi"],
                "entertainment": ["entertainment", "movies", "tv"],
                "science": ["science", "technology", "ai"],
            }

            for tag in tags:
                tag_label = tag.get("label", "").lower()
                tag_id = tag.get("id")

                for category, keywords in category_keywords.items():
                    if any(kw in tag_label for kw in keywords):
                        if category not in self._category_tags:
                            self._category_tags[category] = tag_id
                        break

            logger.info(f"Initialized {len(self._category_tags)} category mappings")

        except Exception as e:
            logger.error(f"Failed to initialize categories: {e}")

    async def close(self):
        """Close HTTP client."""
        await self.gamma_client.close()

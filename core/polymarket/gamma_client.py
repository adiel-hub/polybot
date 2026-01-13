"""Polymarket Gamma API client for market data."""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import httpx

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class Market:
    """Market data model."""
    condition_id: str
    question: str
    description: Optional[str]
    category: Optional[str]
    image_url: Optional[str]
    yes_token_id: str
    no_token_id: str
    yes_price: float
    no_price: float
    volume_24h: float
    total_volume: float
    liquidity: float
    end_date: Optional[str]
    is_active: bool

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Market":
        """Create Market from API response."""
        import json

        # Handle both event and market format
        markets = data.get("markets", [data])
        market = markets[0] if markets else data

        # Get token IDs - may be string or list
        tokens = market.get("clobTokenIds", [])
        if isinstance(tokens, str):
            try:
                tokens = json.loads(tokens)
            except (json.JSONDecodeError, TypeError):
                tokens = []
        yes_token_id = tokens[0] if len(tokens) > 0 else ""
        no_token_id = tokens[1] if len(tokens) > 1 else ""

        # Get prices from outcomes - may be string or list
        outcomes = market.get("outcomePrices", [])
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except (json.JSONDecodeError, TypeError):
                outcomes = []

        yes_price = float(outcomes[0]) if len(outcomes) > 0 else 0.5
        no_price = float(outcomes[1]) if len(outcomes) > 1 else 0.5

        return cls(
            condition_id=market.get("conditionId", data.get("id", "")),
            question=market.get("question", data.get("title", "")),
            description=market.get("description", ""),
            category=data.get("category", ""),
            image_url=data.get("image", market.get("image", "")),
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            yes_price=yes_price,
            no_price=no_price,
            volume_24h=float(market.get("volume24hr", 0) or 0),
            total_volume=float(market.get("volume", data.get("volume", 0)) or 0),
            liquidity=float(market.get("liquidity", 0) or 0),
            end_date=market.get("endDate", data.get("endDate")),
            is_active=market.get("active", True) and not market.get("closed", False),
        )


class GammaMarketClient:
    """Client for Polymarket Gamma API (market data)."""

    def __init__(self):
        self.host = settings.gamma_host
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_events(
        self,
        active: bool = True,
        closed: bool = False,
        limit: int = 20,
        offset: int = 0,
        order: str = "volume24hr",
        tag_id: Optional[int] = None,
    ) -> List[Market]:
        """
        Fetch events/markets with filtering.

        Args:
            active: Only active markets
            closed: Include closed markets
            limit: Number of results
            offset: Pagination offset
            order: Sort order (volume24hr, createdAt, etc.)
            tag_id: Filter by tag/category

        Returns:
            List of Market objects
        """
        try:
            client = await self._get_client()

            params = {
                "active": str(active).lower(),
                "closed": str(closed).lower(),
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": "false",
            }

            if tag_id:
                params["tag_id"] = tag_id

            response = await client.get(f"{self.host}/events", params=params)
            response.raise_for_status()

            data = response.json()
            markets = []

            for event in data:
                try:
                    market = Market.from_api(event)
                    if market.yes_token_id:  # Only include markets with valid tokens
                        markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue

            return markets

        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            return []

    async def get_trending_markets(self, limit: int = 20) -> List[Market]:
        """Get trending markets by 24h volume."""
        return await self.get_events(
            active=True,
            closed=False,
            limit=limit,
            order="volume24hr",
        )

    async def get_new_markets(self, limit: int = 20) -> List[Market]:
        """Get newest markets."""
        return await self.get_events(
            active=True,
            closed=False,
            limit=limit,
            order="createdAt",
        )

    async def get_market_by_condition_id(self, condition_id: str) -> Optional[Market]:
        """
        Get market by condition ID.

        Args:
            condition_id: Market condition ID

        Returns:
            Market or None if not found
        """
        try:
            client = await self._get_client()

            response = await client.get(
                f"{self.host}/markets",
                params={"condition_ids": condition_id},
            )
            response.raise_for_status()

            data = response.json()
            if data:
                return Market.from_api(data[0])
            return None

        except Exception as e:
            logger.error(f"Failed to fetch market {condition_id}: {e}")
            return None

    async def search_markets(self, query: str, limit: int = 20) -> List[Market]:
        """
        Search markets by keyword.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching markets
        """
        try:
            # Gamma API doesn't have direct search, fetch and filter
            all_markets = await self.get_events(limit=100)

            query_lower = query.lower()
            matching = [
                m for m in all_markets
                if query_lower in m.question.lower()
                or (m.description and query_lower in m.description.lower())
            ]

            return matching[:limit]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def get_tags(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get available tags/categories.

        Returns:
            List of tags with id and label
        """
        try:
            client = await self._get_client()

            response = await client.get(
                f"{self.host}/tags",
                params={"limit": limit},
            )
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Failed to fetch tags: {e}")
            return []

    async def get_markets_by_tag(
        self,
        tag_id: int,
        limit: int = 20,
    ) -> List[Market]:
        """
        Get markets by tag/category.

        Args:
            tag_id: Tag ID
            limit: Maximum results

        Returns:
            List of markets in category
        """
        return await self.get_events(
            active=True,
            closed=False,
            limit=limit,
            tag_id=tag_id,
        )

    async def get_market_price(self, token_id: str) -> Optional[float]:
        """
        Get current price for a token.

        Note: This requires CLOB API for real-time prices.
        For now, returns price from market data.

        Args:
            token_id: Token ID

        Returns:
            Current price or None
        """
        try:
            client = await self._get_client()

            response = await client.get(
                f"{self.host}/markets",
                params={"clob_token_ids": token_id},
            )
            response.raise_for_status()

            data = response.json()
            if data:
                market = Market.from_api(data[0])
                # Return YES price if this is YES token, otherwise NO
                if market.yes_token_id == token_id:
                    return market.yes_price
                else:
                    return market.no_price

            return None

        except Exception as e:
            logger.error(f"Failed to fetch price for {token_id}: {e}")
            return None

    async def get_trader_stats(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get trader statistics for copy trading.

        Note: This may require additional API endpoints or CLOB data.

        Args:
            address: Trader wallet address

        Returns:
            Trader stats or None
        """
        try:
            # This would typically come from CLOB API trade history
            # For now, return placeholder
            return {
                "address": address,
                "total_volume": 0,
                "total_trades": 0,
                "pnl": 0,
                "win_rate": 0,
            }
        except Exception as e:
            logger.error(f"Failed to fetch trader stats: {e}")
            return None

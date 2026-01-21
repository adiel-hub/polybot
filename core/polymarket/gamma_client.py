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
    slug: Optional[str] = None
    event_id: Optional[str] = None  # Parent event ID for multi-outcome markets
    event_title: Optional[str] = None  # Parent event title
    outcomes_count: int = 1  # Number of outcomes in parent event

    @classmethod
    def from_api(cls, data: Dict[str, Any], market_data: Dict[str, Any] = None) -> "Market":
        """Create Market from API response.

        Args:
            data: Event data from API
            market_data: Optional specific market data (for multi-outcome events)
        """
        import json

        # Use provided market_data or extract from event
        if market_data:
            market = market_data
        else:
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

        # Get event info for multi-outcome tracking
        markets_list = data.get("markets", [])
        outcomes_count = len(markets_list) if markets_list else 1

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
            slug=market.get("slug", data.get("slug")),
            event_id=data.get("id"),
            event_title=data.get("title"),
            outcomes_count=outcomes_count,
        )

    @classmethod
    def all_from_event(cls, event_data: Dict[str, Any]) -> List["Market"]:
        """Create Market objects for all outcomes in a multi-outcome event.

        For events with multiple markets (e.g., Super Bowl with 32 teams),
        this returns a Market object for each outcome that has liquidity.

        Args:
            event_data: Event data from Gamma API

        Returns:
            List of Market objects for each tradeable outcome
        """
        markets_data = event_data.get("markets", [])

        # If no markets array or single market, use standard parsing
        if not markets_data or len(markets_data) <= 1:
            market = cls.from_api(event_data)
            return [market] if market.yes_token_id else []

        # Multi-outcome event - parse each market
        markets = []
        for market_data in markets_data:
            try:
                market = cls.from_api(event_data, market_data)
                if market.yes_token_id:
                    markets.append(market)
            except Exception:
                continue

        return markets


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
                    # Return one market per event (use first market as representative)
                    # Multi-outcome events will show "+X Options" link for expansion
                    market = Market.from_api(event)
                    if market.yes_token_id:
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

    async def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get event by ID with all its markets/outcomes.

        Args:
            event_id: Event ID

        Returns:
            Event data dict with markets array, or None
        """
        try:
            client = await self._get_client()

            response = await client.get(f"{self.host}/events/{event_id}")

            if response.status_code == 404:
                return None

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to fetch event {event_id}: {e}")
            return None

    async def get_event_markets(self, event_id: str) -> List[Market]:
        """
        Get all markets/outcomes for an event.

        Args:
            event_id: Event ID

        Returns:
            List of Market objects for each outcome
        """
        event_data = await self.get_event_by_id(event_id)
        if not event_data:
            return []

        return Market.all_from_event(event_data)

    async def get_market_by_condition_id(self, condition_id: str) -> Optional[Market]:
        """
        Get market by condition ID.

        Tries /markets API first, then falls back to searching /events
        for multi-outcome markets that may not be indexed in /markets.

        Args:
            condition_id: Market condition ID

        Returns:
            Market or None if not found
        """
        try:
            client = await self._get_client()

            # Try /markets endpoint first (works for most markets)
            response = await client.get(
                f"{self.host}/markets",
                params={"condition_ids": condition_id},
            )
            response.raise_for_status()

            data = response.json()
            if data:
                return Market.from_api(data[0])

            # Fallback: Search events for multi-outcome markets
            # Some markets only appear in /events but not /markets
            logger.info(f"Market not found in /markets, searching /events for {condition_id[:16]}...")
            return await self._search_events_for_condition_id(condition_id)

        except Exception as e:
            logger.error(f"Failed to fetch market {condition_id}: {e}")
            return None

    async def _search_events_for_condition_id(self, condition_id: str) -> Optional[Market]:
        """
        Search through events to find a market by condition ID.

        This is a fallback for multi-outcome markets that exist in /events
        but are not indexed in the /markets endpoint.

        Args:
            condition_id: Market condition ID to find

        Returns:
            Market or None if not found
        """
        try:
            # Fetch recent events (sorted by volume for relevance)
            events = await self.get_events(limit=200)

            for market in events:
                if market.condition_id == condition_id:
                    logger.info(f"Found market in events: {market.question[:50]}...")
                    return market

            logger.warning(f"Market {condition_id[:16]}... not found in events search")
            return None

        except Exception as e:
            logger.error(f"Events search failed for {condition_id}: {e}")
            return None

    async def get_market_by_slug(self, slug: str) -> Optional[Market]:
        """
        Get market by URL slug.

        Args:
            slug: Market slug from URL (e.g., 'bitcoin-100k-2025')

        Returns:
            Market or None if not found
        """
        try:
            client = await self._get_client()

            response = await client.get(f"{self.host}/markets/slug/{slug}")

            if response.status_code == 404:
                logger.warning(f"Market slug not found: {slug}")
                return None

            response.raise_for_status()

            data = response.json()
            return Market.from_api(data)

        except Exception as e:
            logger.error(f"Failed to fetch market by slug '{slug}': {e}")
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

        Fetches trader data from Polymarket's public API endpoints.

        Args:
            address: Trader wallet address

        Returns:
            Trader stats including volume, trades, PnL, win rate
        """
        try:
            client = await self._get_client()

            # Fetch trader profile data from Polymarket API
            # Using the profiles endpoint which provides trader statistics
            profile_url = f"https://polymarket.com/api/profile/{address.lower()}"
            response = await client.get(profile_url)

            if response.status_code == 200:
                data = response.json()

                # Extract stats from profile response
                positions_value = float(data.get("positionsValue", 0) or 0)
                profit_loss = float(data.get("profitLoss", 0) or 0)

                return {
                    "address": address,
                    "total_volume": positions_value,
                    "total_trades": int(data.get("tradesCount", 0) or 0),
                    "pnl": profit_loss,
                    "win_rate": self._calculate_win_rate(data),
                    "positions_value": positions_value,
                    "profit_loss_percent": float(data.get("profitLossPercent", 0) or 0),
                    "username": data.get("username", ""),
                    "profile_image": data.get("profileImage", ""),
                }

            # Fallback: Try the CLOB API activity endpoint
            clob_url = f"https://clob.polymarket.com/activity?user={address.lower()}&limit=100"
            clob_response = await client.get(clob_url)

            if clob_response.status_code == 200:
                activities = clob_response.json()
                return self._calculate_stats_from_activity(address, activities)

            # Return basic stats if no data available
            return {
                "address": address,
                "total_volume": 0,
                "total_trades": 0,
                "pnl": 0,
                "win_rate": 0,
            }

        except Exception as e:
            logger.error(f"Failed to fetch trader stats for {address}: {e}")
            return None

    def _calculate_win_rate(self, profile_data: Dict[str, Any]) -> float:
        """Calculate win rate from profile data."""
        try:
            winning_trades = int(profile_data.get("winningTrades", 0) or 0)
            total_trades = int(profile_data.get("tradesCount", 0) or 0)

            if total_trades == 0:
                return 0.0

            return round((winning_trades / total_trades) * 100, 1)
        except (ValueError, ZeroDivisionError):
            return 0.0

    def _calculate_stats_from_activity(
        self,
        address: str,
        activities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calculate trader stats from activity history."""
        if not activities:
            return {
                "address": address,
                "total_volume": 0,
                "total_trades": 0,
                "pnl": 0,
                "win_rate": 0,
            }

        total_volume = 0.0
        total_trades = len(activities)
        profitable_trades = 0
        total_pnl = 0.0

        for activity in activities:
            # Calculate volume from trade size and price
            size = float(activity.get("size", 0) or 0)
            price = float(activity.get("price", 0) or 0)
            trade_value = size * price
            total_volume += trade_value

            # Track PnL if available
            pnl = float(activity.get("pnl", 0) or 0)
            total_pnl += pnl
            if pnl > 0:
                profitable_trades += 1

        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0

        return {
            "address": address,
            "total_volume": round(total_volume, 2),
            "total_trades": total_trades,
            "pnl": round(total_pnl, 2),
            "win_rate": round(win_rate, 1),
        }

    async def get_top_traders(
        self,
        limit: int = 25,
        offset: int = 0,
        category: str = "OVERALL",
        time_period: str = "WEEK",
        order_by: str = "PNL",
    ) -> List[Dict[str, Any]]:
        """
        Get top traders by performance from Polymarket leaderboard.

        Uses official Polymarket Data API: https://data-api.polymarket.com/v1/leaderboard

        Args:
            limit: Maximum number of traders (1-50)
            offset: Pagination offset (0-1000)
            category: OVERALL, POLITICS, SPORTS, CRYPTO, CULTURE, MENTIONS, WEATHER, ECONOMICS, TECH, FINANCE
            time_period: DAY, WEEK, MONTH, ALL
            order_by: PNL or VOL

        Returns:
            List of trader stats sorted by performance
        """
        try:
            client = await self._get_client()

            # Official Polymarket leaderboard API
            leaderboard_url = "https://data-api.polymarket.com/v1/leaderboard"
            response = await client.get(
                leaderboard_url,
                params={
                    "category": category,
                    "timePeriod": time_period,
                    "orderBy": order_by,
                    "limit": min(limit, 50),  # API max is 50
                    "offset": min(offset, 1000),  # API max is 1000
                },
            )

            if response.status_code != 200:
                logger.warning(f"Leaderboard API returned {response.status_code}")
                return []

            data = response.json()
            traders = []

            # API returns array of trader objects directly
            for entry in data if isinstance(data, list) else []:
                trader = {
                    "address": entry.get("proxyWallet", ""),
                    "name": entry.get("userName", "Anonymous"),
                    "pnl": float(entry.get("pnl", 0) or 0),
                    "volume": float(entry.get("vol", 0) or 0),
                    "rank": int(entry.get("rank", 0) or 0),
                    "profile_image": entry.get("profileImage", ""),
                    "x_username": entry.get("xUsername", ""),
                    "verified": entry.get("verifiedBadge", False),
                }
                traders.append(trader)

            return traders

        except Exception as e:
            logger.error(f"Failed to fetch top traders: {e}")
            return []

    async def get_trader_profile(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get specific trader's leaderboard stats.

        Args:
            address: Trader wallet address (0x-prefixed)

        Returns:
            Trader stats or None if not found
        """
        try:
            client = await self._get_client()

            leaderboard_url = "https://data-api.polymarket.com/v1/leaderboard"
            response = await client.get(
                leaderboard_url,
                params={"user": address.lower()},
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                entry = data[0]
                return {
                    "address": entry.get("proxyWallet", address),
                    "name": entry.get("userName", "Anonymous"),
                    "pnl": float(entry.get("pnl", 0) or 0),
                    "volume": float(entry.get("vol", 0) or 0),
                    "rank": int(entry.get("rank", 0) or 0),
                    "profile_image": entry.get("profileImage", ""),
                    "x_username": entry.get("xUsername", ""),
                    "verified": entry.get("verifiedBadge", False),
                }

            return None

        except Exception as e:
            logger.error(f"Failed to fetch trader profile for {address}: {e}")
            return None

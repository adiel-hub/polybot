"""Leaderboard service for discovering top traders."""

import logging
from typing import Optional, List, Dict, Any

from core.polymarket import GammaMarketClient

logger = logging.getLogger(__name__)


class LeaderboardService:
    """Service for trader leaderboard operations."""

    # Valid categories
    CATEGORIES = [
        "OVERALL",
        "POLITICS",
        "SPORTS",
        "CRYPTO",
        "CULTURE",
        "MENTIONS",
        "WEATHER",
        "ECONOMICS",
        "TECH",
        "FINANCE",
    ]

    # Valid time periods
    TIME_PERIODS = ["DAY", "WEEK", "MONTH", "ALL"]

    # Valid sort options
    ORDER_OPTIONS = ["PNL", "VOL"]

    def __init__(self):
        self.gamma_client = GammaMarketClient()

    async def get_top_traders(
        self,
        limit: int = 10,
        offset: int = 0,
        category: str = "OVERALL",
        time_period: str = "WEEK",
        order_by: str = "PNL",
    ) -> List[Dict[str, Any]]:
        """
        Get top traders from Polymarket leaderboard.

        Args:
            limit: Number of traders to return (1-50)
            offset: Pagination offset (0-1000)
            category: Filter by category (OVERALL, POLITICS, SPORTS, etc.)
            time_period: Time window (DAY, WEEK, MONTH, ALL)
            order_by: Sort by PNL or VOL

        Returns:
            List of trader dictionaries with:
                - address: Wallet address
                - name: Display name
                - pnl: Profit/loss
                - volume: Trading volume
                - rank: Leaderboard rank
                - profile_image: Avatar URL
                - x_username: Twitter handle
                - verified: Verified badge status
        """
        # Validate inputs
        if category not in self.CATEGORIES:
            logger.warning(f"Invalid category {category}, using OVERALL")
            category = "OVERALL"

        if time_period not in self.TIME_PERIODS:
            logger.warning(f"Invalid time period {time_period}, using WEEK")
            time_period = "WEEK"

        if order_by not in self.ORDER_OPTIONS:
            logger.warning(f"Invalid order_by {order_by}, using PNL")
            order_by = "PNL"

        try:
            traders = await self.gamma_client.get_top_traders(
                limit=limit,
                offset=offset,
                category=category,
                time_period=time_period,
                order_by=order_by,
            )

            logger.info(
                f"Fetched {len(traders)} traders "
                f"(category={category}, period={time_period}, order={order_by})"
            )

            return traders

        except Exception as e:
            logger.error(f"Failed to fetch top traders: {e}")
            return []

    async def get_trader_profile(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed profile for a specific trader.

        Args:
            address: Trader wallet address

        Returns:
            Trader profile dictionary or None if not found
        """
        try:
            profile = await self.gamma_client.get_trader_profile(address)
            if profile:
                logger.info(f"Fetched profile for trader {address}")
            else:
                logger.warning(f"Trader {address} not found in leaderboard")

            return profile

        except Exception as e:
            logger.error(f"Failed to fetch trader profile: {e}")
            return None

    async def search_traders_by_name(
        self,
        username: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search traders by username (not yet implemented in API).

        Args:
            username: Username to search for
            limit: Max results

        Returns:
            List of matching traders
        """
        # Note: userName query parameter exists in API but functionality unclear
        # For now, fetch all and filter client-side
        try:
            all_traders = await self.get_top_traders(limit=50, order_by="VOL")

            # Filter by username (case-insensitive)
            username_lower = username.lower()
            matches = [
                t
                for t in all_traders
                if username_lower in t.get("name", "").lower()
                or username_lower in t.get("x_username", "").lower()
            ]

            return matches[:limit]

        except Exception as e:
            logger.error(f"Failed to search traders: {e}")
            return []

    def get_available_categories(self) -> List[Dict[str, str]]:
        """Get list of available category filters."""
        return [
            {"id": cat, "name": cat.replace("_", " ").title()} for cat in self.CATEGORIES
        ]

    def get_available_time_periods(self) -> List[Dict[str, str]]:
        """Get list of available time period filters."""
        return [
            {"DAY": "24 Hours"},
            {"WEEK": "7 Days"},
            {"MONTH": "30 Days"},
            {"ALL": "All Time"},
        ]

    async def close(self):
        """Close HTTP client."""
        await self.gamma_client.close()

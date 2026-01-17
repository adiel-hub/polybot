"""Market monitor service for detecting new Polymarket markets."""

import logging
from typing import List

from core.polymarket.gamma_client import GammaMarketClient, Market
from news_bot.database.repositories.posted_market_repo import PostedMarketRepository

logger = logging.getLogger(__name__)


class MarketMonitorService:
    """Monitors Polymarket for new markets that haven't been posted yet."""

    def __init__(
        self,
        gamma_client: GammaMarketClient,
        posted_repo: PostedMarketRepository,
        min_volume: float = 1000.0,
        min_liquidity: float = 500.0,
    ):
        """
        Initialize the market monitor.

        Args:
            gamma_client: Gamma API client for fetching markets
            posted_repo: Repository for tracking posted markets
            min_volume: Minimum total volume to consider a market
            min_liquidity: Minimum liquidity to consider a market
        """
        self.gamma_client = gamma_client
        self.posted_repo = posted_repo
        self.min_volume = min_volume
        self.min_liquidity = min_liquidity

    async def get_unposted_markets(self, limit: int = 50) -> List[Market]:
        """
        Fetch new markets and filter out already-posted ones.

        1. Fetches newest markets from Gamma API (sorted by creation date)
        2. Filters by volume and liquidity thresholds
        3. Checks against posted_markets table to avoid duplicates
        4. Returns list of markets that haven't been posted yet

        Args:
            limit: Maximum number of markets to fetch from API

        Returns:
            List of Market objects that haven't been posted
        """
        try:
            # Fetch newest markets
            markets = await self.gamma_client.get_new_markets(limit=limit)
            logger.info(f"Fetched {len(markets)} markets from Gamma API")

            # Filter by volume and liquidity thresholds
            filtered = []
            for market in markets:
                if market.total_volume < self.min_volume:
                    continue
                if market.liquidity < self.min_liquidity:
                    continue
                if not market.is_active:
                    continue
                filtered.append(market)

            logger.info(
                f"Filtered to {len(filtered)} markets "
                f"(volume >= ${self.min_volume:,.0f}, liquidity >= ${self.min_liquidity:,.0f})"
            )

            # Check which are already posted
            unposted = []
            for market in filtered:
                is_posted = await self.posted_repo.exists(market.condition_id)
                if not is_posted:
                    unposted.append(market)

            logger.info(f"Found {len(unposted)} unposted markets")
            return unposted

        except Exception as e:
            logger.error(f"Error getting unposted markets: {e}")
            return []

    async def get_trending_unposted(self, limit: int = 50) -> List[Market]:
        """
        Get trending markets that haven't been posted.

        Uses volume sorting instead of creation date.

        Args:
            limit: Maximum number of markets to fetch

        Returns:
            List of unposted trending markets
        """
        try:
            markets = await self.gamma_client.get_trending_markets(limit=limit)
            logger.info(f"Fetched {len(markets)} trending markets")

            # Filter and check posted status
            unposted = []
            for market in markets:
                if market.total_volume < self.min_volume:
                    continue
                if market.liquidity < self.min_liquidity:
                    continue
                if not market.is_active:
                    continue

                is_posted = await self.posted_repo.exists(market.condition_id)
                if not is_posted:
                    unposted.append(market)

            return unposted

        except Exception as e:
            logger.error(f"Error getting trending unposted markets: {e}")
            return []

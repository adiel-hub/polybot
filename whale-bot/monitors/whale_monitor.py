"""Whale trade monitor using Polymarket Data API."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Set

import aiohttp

from config import (
    DATA_API_URL,
    WHALE_THRESHOLD,
    POLL_INTERVAL,
)

logger = logging.getLogger(__name__)

# Maximum age of trades to alert on (in seconds)
# Trades older than this are skipped to avoid alerting on historical data at startup
MAX_TRADE_AGE_SECONDS = 300  # 5 minutes


@dataclass
class WhaleTrade:
    """Data class for whale trade events."""

    trader_address: str
    trader_name: Optional[str]
    market_title: str
    condition_id: str
    outcome: str
    side: str
    size: float
    price: float
    value: float
    tx_hash: Optional[str]
    timestamp: datetime
    market_slug: Optional[str]
    market_icon: Optional[str]


class WhaleMonitor:
    """Monitor large trades on Polymarket via Data API polling."""

    def __init__(self, on_whale_detected: Callable[[WhaleTrade], None]):
        """
        Initialize the whale monitor.

        Args:
            on_whale_detected: Callback function when a whale trade is detected
        """
        self.on_whale_detected = on_whale_detected
        self.running = False
        self._processed_trades: Set[str] = set()
        self._session: Optional[aiohttp.ClientSession] = None

    def _create_trade_id(self, trade: dict) -> str:
        """Create unique ID for a trade to avoid duplicates."""
        tx_hash = trade.get("transactionHash", "")
        timestamp = trade.get("timestamp", "")
        asset = trade.get("asset", "")
        return f"{tx_hash}_{timestamp}_{asset}"

    def _parse_trade(self, trade: dict) -> Optional[WhaleTrade]:
        """Parse trade data from API response."""
        try:
            size = float(trade.get("size", 0) or 0)
            price = float(trade.get("price", 0) or 0)
            value = size * price

            # Check threshold
            if value < WHALE_THRESHOLD:
                return None

            # Parse timestamp (can be Unix timestamp int or ISO string)
            timestamp_raw = trade.get("timestamp")
            if timestamp_raw:
                try:
                    if isinstance(timestamp_raw, (int, float)):
                        # Unix timestamp in seconds
                        timestamp = datetime.fromtimestamp(timestamp_raw)
                    elif isinstance(timestamp_raw, str):
                        timestamp = datetime.fromisoformat(
                            timestamp_raw.replace("Z", "+00:00")
                        )
                    else:
                        timestamp = datetime.now()
                except (ValueError, OSError):
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()

            # Get trader info
            trader_address = trade.get("proxyWallet", "Unknown")
            trader_name = trade.get("name") or trade.get("pseudonym")

            return WhaleTrade(
                trader_address=trader_address,
                trader_name=trader_name,
                market_title=trade.get("title", "Unknown Market"),
                condition_id=trade.get("conditionId", ""),
                outcome=trade.get("outcome", "Unknown"),
                side=trade.get("side", "BUY"),
                size=size,
                price=price,
                value=value,
                tx_hash=trade.get("transactionHash"),
                timestamp=timestamp,
                market_slug=trade.get("slug"),
                market_icon=trade.get("icon"),
            )

        except Exception as e:
            logger.error(f"Error parsing trade: {e}")
            return None

    async def _fetch_trades(self) -> list:
        """Fetch recent trades from Data API."""
        try:
            params = {
                "limit": 100,
                "offset": 0,
                "filterType": "CASH",
                "filterAmount": WHALE_THRESHOLD,
            }

            async with self._session.get(
                f"{DATA_API_URL}/trades",
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API error: {response.status}")
                    return []

        except asyncio.TimeoutError:
            logger.warning("API request timed out")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")
            return []

    async def _poll_trades(self) -> None:
        """Poll for new whale trades."""
        trades = await self._fetch_trades()
        now = datetime.now()

        for trade_data in trades:
            trade_id = self._create_trade_id(trade_data)

            # Skip already processed
            if trade_id in self._processed_trades:
                continue

            self._processed_trades.add(trade_id)

            # Keep set bounded
            if len(self._processed_trades) > 10000:
                self._processed_trades = set(
                    list(self._processed_trades)[-5000:]
                )

            # Parse and notify
            whale_trade = self._parse_trade(trade_data)
            if whale_trade:
                # Skip trades older than MAX_TRADE_AGE_SECONDS
                trade_age = (now - whale_trade.timestamp).total_seconds()
                if trade_age > MAX_TRADE_AGE_SECONDS:
                    logger.debug(
                        f"Skipping old trade ({trade_age:.0f}s old): "
                        f"${whale_trade.value:,.2f} on {whale_trade.market_title[:30]}"
                    )
                    continue

                logger.info(
                    f"Whale detected: ${whale_trade.value:,.2f} on {whale_trade.market_title[:50]}"
                )
                await self.on_whale_detected(whale_trade)

    async def start(self) -> None:
        """Start monitoring for whale trades."""
        self.running = True
        logger.info(
            f"Starting whale monitor (threshold: ${WHALE_THRESHOLD:,.0f}, "
            f"poll interval: {POLL_INTERVAL}s)"
        )

        self._session = aiohttp.ClientSession()

        try:
            while self.running:
                await self._poll_trades()
                await asyncio.sleep(POLL_INTERVAL)
        finally:
            await self._session.close()

    async def stop(self) -> None:
        """Stop the monitor."""
        self.running = False
        if self._session:
            await self._session.close()
        logger.info("Whale monitor stopped")

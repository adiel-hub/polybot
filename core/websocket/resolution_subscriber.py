"""Market resolution subscriber for auto-claim functionality."""

import asyncio
import json
import logging
from typing import Dict, Any, Set, Callable, Optional
from datetime import datetime

from database.connection import Database
from core.polymarket import GammaMarketClient

logger = logging.getLogger(__name__)


class ResolutionSubscriber:
    """
    Monitors market resolutions and triggers auto-claims.

    Polls Gamma API for position markets that have resolved.
    When a market resolves with a clear winner (price = 1.0 or 0.0),
    it triggers the claim callback.
    """

    def __init__(
        self,
        db: Database,
        poll_interval: int = 300,  # 5 minutes
        on_resolution_callback: Optional[Callable] = None,
    ):
        """
        Initialize resolution subscriber.

        Args:
            db: Database instance
            poll_interval: Seconds between resolution checks
            on_resolution_callback: Async callback(condition_id, winning_outcome)
        """
        self.db = db
        self.poll_interval = poll_interval
        self.on_resolution_callback = on_resolution_callback

        self.gamma_client = GammaMarketClient()

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._monitored_markets: Set[str] = set()  # condition_ids with positions

    async def start(self) -> None:
        """Start resolution monitoring."""
        self._running = True
        await self._refresh_monitored_markets()
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            f"Resolution subscriber started, monitoring {len(self._monitored_markets)} markets"
        )

    async def stop(self) -> None:
        """Stop resolution monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.gamma_client.close()
        logger.info("Resolution subscriber stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop for resolution checks."""
        while self._running:
            try:
                # Refresh monitored markets periodically
                await self._refresh_monitored_markets()

                # Check for resolutions
                await self._check_resolutions()
            except Exception as e:
                logger.error(f"Resolution check error: {e}")

            await asyncio.sleep(self.poll_interval)

    async def _refresh_monitored_markets(self) -> None:
        """Refresh list of markets to monitor from active positions."""
        try:
            conn = await self.db.get_connection()
            cursor = await conn.execute(
                """
                SELECT DISTINCT market_condition_id
                FROM positions
                WHERE size > 0
                """
            )
            rows = await cursor.fetchall()
            self._monitored_markets = {row["market_condition_id"] for row in rows}
            logger.debug(f"Monitoring {len(self._monitored_markets)} markets for resolution")
        except Exception as e:
            logger.error(f"Failed to refresh monitored markets: {e}")

    async def _check_resolutions(self) -> None:
        """Check if any monitored markets have resolved."""
        if not self._monitored_markets:
            return

        # Check already-processed markets to avoid duplicate processing
        processed = await self._get_processed_markets()

        for condition_id in list(self._monitored_markets):
            if condition_id in processed:
                continue

            try:
                resolution_data = await self._get_resolution_data(condition_id)

                if resolution_data and resolution_data.get("resolved"):
                    winning_outcome = resolution_data.get("winning_outcome")
                    logger.info(
                        f"Market resolved: {condition_id[:16]}... "
                        f"Winner: {winning_outcome}"
                    )

                    if self.on_resolution_callback:
                        await self.on_resolution_callback(
                            condition_id=condition_id,
                            winning_outcome=winning_outcome,
                        )

            except Exception as e:
                logger.error(f"Check resolution failed for {condition_id[:16]}...: {e}")

    async def _get_resolution_data(
        self,
        condition_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get resolution data for a market.

        Checks if a market has resolved by looking at outcome prices.
        A market is resolved when one outcome has price 1.0 (winner)
        and the other has price 0.0 (loser).

        Args:
            condition_id: Market condition ID

        Returns:
            Dict with resolved status and winning outcome
        """
        try:
            market = await self.gamma_client.get_market_by_condition_id(condition_id)

            if not market:
                return {"resolved": False}

            # Check if market is inactive (closed)
            if market.is_active:
                return {"resolved": False}

            # Check outcome prices
            yes_price = market.yes_price
            no_price = market.no_price

            # Market is resolved if one outcome has price >= 0.99 (accounting for rounding)
            if yes_price >= 0.99:
                return {
                    "resolved": True,
                    "winning_outcome": "YES",
                    "yes_price": yes_price,
                    "no_price": no_price,
                }
            elif no_price >= 0.99:
                return {
                    "resolved": True,
                    "winning_outcome": "NO",
                    "yes_price": yes_price,
                    "no_price": no_price,
                }

            # Market closed but no clear winner yet (void/refund case)
            return {"resolved": False, "closed": True}

        except Exception as e:
            logger.error(f"Get resolution data failed for {condition_id[:16]}...: {e}")
            return None

    async def _get_processed_markets(self) -> Set[str]:
        """Get set of already-processed market condition IDs."""
        try:
            conn = await self.db.get_connection()
            cursor = await conn.execute(
                """
                SELECT condition_id FROM resolved_markets WHERE processed = 1
                """
            )
            rows = await cursor.fetchall()
            return {row["condition_id"] for row in rows}
        except Exception as e:
            logger.error(f"Failed to get processed markets: {e}")
            return set()

    async def add_market(self, condition_id: str) -> None:
        """
        Add a market to monitor.

        Called when user opens a new position.

        Args:
            condition_id: Market condition ID
        """
        self._monitored_markets.add(condition_id)
        logger.debug(f"Added market to resolution monitoring: {condition_id[:16]}...")

    async def remove_market(self, condition_id: str) -> None:
        """
        Remove a market from monitoring.

        Called when all positions on a market are closed.

        Args:
            condition_id: Market condition ID
        """
        self._monitored_markets.discard(condition_id)
        logger.debug(f"Removed market from resolution monitoring: {condition_id[:16]}...")

    def get_monitored_count(self) -> int:
        """Get number of markets being monitored."""
        return len(self._monitored_markets)

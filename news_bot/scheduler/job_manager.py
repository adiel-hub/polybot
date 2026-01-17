"""Job manager for scheduling market polling."""

import logging
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime

logger = logging.getLogger(__name__)


class JobManager:
    """
    Manages scheduled jobs for market monitoring.

    Uses APScheduler for async job scheduling.
    """

    def __init__(self):
        """Initialize the job manager."""
        self.scheduler = AsyncIOScheduler()
        self._poll_callback: Optional[Callable] = None
        self._is_running = False

    def set_poll_callback(self, callback: Callable) -> None:
        """
        Set the callback function for market polling.

        Args:
            callback: Async function to call on each poll
        """
        self._poll_callback = callback

    def start(self, interval_minutes: int = 15) -> None:
        """
        Start the scheduler.

        Adds a recurring job that polls for new markets
        at the specified interval. Also runs immediately on startup.

        Args:
            interval_minutes: Minutes between polls
        """
        if not self._poll_callback:
            raise ValueError("Poll callback not set. Call set_poll_callback first.")

        if self._is_running:
            logger.warning("Scheduler is already running")
            return

        # Add recurring job
        self.scheduler.add_job(
            self._poll_callback,
            IntervalTrigger(minutes=interval_minutes),
            id="market_poll",
            name="Poll for new markets",
            replace_existing=True,
        )

        # Run immediately on startup
        self.scheduler.add_job(
            self._poll_callback,
            DateTrigger(run_date=datetime.now()),
            id="market_poll_immediate",
            name="Initial market poll",
        )

        self.scheduler.start()
        self._is_running = True

        logger.info(
            f"Scheduler started. Polling every {interval_minutes} minutes."
        )

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("Scheduler stopped")

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._is_running

    def get_next_run_time(self) -> Optional[datetime]:
        """Get the next scheduled run time."""
        job = self.scheduler.get_job("market_poll")
        if job:
            return job.next_run_time
        return None

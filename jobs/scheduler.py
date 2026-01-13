"""Job scheduler setup.

Note: Polling-based jobs have been replaced with WebSocket-based real-time updates.
See core/websocket/ for the new implementation.

This file is kept for compatibility but no longer registers any polling jobs.
"""

import logging
from telegram.ext import Application

logger = logging.getLogger(__name__)


async def setup_jobs(application: Application) -> None:
    """
    Register background jobs.

    Note: This function is deprecated. Use setup_websocket_service() instead.
    Polling jobs have been replaced with WebSocket-based real-time updates.
    """
    logger.info(
        "setup_jobs() is deprecated - use setup_websocket_service() instead. "
        "No polling jobs registered."
    )

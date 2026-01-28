"""Proxy configuration for Polymarket CLOB client."""

import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)


def configure_clob_proxy() -> None:
    """
    Configure the py-clob-client to use a proxy if configured.

    This monkey-patches the global httpx client used by py-clob-client
    to route requests through the configured proxy.
    """
    if not settings.proxy_url:
        logger.info("No proxy configured for CLOB client")
        return

    try:
        # Import the helpers module from py-clob-client
        from py_clob_client.http_helpers import helpers

        # Create a new httpx client with proxy support
        proxy_client = httpx.Client(
            http2=True,
            proxy=settings.proxy_url,
            timeout=30.0,
        )

        # Replace the global client
        helpers._http_client = proxy_client

        logger.info(f"✅ CLOB client configured to use proxy")

    except Exception as e:
        logger.error(f"Failed to configure proxy: {e}")
        raise

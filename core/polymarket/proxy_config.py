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
        # Ensure proxy URL has http:// prefix
        proxy_url = settings.proxy_url
        if not proxy_url.startswith(("http://", "https://")):
            proxy_url = f"http://{proxy_url}"

        logger.info(f"Configuring CLOB proxy: {proxy_url.split('@')[-1]}")  # Log host only, not credentials

        # Import the helpers module from py-clob-client
        from py_clob_client.http_helpers import helpers

        # Create a new httpx client with proxy support
        proxy_client = httpx.Client(
            http2=True,
            proxy=proxy_url,
            timeout=30.0,
        )

        # Replace the global client
        helpers._http_client = proxy_client

        # Test the proxy by making a simple request
        try:
            test_resp = proxy_client.get("https://httpbin.org/ip", timeout=10.0)
            if test_resp.status_code == 200:
                ip_info = test_resp.json()
                logger.info(f"✅ Proxy working - External IP: {ip_info.get('origin', 'unknown')}")
            else:
                logger.warning(f"⚠️ Proxy test returned status {test_resp.status_code}")
        except Exception as test_err:
            logger.warning(f"⚠️ Proxy test failed: {test_err}")

        logger.info("✅ CLOB client configured to use proxy")

    except Exception as e:
        logger.error(f"Failed to configure proxy: {e}")
        raise

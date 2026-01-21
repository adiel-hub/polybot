"""Alchemy Webhook Manager for programmatic webhook address management.

This service allows you to programmatically add/remove addresses
from your Alchemy webhook without manually updating the dashboard.
"""

import logging
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Alchemy Notify API base URL
ALCHEMY_NOTIFY_API = "https://dashboard.alchemy.com/api"


class AlchemyWebhookManager:
    """
    Manages Alchemy webhook addresses via their API.

    Allows programmatic addition/removal of addresses to monitor
    without manually updating the Alchemy dashboard.
    """

    def __init__(self, auth_token: str, webhook_id: str):
        """
        Initialize webhook manager.

        Args:
            auth_token: Alchemy Auth Token (from dashboard top right)
            webhook_id: ID of the webhook to manage
        """
        self.auth_token = auth_token
        self.webhook_id = webhook_id
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "X-Alchemy-Token": self.auth_token,
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def add_addresses(self, addresses: List[str]) -> bool:
        """
        Add addresses to the webhook.

        Args:
            addresses: List of wallet addresses to add

        Returns:
            True if successful
        """
        if not addresses:
            return True

        try:
            session = await self._get_session()

            payload = {
                "webhook_id": self.webhook_id,
                "addresses_to_add": addresses,
            }

            async with session.patch(
                f"{ALCHEMY_NOTIFY_API}/update-webhook-addresses",
                json=payload,
            ) as response:
                if response.status == 200:
                    logger.info(f"Added {len(addresses)} addresses to Alchemy webhook")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Failed to add addresses: {response.status} - {error}")
                    return False

        except Exception as e:
            logger.error(f"Failed to add addresses to webhook: {e}")
            return False

    async def remove_addresses(self, addresses: List[str]) -> bool:
        """
        Remove addresses from the webhook.

        Args:
            addresses: List of wallet addresses to remove

        Returns:
            True if successful
        """
        if not addresses:
            return True

        try:
            session = await self._get_session()

            payload = {
                "webhook_id": self.webhook_id,
                "addresses_to_remove": addresses,
            }

            async with session.patch(
                f"{ALCHEMY_NOTIFY_API}/update-webhook-addresses",
                json=payload,
            ) as response:
                if response.status == 200:
                    logger.info(f"Removed {len(addresses)} addresses from Alchemy webhook")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Failed to remove addresses: {response.status} - {error}")
                    return False

        except Exception as e:
            logger.error(f"Failed to remove addresses from webhook: {e}")
            return False

    async def get_addresses(self) -> List[str]:
        """
        Get all addresses currently tracked by the webhook.

        Returns:
            List of addresses
        """
        try:
            session = await self._get_session()

            async with session.get(
                f"{ALCHEMY_NOTIFY_API}/webhook-addresses",
                params={"webhook_id": self.webhook_id},
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    addresses = data.get("data", [])
                    logger.info(f"Retrieved {len(addresses)} addresses from Alchemy webhook")
                    return addresses
                else:
                    error = await response.text()
                    logger.error(f"Failed to get addresses: {response.status} - {error}")
                    return []

        except Exception as e:
            logger.error(f"Failed to get webhook addresses: {e}")
            return []

    async def sync_addresses(self, addresses: List[str]) -> bool:
        """
        Sync webhook addresses with provided list.

        Adds missing addresses and removes addresses not in the list.

        Args:
            addresses: Complete list of addresses that should be tracked

        Returns:
            True if successful
        """
        try:
            # Get current addresses
            current = set(addr.lower() for addr in await self.get_addresses())
            desired = set(addr.lower() for addr in addresses)

            # Calculate diff
            to_add = list(desired - current)
            to_remove = list(current - desired)

            success = True

            if to_add:
                if not await self.add_addresses(to_add):
                    success = False

            if to_remove:
                if not await self.remove_addresses(to_remove):
                    success = False

            logger.info(
                f"Synced webhook addresses: +{len(to_add)} -{len(to_remove)} "
                f"(total: {len(desired)})"
            )
            return success

        except Exception as e:
            logger.error(f"Failed to sync webhook addresses: {e}")
            return False

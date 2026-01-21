"""Alchemy Webhook handler for deposit detection.

Replaces the WebSocket-based deposit_subscriber with webhook-based detection.
This is much more cost-effective as Alchemy only sends events for registered addresses,
not all USDC transfers on the network.

Setup:
1. Create a webhook at https://dashboard.alchemy.com/webhooks
2. Select "Address Activity" webhook type
3. Choose Polygon Mainnet
4. Add your webhook URL (e.g., https://yourdomain.com/webhook/alchemy)
5. Copy the signing key to ALCHEMY_WEBHOOK_SIGNING_KEY in .env
"""

import hashlib
import hmac
import json
import logging
from typing import Dict, Any, Optional, Callable

from aiohttp import web

from database.connection import Database
from database.repositories import WalletRepository, UserRepository
from config.constants import USDC_ADDRESS, USDC_E_ADDRESS, USDC_DECIMALS

logger = logging.getLogger(__name__)


class AlchemyWebhookHandler:
    """
    Handles incoming Alchemy Address Activity webhooks for deposit detection.

    Benefits over WebSocket:
    - Only receives events for registered addresses (not all USDC transfers)
    - Much lower compute unit usage
    - Built-in retry logic from Alchemy
    - No connection management needed
    """

    def __init__(
        self,
        db: Database,
        signing_key: str,
        bot_send_message: Optional[Callable] = None,
    ):
        """
        Initialize webhook handler.

        Args:
            db: Database instance
            signing_key: Alchemy webhook signing key for verification
            bot_send_message: Callback to send Telegram messages
        """
        self.db = db
        self.signing_key = signing_key
        self.bot_send_message = bot_send_message

        # Track monitored addresses (lowercase)
        self._wallet_addresses: set[str] = set()

    async def load_wallet_addresses(self) -> None:
        """Load all wallet addresses from database."""
        try:
            wallet_repo = WalletRepository(self.db)
            addresses = await wallet_repo.get_all_addresses()
            self._wallet_addresses = {addr.lower() for addr in addresses}
            logger.info(f"Loaded {len(self._wallet_addresses)} wallet addresses for webhook monitoring")
        except Exception as e:
            logger.error(f"Failed to load wallet addresses: {e}")

    def add_wallet(self, address: str) -> None:
        """Add a wallet address to monitor."""
        self._wallet_addresses.add(address.lower())
        logger.debug(f"Added wallet to webhook monitoring: {address[:10]}...")

    def remove_wallet(self, address: str) -> None:
        """Remove a wallet address from monitoring."""
        self._wallet_addresses.discard(address.lower())

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """
        Verify the webhook signature from Alchemy.

        Args:
            body: Raw request body
            signature: Signature from x-alchemy-signature header

        Returns:
            True if signature is valid
        """
        if not self.signing_key:
            logger.warning("No signing key configured, skipping verification")
            return True

        expected = hmac.new(
            self.signing_key.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """
        Handle incoming Alchemy webhook request.

        Args:
            request: aiohttp request object

        Returns:
            HTTP response
        """
        try:
            # Get raw body for signature verification
            body = await request.read()

            # Verify signature
            signature = request.headers.get("x-alchemy-signature", "")
            if not self.verify_signature(body, signature):
                logger.warning("Invalid webhook signature")
                return web.Response(status=401, text="Invalid signature")

            # Parse webhook data
            data = json.loads(body)

            # Process the webhook event
            await self._process_webhook(data)

            return web.Response(status=200, text="OK")

        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook request")
            return web.Response(status=400, text="Invalid JSON")
        except Exception as e:
            logger.error(f"Webhook handler error: {e}")
            return web.Response(status=500, text="Internal error")

    async def _process_webhook(self, data: Dict[str, Any]) -> None:
        """
        Process Alchemy Address Activity webhook payload.

        Payload structure:
        {
            "webhookId": "...",
            "id": "...",
            "createdAt": "...",
            "type": "ADDRESS_ACTIVITY",
            "event": {
                "network": "MATIC_MAINNET",
                "activity": [
                    {
                        "fromAddress": "0x...",
                        "toAddress": "0x...",
                        "value": 100.5,
                        "asset": "USDC",
                        "category": "erc20",
                        "rawContract": {
                            "address": "0x...",
                            "decimals": 6
                        },
                        "hash": "0x..."
                    }
                ]
            }
        }
        """
        webhook_type = data.get("type")
        if webhook_type != "ADDRESS_ACTIVITY":
            logger.debug(f"Ignoring webhook type: {webhook_type}")
            return

        event = data.get("event", {})
        activities = event.get("activity", [])

        for activity in activities:
            await self._process_activity(activity)

    async def _process_activity(self, activity: Dict[str, Any]) -> None:
        """Process a single activity from the webhook."""
        try:
            # Only process ERC20 transfers
            category = activity.get("category", "").lower()
            if category not in ("erc20", "token"):
                return

            # Check if it's USDC
            raw_contract = activity.get("rawContract", {})
            contract_address = raw_contract.get("address", "").lower()

            if contract_address not in (USDC_ADDRESS.lower(), USDC_E_ADDRESS.lower()):
                return

            # Get transfer details
            to_address = activity.get("toAddress", "").lower()
            from_address = activity.get("fromAddress", "").lower()

            # Check if this is a deposit to one of our wallets
            if to_address not in self._wallet_addresses:
                return

            # Get amount (Alchemy provides it already formatted)
            amount = float(activity.get("value", 0))
            if amount <= 0:
                return

            tx_hash = activity.get("hash", "")

            logger.info(
                f"Deposit detected via webhook: {amount} USDC to {to_address[:10]}... "
                f"from {from_address[:10]}..."
            )

            # Process the deposit
            await self._notify_deposit(
                to_address=to_address,
                amount=amount,
                tx_hash=tx_hash,
            )

        except Exception as e:
            logger.error(f"Failed to process activity: {e}")

    async def _notify_deposit(
        self,
        to_address: str,
        amount: float,
        tx_hash: str,
    ) -> None:
        """Notify user of deposit."""
        try:
            wallet_repo = WalletRepository(self.db)
            user_repo = UserRepository(self.db)

            # Find wallet by address
            wallet = await wallet_repo.get_by_address(to_address)
            if not wallet:
                logger.warning(f"Wallet not found for deposit: {to_address}")
                return

            # Find user
            user = await user_repo.get_by_id(wallet.user_id)
            if not user:
                return

            # Notify user
            if self.bot_send_message:
                try:
                    message = (
                        f"💰 *Deposit Received!*\n\n"
                        f"💵 Amount: `${amount:.2f}` USDC\n"
                        f"🔗 TX: `{tx_hash[:16]}...`\n\n"
                        f"📈 You're ready to trade!"
                    )

                    await self.bot_send_message(
                        chat_id=user.telegram_id,
                        text=message,
                        parse_mode="Markdown",
                    )
                    logger.info(f"Notified user {user.telegram_id} of ${amount} deposit")
                except Exception as e:
                    logger.error(f"Failed to notify user {user.telegram_id}: {e}")

        except Exception as e:
            logger.error(f"Failed to process deposit notification: {e}")


def create_webhook_app(handler: AlchemyWebhookHandler) -> web.Application:
    """
    Create aiohttp application for webhook endpoint.

    Args:
        handler: AlchemyWebhookHandler instance

    Returns:
        aiohttp Application
    """
    app = web.Application()
    app.router.add_post("/webhook/alchemy", handler.handle_webhook)
    app.router.add_get("/health", lambda r: web.Response(text="OK"))
    return app

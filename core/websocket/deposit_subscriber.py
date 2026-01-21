"""Deposit subscriber for real-time USDC transfer detection via Alchemy WebSocket."""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, Callable, Set

import websockets

from database.connection import Database
from database.repositories import WalletRepository, UserRepository
from config.constants import USDC_ADDRESS, USDC_E_ADDRESS, USDC_DECIMALS, TRANSFER_EVENT_SIGNATURE, CLOB_CONTRACTS

logger = logging.getLogger(__name__)


class DepositSubscriber:
    """
    Subscribes to USDC Transfer events on Polygon via Alchemy WebSocket.

    Replaces the polling-based deposit_checker.py job with real-time notifications.
    Uses Alchemy's eth_subscribe with logs filter for efficient event detection.

    Note: This is the simplified version without auto-approvals.
    Approvals are handled lazily on first trade to minimize RPC usage.
    """

    RECONNECT_DELAY = 5.0
    MAX_RECONNECT_ATTEMPTS = 10

    def __init__(
        self,
        db: Database,
        alchemy_ws_url: str,
        bot_send_message: Optional[Callable] = None,
    ):
        self.db = db
        self.alchemy_ws_url = alchemy_ws_url
        self.bot_send_message = bot_send_message

        self._websocket = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0
        self._subscription_ids: list[str] = []

        # Track monitored wallet addresses (lowercase for comparison)
        self._wallet_addresses: Set[str] = set()

    async def start(self) -> None:
        """Start the deposit subscriber."""
        if self._running:
            return

        if not self.alchemy_ws_url:
            logger.warning("Alchemy WebSocket URL not configured, deposit subscriber disabled")
            return

        self._running = True
        await self._load_wallet_addresses()

        self._task = asyncio.create_task(
            self._connection_loop(),
            name="deposit_subscriber",
        )
        logger.info("Deposit subscriber started")

    async def stop(self) -> None:
        """Stop the deposit subscriber."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._websocket:
            await self._websocket.close()

        logger.info("Deposit subscriber stopped")

    async def add_wallet(self, address: str) -> None:
        """Add a wallet address to monitor for deposits."""
        normalized = address.lower()
        self._wallet_addresses.add(normalized)
        logger.debug(f"Added wallet to deposit monitoring: {address[:10]}...")

    async def remove_wallet(self, address: str) -> None:
        """Remove a wallet address from monitoring."""
        normalized = address.lower()
        self._wallet_addresses.discard(normalized)

    async def _load_wallet_addresses(self) -> None:
        """Load all wallet addresses from database."""
        try:
            wallet_repo = WalletRepository(self.db)
            addresses = await wallet_repo.get_all_addresses()

            self._wallet_addresses = {addr.lower() for addr in addresses}
            logger.info(f"Loaded {len(self._wallet_addresses)} wallet addresses for monitoring")

        except Exception as e:
            logger.error(f"Failed to load wallet addresses: {e}")

    async def _connection_loop(self) -> None:
        """Main connection loop with auto-reconnect."""
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Deposit subscriber connection error: {e}")

            if not self._running:
                break

            # Exponential backoff
            delay = min(
                self.RECONNECT_DELAY * (2 ** self._reconnect_attempts),
                60.0,
            )
            self._reconnect_attempts += 1

            if self._reconnect_attempts > self.MAX_RECONNECT_ATTEMPTS:
                logger.error("Max reconnect attempts reached for deposit subscriber")
                break

            logger.info(f"Reconnecting deposit subscriber in {delay:.1f}s")
            await asyncio.sleep(delay)

    async def _connect_and_listen(self) -> None:
        """Connect to Alchemy WebSocket and subscribe to events."""
        logger.info(f"Connecting to Alchemy WebSocket")

        async with websockets.connect(self.alchemy_ws_url) as websocket:
            self._websocket = websocket
            self._reconnect_attempts = 0
            logger.info("Connected to Alchemy WebSocket")

            # Subscribe to Transfer events for both USDC contracts
            await self._subscribe_to_transfers(websocket)

            # Listen for messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from Alchemy: {message[:100]}")
                except Exception as e:
                    logger.error(f"Error handling Alchemy message: {e}")

    async def _subscribe_to_transfers(self, websocket) -> None:
        """Subscribe to USDC Transfer events."""
        self._subscription_ids.clear()

        for usdc_address in [USDC_ADDRESS, USDC_E_ADDRESS]:
            # Build subscription request for Transfer events
            # Filter by Transfer event signature (topic0) on this contract
            subscription_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": [
                    "logs",
                    {
                        "address": usdc_address,
                        "topics": [TRANSFER_EVENT_SIGNATURE],
                    }
                ]
            }

            await websocket.send(json.dumps(subscription_request))
            logger.info(f"Subscribed to Transfer events on {usdc_address[:10]}...")

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket message."""
        # Handle subscription confirmation
        if "result" in data and isinstance(data["result"], str):
            self._subscription_ids.append(data["result"])
            logger.debug(f"Subscription confirmed: {data['result']}")
            return

        # Handle subscription events
        if data.get("method") == "eth_subscription":
            params = data.get("params", {})
            result = params.get("result", {})

            if result:
                await self._handle_transfer_event(result)

    async def _handle_transfer_event(self, event: Dict[str, Any]) -> None:
        """Process a Transfer event log."""
        try:
            topics = event.get("topics", [])
            data_hex = event.get("data", "0x")

            if len(topics) < 3:
                return

            # topics[0] = event signature (Transfer)
            # topics[1] = from address (indexed, padded to 32 bytes)
            # topics[2] = to address (indexed, padded to 32 bytes)
            from_address = self._decode_address(topics[1])
            to_address = self._decode_address(topics[2])

            # Check if this is a deposit to one of our wallets
            if to_address.lower() not in self._wallet_addresses:
                return

            # Ignore transfers from CLOB exchange contracts (these are sale proceeds, not deposits)
            exchange_addresses = {addr.lower() for addr in CLOB_CONTRACTS.values()}
            if from_address.lower() in exchange_addresses:
                logger.debug(f"Ignoring transfer from exchange contract {from_address[:10]}... (sale proceeds)")
                return

            # Decode amount from data (uint256)
            amount_wei = int(data_hex, 16)
            amount = amount_wei / (10 ** USDC_DECIMALS)

            # Ignore zero-value transfers (these are often approval transactions)
            if amount <= 0:
                logger.debug(f"Ignoring zero-value transfer to {to_address[:10]}...")
                return

            tx_hash = event.get("transactionHash", "")
            block_hex = event.get("blockNumber", "0x0")
            block_number = int(block_hex, 16)

            logger.info(
                f"Deposit detected: {amount} USDC to {to_address[:10]}... "
                f"from {from_address[:10]}... (tx: {tx_hash[:16]}...)"
            )

            # Process the deposit
            await self._process_deposit(
                to_address=to_address,
                amount=amount,
                tx_hash=tx_hash,
                block_number=block_number,
            )

        except Exception as e:
            logger.error(f"Failed to handle transfer event: {e}")

    def _decode_address(self, topic: str) -> str:
        """Decode an address from a 32-byte topic."""
        # Remove 0x prefix and take last 40 chars (20 bytes)
        if topic.startswith("0x"):
            topic = topic[2:]
        return "0x" + topic[-40:]

    async def _process_deposit(
        self,
        to_address: str,
        amount: float,
        tx_hash: str,
        block_number: int,
    ) -> None:
        """
        Process a detected deposit.

        Simply updates the balance and notifies the user.
        Approvals are handled lazily on first trade.
        """
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

            # Update wallet balance
            await wallet_repo.add_balance(wallet.id, amount)

            # Notify user
            if self.bot_send_message:
                try:
                    message = (
                        f"💰 *Deposit Received!*\n\n"
                        f"💵 Amount: `${amount:.2f}` USDC\n"
                        f"🔗 TX: `{tx_hash[:16]}...`\n\n"
                        f"✅ Your balance has been updated\\.\n"
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
            logger.error(f"Failed to process deposit: {e}")

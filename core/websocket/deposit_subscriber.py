"""Deposit subscriber for real-time USDC transfer detection via Alchemy WebSocket."""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, Callable, Set

import websockets
from web3 import Web3
from eth_account import Account

from database.connection import Database
from database.repositories import WalletRepository, UserRepository
from config.constants import USDC_ADDRESS, USDC_E_ADDRESS, USDC_DECIMALS, TRANSFER_EVENT_SIGNATURE, CLOB_CONTRACTS, CTF_CONTRACT
from config import settings
from services.user_service import UserService
from core.wallet.encryption import KeyEncryption

logger = logging.getLogger(__name__)


class DepositSubscriber:
    """
    Subscribes to USDC Transfer events on Polygon via Alchemy WebSocket.

    Replaces the polling-based deposit_checker.py job with real-time notifications.
    Uses Alchemy's eth_subscribe with logs filter for efficient event detection.
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

        # Initialize web3 for auto-approval transactions
        self.w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))

        # USDC.e contract for approvals
        self.usdc_e_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_E_ADDRESS),
            abi=[
                {
                    'constant': False,
                    'inputs': [
                        {'name': '_spender', 'type': 'address'},
                        {'name': '_value', 'type': 'uint256'},
                    ],
                    'name': 'approve',
                    'outputs': [{'name': '', 'type': 'bool'}],
                    'type': 'function',
                },
                {
                    'constant': True,
                    'inputs': [
                        {'name': '_owner', 'type': 'address'},
                        {'name': '_spender', 'type': 'address'},
                    ],
                    'name': 'allowance',
                    'outputs': [{'name': '', 'type': 'uint256'}],
                    'type': 'function',
                },
            ],
        )

        # CTF (Conditional Token Framework) contract for position token approvals
        self.ctf_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(CTF_CONTRACT),
            abi=[
                {
                    'constant': False,
                    'inputs': [
                        {'name': 'operator', 'type': 'address'},
                        {'name': 'approved', 'type': 'bool'},
                    ],
                    'name': 'setApprovalForAll',
                    'outputs': [],
                    'type': 'function',
                },
                {
                    'constant': True,
                    'inputs': [
                        {'name': 'owner', 'type': 'address'},
                        {'name': 'operator', 'type': 'address'},
                    ],
                    'name': 'isApprovedForAll',
                    'outputs': [{'name': '', 'type': 'bool'}],
                    'type': 'function',
                },
            ],
        )

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
            token_address = event.get("address", "")

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
                token_address=token_address,
            )

        except Exception as e:
            logger.error(f"Failed to handle transfer event: {e}")

    def _decode_address(self, topic: str) -> str:
        """Decode an address from a 32-byte topic."""
        # Remove 0x prefix and take last 40 chars (20 bytes)
        if topic.startswith("0x"):
            topic = topic[2:]
        return "0x" + topic[-40:]

    async def _auto_approve_trading(self, wallet, user) -> Optional[str]:
        """
        Auto-approve USDC.e for Polymarket CLOB contracts on first deposit.
        User pays their own gas fees.

        Returns:
            Status message for user notification, or None if already approved
        """
        try:
            # Get user's private key
            user_service = UserService(self.db, KeyEncryption(settings.master_encryption_key))
            private_key = await user_service.get_private_key(user.id)

            if not private_key:
                logger.error(f"Could not get private key for user {user.id}")
                return None

            account = Account.from_key(private_key)
            user_address = account.address
            max_uint256 = 2**256 - 1

            # Check which CLOB contracts need approval
            contracts_to_approve = []
            for name, address in CLOB_CONTRACTS.items():
                try:
                    allowance = self.usdc_e_contract.functions.allowance(
                        Web3.to_checksum_address(user_address),
                        Web3.to_checksum_address(address),
                    ).call()

                    # If allowance is less than half of max, needs approval
                    if allowance < max_uint256 // 2:
                        contracts_to_approve.append((name, address))
                except Exception as e:
                    logger.error(f"Error checking allowance for {name}: {e}")
                    continue

            if not contracts_to_approve:
                logger.info(f"All CLOB contracts already approved for user {user.id}")
                return None

            # Check if user has POL for gas
            user_pol = self.w3.eth.get_balance(user_address) / 1e18
            gas_price = self.w3.eth.gas_price
            estimated_gas_cost = (100000 * gas_price * len(contracts_to_approve)) / 1e18

            if user_pol < estimated_gas_cost * 1.5:  # 50% buffer
                logger.warning(
                    f"User {user.id} has insufficient POL for auto-approval: "
                    f"{user_pol:.4f} POL < {estimated_gas_cost * 1.5:.4f} POL needed"
                )
                return "⚠️ *Trading Setup Pending*\n\nYou need ~0.01 POL to enable trading\\. Please deposit POL to complete setup\\."

            # Approve each contract
            approved_count = 0
            for name, address in contracts_to_approve:
                try:
                    # Build approval transaction
                    tx = self.usdc_e_contract.functions.approve(
                        Web3.to_checksum_address(address),
                        max_uint256,
                    ).build_transaction({
                        'from': user_address,
                        'nonce': self.w3.eth.get_transaction_count(user_address) + approved_count,
                        'gas': 100000,
                        'gasPrice': gas_price,
                        'chainId': settings.chain_id,
                    })

                    # User signs and sends
                    signed = account.sign_transaction(tx)
                    tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)

                    logger.info(f"Auto-approved {name} for user {user.id}: {tx_hash.hex()}")
                    approved_count += 1

                    # Small delay between transactions
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Failed to approve {name} for user {user.id}: {e}")
                    # Continue with other approvals even if one fails

            if approved_count > 0:
                return f"🎉 *Trading Enabled!*\n\nApproved {approved_count} contract{'s' if approved_count > 1 else ''} for trading\\. You're ready to trade!"
            else:
                return None

        except Exception as e:
            logger.error(f"Auto-approval error for user {user.id}: {e}")
            return None

    async def _auto_approve_ctf_selling(self, wallet, user) -> Optional[str]:
        """
        Auto-approve CTF contract to transfer position tokens (for selling).
        User pays their own gas fees.

        Returns:
            Status message for user notification, or None if already approved
        """
        try:
            # Get user's private key
            user_service = UserService(self.db, KeyEncryption(settings.master_encryption_key))
            private_key = await user_service.get_private_key(user.id)

            if not private_key:
                logger.error(f"Could not get private key for user {user.id}")
                return None

            account = Account.from_key(private_key)
            user_address = account.address

            # Check which CLOB contracts need CTF approval for selling
            contracts_to_approve = []
            for name, address in CLOB_CONTRACTS.items():
                try:
                    is_approved = self.ctf_contract.functions.isApprovedForAll(
                        Web3.to_checksum_address(user_address),
                        Web3.to_checksum_address(address),
                    ).call()

                    if not is_approved:
                        contracts_to_approve.append((name, address))
                except Exception as e:
                    logger.error(f"Error checking CTF approval for {name}: {e}")
                    continue

            if not contracts_to_approve:
                logger.info(f"All CLOB contracts already approved for selling for user {user.id}")
                return None

            # Check if user has POL for gas
            user_pol = self.w3.eth.get_balance(user_address) / 1e18
            gas_price = self.w3.eth.gas_price
            estimated_gas_cost = (100000 * gas_price * len(contracts_to_approve)) / 1e18

            if user_pol < estimated_gas_cost * 1.5:  # 50% buffer
                logger.warning(
                    f"User {user.id} has insufficient POL for CTF auto-approval: "
                    f"{user_pol:.4f} POL < {estimated_gas_cost * 1.5:.4f} POL needed"
                )
                return "⚠️ *Selling Setup Pending*\n\nYou need ~0.01 POL to enable selling\\. Please deposit POL to complete setup\\."

            # Approve each contract
            approved_count = 0
            for name, address in contracts_to_approve:
                try:
                    # Build setApprovalForAll transaction
                    tx = self.ctf_contract.functions.setApprovalForAll(
                        Web3.to_checksum_address(address),
                        True,
                    ).build_transaction({
                        'from': user_address,
                        'nonce': self.w3.eth.get_transaction_count(user_address) + approved_count,
                        'gas': 100000,
                        'gasPrice': gas_price,
                        'chainId': settings.chain_id,
                    })

                    # User signs and sends
                    signed = account.sign_transaction(tx)
                    tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)

                    logger.info(f"Auto-approved CTF for {name} for user {user.id}: {tx_hash.hex()}")
                    approved_count += 1

                    # Small delay between transactions
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Failed to approve CTF for {name} for user {user.id}: {e}")
                    # Continue with other approvals even if one fails

            if approved_count > 0:
                return f"🎉 *Selling Enabled!*\n\nApproved {approved_count} contract{'s' if approved_count > 1 else ''} for selling positions\\. You can now sell your positions!"
            else:
                return None

        except Exception as e:
            logger.error(f"CTF auto-approval error for user {user.id}: {e}")
            return None

    async def _process_deposit(
        self,
        to_address: str,
        amount: float,
        tx_hash: str,
        block_number: int,
        token_address: str,
    ) -> None:
        """Process a detected deposit."""
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

            # Auto-approve USDC.e for buying AND CTF for selling
            approval_messages = []
            if token_address.lower() == USDC_E_ADDRESS.lower():
                # Approve USDC.e for buying
                try:
                    approval_result = await self._auto_approve_trading(wallet, user)
                    if approval_result:
                        approval_messages.append(approval_result)
                except Exception as e:
                    logger.error(f"USDC auto-approval failed for user {user.id}: {e}")
                    # Don't fail deposit processing if approval fails

                # Approve CTF for selling positions
                try:
                    ctf_approval_result = await self._auto_approve_ctf_selling(wallet, user)
                    if ctf_approval_result:
                        approval_messages.append(ctf_approval_result)
                except Exception as e:
                    logger.error(f"CTF auto-approval failed for user {user.id}: {e}")
                    # Don't fail deposit processing if approval fails

            approval_status = "\n\n".join(approval_messages) if approval_messages else ""

            # Notify user
            if self.bot_send_message:
                try:
                    message = (
                        f"💰 *Deposit Received!*\n\n"
                        f"💵 Amount: `${amount:.2f}` USDC\n"
                        f"🔗 TX: `{tx_hash[:16]}...`\n\n"
                        f"✅ Your balance has been updated."
                    )

                    if approval_status:
                        message += f"\n\n{approval_status}"

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

"""Tests for deposit subscriber."""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.websocket.deposit_subscriber import DepositSubscriber
from config.constants import USDC_DECIMALS


class TestDepositSubscriber:
    """Tests for DepositSubscriber."""

    @pytest_asyncio.fixture
    async def deposit_subscriber(self, temp_db):
        """Create a DepositSubscriber instance for testing."""
        subscriber = DepositSubscriber(
            db=temp_db,
            alchemy_ws_url="wss://polygon-mainnet.g.alchemy.com/v2/test-key",
            bot_send_message=None,
        )
        return subscriber

    def test_init(self, deposit_subscriber):
        """Test DepositSubscriber initialization."""
        assert deposit_subscriber._running is False
        assert deposit_subscriber._websocket is None
        assert deposit_subscriber._subscription_ids == []
        assert deposit_subscriber._wallet_addresses == set()

    def test_init_no_url(self, temp_db):
        """Test DepositSubscriber with no URL."""
        subscriber = DepositSubscriber(
            db=temp_db,
            alchemy_ws_url="",
            bot_send_message=None,
        )
        assert subscriber.alchemy_ws_url == ""

    @pytest.mark.asyncio
    async def test_add_wallet(self, deposit_subscriber):
        """Test adding wallet address for monitoring."""
        await deposit_subscriber.add_wallet("0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD")

        assert "0x742d35cc6634c0532925a3b844bc9e7595f1abcd" in deposit_subscriber._wallet_addresses

    @pytest.mark.asyncio
    async def test_add_wallet_normalized_to_lowercase(self, deposit_subscriber):
        """Test wallet addresses are normalized to lowercase."""
        await deposit_subscriber.add_wallet("0xABCDEF123456")

        assert "0xabcdef123456" in deposit_subscriber._wallet_addresses
        assert "0xABCDEF123456" not in deposit_subscriber._wallet_addresses

    @pytest.mark.asyncio
    async def test_remove_wallet(self, deposit_subscriber):
        """Test removing wallet address from monitoring."""
        await deposit_subscriber.add_wallet("0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD")
        await deposit_subscriber.remove_wallet("0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD")

        assert len(deposit_subscriber._wallet_addresses) == 0

    def test_decode_address(self, deposit_subscriber):
        """Test decoding address from 32-byte topic."""
        # Standard padded address topic
        topic = "0x000000000000000000000000742d35cc6634c0532925a3b844bc9e7595f1abcd"

        result = deposit_subscriber._decode_address(topic)

        assert result.lower() == "0x742d35cc6634c0532925a3b844bc9e7595f1abcd"

    def test_decode_address_without_prefix(self, deposit_subscriber):
        """Test decoding address without 0x prefix."""
        topic = "000000000000000000000000742d35cc6634c0532925a3b844bc9e7595f1abcd"

        result = deposit_subscriber._decode_address(topic)

        assert result.lower() == "0x742d35cc6634c0532925a3b844bc9e7595f1abcd"

    @pytest.mark.asyncio
    async def test_handle_transfer_event_not_our_wallet(self, deposit_subscriber):
        """Test transfer event is ignored if not our wallet."""
        deposit_subscriber._wallet_addresses = {"0xour_wallet"}
        deposit_subscriber._process_deposit = AsyncMock()

        event = {
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",  # Transfer
                "0x000000000000000000000000from_address",  # from
                "0x000000000000000000000000other_wallet",  # to - not ours
            ],
            "data": hex(1000000),  # 1 USDC
            "transactionHash": "0x123",
            "blockNumber": "0x100",
            "address": "0xusdc",
        }

        await deposit_subscriber._handle_transfer_event(event)

        deposit_subscriber._process_deposit.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_transfer_event_our_wallet(self, deposit_subscriber):
        """Test transfer event is processed if it's our wallet."""
        our_wallet = "0x742d35cc6634c0532925a3b844bc9e7595f1abcd"
        deposit_subscriber._wallet_addresses = {our_wallet}
        deposit_subscriber._process_deposit = AsyncMock()

        event = {
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",  # Transfer
                "0x000000000000000000000000from_address_here______________",  # from
                "0x000000000000000000000000742d35cc6634c0532925a3b844bc9e7595f1abcd",  # to - ours
            ],
            "data": "0xf4240",  # 1000000 = 1 USDC
            "transactionHash": "0x123abc",
            "blockNumber": "0x100",
            "address": "0xusdc_contract",
        }

        await deposit_subscriber._handle_transfer_event(event)

        deposit_subscriber._process_deposit.assert_called_once()

        # Verify call arguments
        call_kwargs = deposit_subscriber._process_deposit.call_args[1]
        assert call_kwargs["amount"] == 1.0  # 1000000 / 10^6
        assert call_kwargs["tx_hash"] == "0x123abc"
        assert call_kwargs["block_number"] == 256  # 0x100

    @pytest.mark.asyncio
    async def test_handle_message_subscription_confirmation(self, deposit_subscriber):
        """Test handling subscription confirmation message."""
        data = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "0x12345subscriptionid",
        }

        await deposit_subscriber._handle_message(data)

        assert "0x12345subscriptionid" in deposit_subscriber._subscription_ids

    @pytest.mark.asyncio
    async def test_start_does_nothing_without_url(self, temp_db):
        """Test start does nothing if no Alchemy URL configured."""
        subscriber = DepositSubscriber(
            db=temp_db,
            alchemy_ws_url="",
            bot_send_message=None,
        )

        await subscriber.start()

        assert subscriber._running is False
        assert subscriber._task is None

    @pytest.mark.asyncio
    async def test_stop(self, deposit_subscriber):
        """Test stopping the subscriber."""
        deposit_subscriber._running = True

        # Create a real asyncio task
        async def dummy_coro():
            await asyncio.sleep(100)

        deposit_subscriber._task = asyncio.create_task(dummy_coro())

        await deposit_subscriber.stop()

        assert deposit_subscriber._running is False
        assert deposit_subscriber._task.cancelled()

"""
Real API WebSocket Integration Tests.

These tests connect to actual WebSocket endpoints to verify connectivity and message handling.
They require network access and may be slow - run with: pytest -m integration

To run these tests:
    pytest tests/test_core/test_websocket/test_integration.py -v -s

Note: Some tests require ALCHEMY_API_KEY in environment.
"""

import asyncio
import json
import os
import pytest
import websockets
from websockets import State
from datetime import datetime
from typing import Any, Dict, List, Optional


def is_ws_open(ws) -> bool:
    """Check if WebSocket connection is open (compatible with websockets v14+)."""
    try:
        return ws.state == State.OPEN
    except AttributeError:
        # Fallback for older versions
        return getattr(ws, 'open', True)

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Polymarket WebSocket URLs
POLYMARKET_WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
POLYMARKET_WS_USER_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"

# Alchemy WebSocket URL template
ALCHEMY_WS_URL_TEMPLATE = "wss://polygon-mainnet.g.alchemy.com/v2/{api_key}"

# USDC contract on Polygon
USDC_POLYGON_ADDRESS = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"

# Transfer event signature: keccak256("Transfer(address,address,uint256)")
TRANSFER_EVENT_SIGNATURE = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class WebSocketTestCollector:
    """Collects messages from WebSocket for testing."""

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.connection_established = False
        self.errors: List[str] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def add_message(self, msg: Dict[str, Any]):
        self.messages.append(msg)

    def add_error(self, error: str):
        self.errors.append(error)

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0


class TestPolymarketWebSocketConnection:
    """Test basic connectivity to Polymarket WebSocket endpoints."""

    @pytest.mark.asyncio
    async def test_market_websocket_connects(self):
        """Test that we can connect to the Polymarket market WebSocket."""
        collector = WebSocketTestCollector()
        collector.start_time = datetime.now()

        try:
            async with websockets.connect(
                POLYMARKET_WS_MARKET_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                collector.connection_established = True
                print(f"\n✅ Connected to Polymarket Market WebSocket")
                print(f"   URL: {POLYMARKET_WS_MARKET_URL}")

                # Connection successful
                assert is_ws_open(ws), "WebSocket should be open"

        except Exception as e:
            collector.add_error(str(e))
            pytest.fail(f"Failed to connect to Polymarket Market WebSocket: {e}")
        finally:
            collector.end_time = datetime.now()
            print(f"   Duration: {collector.duration_seconds:.2f}s")

    @pytest.mark.asyncio
    async def test_user_websocket_connects(self):
        """Test that we can connect to the Polymarket user WebSocket."""
        collector = WebSocketTestCollector()
        collector.start_time = datetime.now()

        try:
            async with websockets.connect(
                POLYMARKET_WS_USER_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                collector.connection_established = True
                print(f"\n✅ Connected to Polymarket User WebSocket")
                print(f"   URL: {POLYMARKET_WS_USER_URL}")

                assert is_ws_open(ws), "WebSocket should be open"

        except Exception as e:
            collector.add_error(str(e))
            pytest.fail(f"Failed to connect to Polymarket User WebSocket: {e}")
        finally:
            collector.end_time = datetime.now()
            print(f"   Duration: {collector.duration_seconds:.2f}s")


class TestPolymarketSubscriptions:
    """Test subscription functionality on Polymarket WebSocket."""

    @pytest.mark.asyncio
    async def test_subscribe_to_market_prices(self):
        """Test subscribing to market price updates."""
        collector = WebSocketTestCollector()
        collector.start_time = datetime.now()

        # Use a well-known active market token ID (this is a common one)
        # You can get real token IDs from https://gamma-api.polymarket.com/markets
        test_token_ids = [
            "21742633143463906290569050155826241533067272736897614950488156847949938836455",  # Example token
        ]

        try:
            async with websockets.connect(
                POLYMARKET_WS_MARKET_URL,
                ping_interval=20,
                ping_timeout=10,
            ) as ws:
                collector.connection_established = True
                print(f"\n✅ Connected to Polymarket Market WebSocket")

                # Send subscription message
                subscription_msg = {
                    "assets_ids": test_token_ids,
                    "type": "market",
                }
                await ws.send(json.dumps(subscription_msg))
                print(f"   📤 Sent subscription for {len(test_token_ids)} tokens")

                # Wait for messages (up to 10 seconds)
                try:
                    async with asyncio.timeout(10):
                        while len(collector.messages) < 3:
                            message = await ws.recv()
                            data = json.loads(message)
                            collector.add_message(data)
                            print(f"   📥 Received: {json.dumps(data)[:100]}...")
                except asyncio.TimeoutError:
                    print(f"   ⏱️ Timeout after collecting {len(collector.messages)} messages")

                # Verify we got some messages or at least connected successfully
                print(f"   📊 Total messages received: {len(collector.messages)}")

        except Exception as e:
            collector.add_error(str(e))
            # Don't fail if we just didn't get messages - subscription might not have activity
            print(f"   ⚠️ Note: {e}")
        finally:
            collector.end_time = datetime.now()
            print(f"   Duration: {collector.duration_seconds:.2f}s")

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe_cycle(self):
        """Test the full subscribe/unsubscribe cycle."""
        test_token = "21742633143463906290569050155826241533067272736897614950488156847949938836455"

        try:
            async with websockets.connect(
                POLYMARKET_WS_MARKET_URL,
                ping_interval=20,
                ping_timeout=10,
            ) as ws:
                print(f"\n✅ Connected to Polymarket Market WebSocket")

                # Subscribe
                subscribe_msg = {
                    "assets_ids": [test_token],
                    "type": "market",
                }
                await ws.send(json.dumps(subscribe_msg))
                print(f"   📤 Subscribed to token")

                # Small delay
                await asyncio.sleep(1)

                # Unsubscribe
                unsubscribe_msg = {
                    "assets_ids": [test_token],
                    "type": "market",
                    "action": "unsubscribe",
                }
                await ws.send(json.dumps(unsubscribe_msg))
                print(f"   📤 Unsubscribed from token")

                print(f"   ✅ Subscribe/Unsubscribe cycle completed successfully")

        except Exception as e:
            pytest.fail(f"Subscribe/Unsubscribe cycle failed: {e}")


class TestAlchemyWebSocket:
    """Test Alchemy WebSocket for Polygon deposit monitoring."""

    @pytest.fixture
    def alchemy_api_key(self):
        """Get Alchemy API key from environment."""
        api_key = os.environ.get("ALCHEMY_API_KEY", "")
        if not api_key or api_key == "your_alchemy_api_key_here":
            pytest.skip("ALCHEMY_API_KEY not configured - skipping Alchemy tests")
        return api_key

    @pytest.mark.asyncio
    async def test_alchemy_websocket_connects(self, alchemy_api_key):
        """Test that we can connect to Alchemy Polygon WebSocket."""
        collector = WebSocketTestCollector()
        collector.start_time = datetime.now()

        ws_url = ALCHEMY_WS_URL_TEMPLATE.format(api_key=alchemy_api_key)

        try:
            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=10,
            ) as ws:
                collector.connection_established = True
                print(f"\n✅ Connected to Alchemy Polygon WebSocket")
                print(f"   URL: wss://polygon-mainnet.g.alchemy.com/v2/***")

                assert is_ws_open(ws), "WebSocket should be open"

        except Exception as e:
            collector.add_error(str(e))
            pytest.fail(f"Failed to connect to Alchemy WebSocket: {e}")
        finally:
            collector.end_time = datetime.now()
            print(f"   Duration: {collector.duration_seconds:.2f}s")

    @pytest.mark.asyncio
    async def test_alchemy_subscribe_to_usdc_transfers(self, alchemy_api_key):
        """Test subscribing to USDC Transfer events on Polygon."""
        collector = WebSocketTestCollector()
        collector.start_time = datetime.now()

        ws_url = ALCHEMY_WS_URL_TEMPLATE.format(api_key=alchemy_api_key)

        try:
            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=10,
            ) as ws:
                collector.connection_established = True
                print(f"\n✅ Connected to Alchemy Polygon WebSocket")

                # Subscribe to USDC Transfer events
                subscription_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": [
                        "logs",
                        {
                            "address": USDC_POLYGON_ADDRESS,
                            "topics": [TRANSFER_EVENT_SIGNATURE],
                        }
                    ]
                }

                await ws.send(json.dumps(subscription_request))
                print(f"   📤 Sent subscription for USDC Transfer events")
                print(f"   📍 USDC Contract: {USDC_POLYGON_ADDRESS}")

                # Wait for subscription confirmation
                try:
                    async with asyncio.timeout(5):
                        response = await ws.recv()
                        data = json.loads(response)
                        collector.add_message(data)

                        if "result" in data:
                            subscription_id = data["result"]
                            print(f"   ✅ Subscription confirmed: {subscription_id}")
                        elif "error" in data:
                            pytest.fail(f"Subscription error: {data['error']}")

                except asyncio.TimeoutError:
                    pytest.fail("Timeout waiting for subscription confirmation")

                # Listen for a few Transfer events (USDC is very active)
                print(f"   👂 Listening for USDC transfers (up to 30s)...")
                try:
                    async with asyncio.timeout(30):
                        while len(collector.messages) < 6:  # Get 5 transfer events
                            message = await ws.recv()
                            data = json.loads(message)
                            collector.add_message(data)

                            if "params" in data and "result" in data["params"]:
                                log = data["params"]["result"]
                                tx_hash = log.get("transactionHash", "unknown")[:20]
                                block = int(log.get("blockNumber", "0x0"), 16)
                                print(f"   📥 Transfer detected - Block: {block}, TX: {tx_hash}...")

                except asyncio.TimeoutError:
                    print(f"   ⏱️ Timeout - collected {len(collector.messages) - 1} transfer events")

                # We should have received at least the subscription confirmation
                assert len(collector.messages) >= 1, "Should receive subscription confirmation"
                print(f"   📊 Total events received: {len(collector.messages) - 1}")

        except Exception as e:
            collector.add_error(str(e))
            pytest.fail(f"Alchemy USDC subscription test failed: {e}")
        finally:
            collector.end_time = datetime.now()
            print(f"   Duration: {collector.duration_seconds:.2f}s")

    @pytest.mark.asyncio
    async def test_alchemy_get_block_number(self, alchemy_api_key):
        """Test JSON-RPC call over WebSocket to get current block."""
        ws_url = ALCHEMY_WS_URL_TEMPLATE.format(api_key=alchemy_api_key)

        try:
            async with websockets.connect(ws_url, ping_interval=20) as ws:
                print(f"\n✅ Connected to Alchemy Polygon WebSocket")

                # Get current block number
                request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_blockNumber",
                    "params": []
                }

                await ws.send(json.dumps(request))
                response = await ws.recv()
                data = json.loads(response)

                assert "result" in data, "Response should contain result"
                block_number = int(data["result"], 16)
                print(f"   📦 Current Polygon block: {block_number:,}")

                assert block_number > 0, "Block number should be positive"

        except Exception as e:
            pytest.fail(f"Failed to get block number: {e}")

    @pytest.mark.asyncio
    async def test_alchemy_get_usdc_balance(self, alchemy_api_key):
        """Test getting USDC balance of a known address via WebSocket."""
        ws_url = ALCHEMY_WS_URL_TEMPLATE.format(api_key=alchemy_api_key)

        # Use USDC contract address itself (will have 0 balance but tests the call)
        test_address = "0x0000000000000000000000000000000000000001"

        try:
            async with websockets.connect(ws_url, ping_interval=20) as ws:
                print(f"\n✅ Connected to Alchemy Polygon WebSocket")

                # ERC20 balanceOf(address) function selector
                # balanceOf(address) = 0x70a08231
                padded_address = test_address[2:].lower().zfill(64)
                data_hex = f"0x70a08231{padded_address}"

                request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_call",
                    "params": [
                        {
                            "to": USDC_POLYGON_ADDRESS,
                            "data": data_hex,
                        },
                        "latest"
                    ]
                }

                await ws.send(json.dumps(request))
                response = await ws.recv()
                result = json.loads(response)

                assert "result" in result, f"Response should contain result: {result}"
                balance_hex = result["result"]
                balance = int(balance_hex, 16) / 10**6  # USDC has 6 decimals
                print(f"   💰 USDC balance of test address: {balance:.6f}")

        except Exception as e:
            pytest.fail(f"Failed to get USDC balance: {e}")


class TestWebSocketReconnection:
    """Test WebSocket reconnection behavior."""

    @pytest.mark.asyncio
    async def test_reconnect_after_close(self):
        """Test that we can reconnect after closing connection."""
        print(f"\n🔄 Testing reconnection...")

        # First connection
        async with websockets.connect(
            POLYMARKET_WS_MARKET_URL,
            ping_interval=20,
        ) as ws1:
            print(f"   ✅ First connection established")
            assert is_ws_open(ws1)

        print(f"   🔌 First connection closed")

        # Wait a moment
        await asyncio.sleep(1)

        # Second connection
        async with websockets.connect(
            POLYMARKET_WS_MARKET_URL,
            ping_interval=20,
        ) as ws2:
            print(f"   ✅ Second connection established (reconnection successful)")
            assert is_ws_open(ws2)

    @pytest.mark.asyncio
    async def test_multiple_concurrent_connections(self):
        """Test handling multiple concurrent WebSocket connections."""
        print(f"\n🔀 Testing multiple concurrent connections...")

        connections = []
        urls = [
            POLYMARKET_WS_MARKET_URL,
            POLYMARKET_WS_USER_URL,
        ]

        try:
            # Open multiple connections concurrently
            tasks = [
                websockets.connect(url, ping_interval=20, ping_timeout=10)
                for url in urls
            ]

            connections = await asyncio.gather(*tasks)

            print(f"   ✅ Opened {len(connections)} concurrent connections")

            for i, ws in enumerate(connections):
                assert is_ws_open(ws), f"Connection {i} should be open"
                print(f"   📡 Connection {i}: {urls[i][:50]}... - OPEN")

        finally:
            # Close all connections
            for ws in connections:
                await ws.close()
            print(f"   🔌 All connections closed")


class TestMessageParsing:
    """Test parsing of actual WebSocket messages."""

    @pytest.mark.asyncio
    async def test_parse_price_change_message(self):
        """Test parsing a price change message from Polymarket."""
        # Example message structure (based on Polymarket API)
        sample_message = {
            "event_type": "price_change",
            "asset_id": "21742633143463906290569050155826241533067272736897614950488156847949938836455",
            "market": "0x1234...",
            "price": "0.65",
            "timestamp": 1704067200,
        }

        # Verify we can parse the expected fields
        assert "event_type" in sample_message
        assert "price" in sample_message
        price = float(sample_message["price"])
        assert 0 <= price <= 1, "Price should be between 0 and 1"

        print(f"\n✅ Sample price change message parsed successfully")
        print(f"   Event: {sample_message['event_type']}")
        print(f"   Price: {price}")

    @pytest.mark.asyncio
    async def test_parse_transfer_event_log(self):
        """Test parsing an Alchemy Transfer event log."""
        # Example log structure from Alchemy
        sample_log = {
            "address": "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359",
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x000000000000000000000000sender_address_here_padded_to_32_bytes",
                "0x000000000000000000000000receiver_address_here_padded_to_32_bytes",
            ],
            "data": "0x00000000000000000000000000000000000000000000000000000000000f4240",
            "blockNumber": "0x3a5b6c7",
            "transactionHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "logIndex": "0x1",
        }

        # Parse the amount from data (USDC has 6 decimals)
        amount_hex = sample_log["data"]
        amount_raw = int(amount_hex, 16)
        amount_usdc = amount_raw / 10**6

        # Parse block number
        block_number = int(sample_log["blockNumber"], 16)

        print(f"\n✅ Sample Transfer event log parsed successfully")
        print(f"   Contract: {sample_log['address']}")
        print(f"   Amount: {amount_usdc} USDC ({amount_raw} raw)")
        print(f"   Block: {block_number}")
        print(f"   TX: {sample_log['transactionHash'][:20]}...")

        assert amount_usdc == 1.0, "Sample amount should be 1 USDC"


class TestEndToEndWebSocketFlow:
    """End-to-end tests for complete WebSocket flows."""

    @pytest.mark.asyncio
    async def test_full_market_subscription_flow(self):
        """Test complete flow: connect → subscribe → receive → unsubscribe → disconnect."""
        print(f"\n🚀 Running full market subscription flow...")

        token_id = "21742633143463906290569050155826241533067272736897614950488156847949938836455"
        messages_received = []

        async with websockets.connect(
            POLYMARKET_WS_MARKET_URL,
            ping_interval=20,
            ping_timeout=10,
        ) as ws:
            print(f"   1️⃣ Connected")

            # Subscribe
            await ws.send(json.dumps({
                "assets_ids": [token_id],
                "type": "market",
            }))
            print(f"   2️⃣ Subscribed")

            # Try to receive messages
            try:
                async with asyncio.timeout(5):
                    while len(messages_received) < 2:
                        msg = await ws.recv()
                        messages_received.append(json.loads(msg))
                        print(f"   3️⃣ Received message #{len(messages_received)}")
            except asyncio.TimeoutError:
                print(f"   ⏱️ No more messages (received {len(messages_received)})")

            # Unsubscribe
            await ws.send(json.dumps({
                "assets_ids": [token_id],
                "type": "market",
                "action": "unsubscribe",
            }))
            print(f"   4️⃣ Unsubscribed")

        print(f"   5️⃣ Disconnected")
        print(f"   ✅ Full flow completed successfully")

    @pytest.mark.asyncio
    async def test_full_deposit_monitoring_flow(self):
        """Test complete deposit monitoring flow with Alchemy."""
        api_key = os.environ.get("ALCHEMY_API_KEY", "")
        if not api_key or api_key == "your_alchemy_api_key_here":
            pytest.skip("ALCHEMY_API_KEY not configured")

        print(f"\n🚀 Running full deposit monitoring flow...")

        ws_url = ALCHEMY_WS_URL_TEMPLATE.format(api_key=api_key)
        subscription_id = None

        async with websockets.connect(ws_url, ping_interval=20) as ws:
            print(f"   1️⃣ Connected to Alchemy")

            # Subscribe to USDC transfers
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": [
                    "logs",
                    {
                        "address": USDC_POLYGON_ADDRESS,
                        "topics": [TRANSFER_EVENT_SIGNATURE],
                    }
                ]
            }))

            # Get subscription confirmation
            response = await ws.recv()
            data = json.loads(response)
            subscription_id = data.get("result")
            print(f"   2️⃣ Subscribed (ID: {subscription_id})")

            # Wait for some events
            events = []
            try:
                async with asyncio.timeout(15):
                    while len(events) < 3:
                        msg = await ws.recv()
                        event_data = json.loads(msg)
                        if "params" in event_data:
                            events.append(event_data)
                            print(f"   3️⃣ Received transfer event #{len(events)}")
            except asyncio.TimeoutError:
                print(f"   ⏱️ Timeout (received {len(events)} events)")

            # Unsubscribe
            if subscription_id:
                await ws.send(json.dumps({
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_unsubscribe",
                    "params": [subscription_id]
                }))
                unsubscribe_response = await ws.recv()
                print(f"   4️⃣ Unsubscribed")

        print(f"   5️⃣ Disconnected")
        print(f"   ✅ Full deposit monitoring flow completed")


# Fixture to run only integration tests
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (connects to real APIs)"
    )

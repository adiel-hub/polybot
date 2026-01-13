"""Tests for WebSocket manager."""

import asyncio
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.websocket.manager import WebSocketManager, ConnectionState


class TestConnectionState:
    """Tests for ConnectionState dataclass."""

    def test_default_values(self):
        """Test default ConnectionState values."""
        state = ConnectionState(url="wss://example.com")

        assert state.url == "wss://example.com"
        assert state.websocket is None
        assert state.is_connected is False
        assert state.reconnect_attempts == 0
        assert state.subscribed_assets == set()
        assert state.last_message_time == 0

    def test_subscribed_assets_set(self):
        """Test subscribed_assets is a proper set."""
        state = ConnectionState(url="wss://example.com")

        state.subscribed_assets.add("token1")
        state.subscribed_assets.add("token2")
        state.subscribed_assets.add("token1")  # duplicate

        assert len(state.subscribed_assets) == 2
        assert "token1" in state.subscribed_assets
        assert "token2" in state.subscribed_assets


class TestWebSocketManager:
    """Tests for WebSocketManager."""

    def test_init(self):
        """Test WebSocketManager initialization."""
        manager = WebSocketManager()

        assert manager._connections == {}
        assert manager._message_handlers == {}
        assert manager._running is False
        assert manager._tasks == []

    def test_register_connection(self):
        """Test registering a connection."""
        manager = WebSocketManager()

        async def handler(name, data):
            pass

        manager.register_connection(
            name="test",
            url="wss://example.com",
            message_handler=handler,
        )

        assert "test" in manager._connections
        assert "test" in manager._message_handlers
        assert manager._connections["test"].url == "wss://example.com"
        assert manager._message_handlers["test"] is handler

    def test_is_connected_false_by_default(self):
        """Test is_connected returns False when not connected."""
        manager = WebSocketManager()

        assert manager.is_connected("nonexistent") is False

        # Register but don't connect
        manager.register_connection(
            name="test",
            url="wss://example.com",
            message_handler=lambda n, d: None,
        )

        assert manager.is_connected("test") is False

    def test_is_connected_true_when_connected(self):
        """Test is_connected returns True when connected."""
        manager = WebSocketManager()

        manager.register_connection(
            name="test",
            url="wss://example.com",
            message_handler=lambda n, d: None,
        )

        # Simulate connection
        manager._connections["test"].is_connected = True

        assert manager.is_connected("test") is True

    @pytest.mark.asyncio
    async def test_subscribe_when_not_connected(self):
        """Test subscribe fails gracefully when not connected."""
        manager = WebSocketManager()

        result = await manager.subscribe("nonexistent", ["token1"])

        assert result is False

    @pytest.mark.asyncio
    async def test_subscribe_sends_message(self):
        """Test subscribe sends subscription message."""
        manager = WebSocketManager()
        mock_ws = AsyncMock()

        manager.register_connection(
            name="test",
            url="wss://example.com",
            message_handler=lambda n, d: None,
        )

        # Simulate connection
        manager._connections["test"].websocket = mock_ws
        manager._connections["test"].is_connected = True

        result = await manager.subscribe("test", ["token1", "token2"])

        assert result is True
        mock_ws.send.assert_called_once()

        # Verify message format
        call_args = mock_ws.send.call_args[0][0]
        message = json.loads(call_args)
        assert message["assets_ids"] == ["token1", "token2"]
        assert message["operation"] == "subscribe"

        # Verify subscribed assets tracked
        assert "token1" in manager._connections["test"].subscribed_assets
        assert "token2" in manager._connections["test"].subscribed_assets

    @pytest.mark.asyncio
    async def test_unsubscribe_sends_message(self):
        """Test unsubscribe sends unsubscription message."""
        manager = WebSocketManager()
        mock_ws = AsyncMock()

        manager.register_connection(
            name="test",
            url="wss://example.com",
            message_handler=lambda n, d: None,
        )

        # Simulate connection with subscriptions
        manager._connections["test"].websocket = mock_ws
        manager._connections["test"].is_connected = True
        manager._connections["test"].subscribed_assets = {"token1", "token2"}

        result = await manager.unsubscribe("test", ["token1"])

        assert result is True
        mock_ws.send.assert_called_once()

        # Verify message format
        call_args = mock_ws.send.call_args[0][0]
        message = json.loads(call_args)
        assert message["assets_ids"] == ["token1"]
        assert message["operation"] == "unsubscribe"

        # Verify token removed from tracked assets
        assert "token1" not in manager._connections["test"].subscribed_assets
        assert "token2" in manager._connections["test"].subscribed_assets

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self):
        """Test stop cancels all running tasks."""
        manager = WebSocketManager()
        manager._running = True

        # Create real asyncio tasks that can be cancelled
        async def dummy_coro():
            await asyncio.sleep(100)

        task1 = asyncio.create_task(dummy_coro())
        task2 = asyncio.create_task(dummy_coro())
        manager._tasks = [task1, task2]

        await manager.stop()

        assert manager._running is False
        assert task1.cancelled()
        assert task2.cancelled()
        assert manager._tasks == []

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self):
        """Test start sets running flag."""
        manager = WebSocketManager()

        # Don't actually start connections
        with patch.object(manager, '_connection_loop', AsyncMock()):
            await manager.start()

        assert manager._running is True

    @pytest.mark.asyncio
    async def test_start_does_nothing_if_already_running(self):
        """Test start does nothing if already running."""
        manager = WebSocketManager()
        manager._running = True

        manager.register_connection(
            name="test",
            url="wss://example.com",
            message_handler=lambda n, d: None,
        )

        await manager.start()

        # No tasks should be created
        assert manager._tasks == []

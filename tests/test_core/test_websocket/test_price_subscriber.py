"""Tests for price subscriber."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.websocket.price_subscriber import PriceSubscriber, EVENT_PRICE_CHANGE


class TestPriceSubscriber:
    """Tests for PriceSubscriber."""

    @pytest_asyncio.fixture
    async def price_subscriber(self, temp_db, key_encryption):
        """Create a PriceSubscriber instance for testing."""
        mock_ws_manager = MagicMock()
        mock_ws_manager.register_connection = MagicMock()
        mock_ws_manager.is_connected = MagicMock(return_value=False)
        mock_ws_manager.subscribe = AsyncMock()

        subscriber = PriceSubscriber(
            ws_manager=mock_ws_manager,
            db=temp_db,
            encryption=key_encryption,
            market_ws_url="wss://test.polymarket.com/ws/market",
            bot_send_message=None,
        )

        return subscriber

    @pytest.mark.asyncio
    async def test_init(self, price_subscriber):
        """Test PriceSubscriber initialization."""
        assert price_subscriber._token_prices == {}
        assert price_subscriber._active_stop_losses == {}
        assert price_subscriber._monitored_positions == set()

    @pytest.mark.asyncio
    async def test_start_registers_connection(self, price_subscriber):
        """Test start registers with WebSocket manager."""
        await price_subscriber.start()

        price_subscriber.ws_manager.register_connection.assert_called_once_with(
            name="polymarket_market",
            url="wss://test.polymarket.com/ws/market",
            message_handler=price_subscriber._handle_market_message,
        )

    @pytest.mark.asyncio
    async def test_handle_price_update_caches_price(self, price_subscriber):
        """Test price updates are cached."""
        data = {
            "event_type": EVENT_PRICE_CHANGE,
            "asset_id": "token123",
            "price": "0.65",
        }

        await price_subscriber._handle_price_update(data)

        assert price_subscriber._token_prices["token123"] == 0.65

    @pytest.mark.asyncio
    async def test_handle_price_update_invalid_data(self, price_subscriber):
        """Test price update handles invalid data gracefully."""
        # Missing token_id
        data1 = {"event_type": EVENT_PRICE_CHANGE, "price": "0.65"}
        await price_subscriber._handle_price_update(data1)
        assert len(price_subscriber._token_prices) == 0

        # Missing price
        data2 = {"event_type": EVENT_PRICE_CHANGE, "asset_id": "token123"}
        await price_subscriber._handle_price_update(data2)
        assert len(price_subscriber._token_prices) == 0

        # Invalid price format
        data3 = {"event_type": EVENT_PRICE_CHANGE, "asset_id": "token123", "price": "invalid"}
        await price_subscriber._handle_price_update(data3)
        assert len(price_subscriber._token_prices) == 0

    @pytest.mark.asyncio
    async def test_add_stop_loss(self, price_subscriber):
        """Test adding stop loss to monitoring."""
        # Create mock stop loss
        mock_sl = MagicMock()
        mock_sl.id = 1
        mock_sl.user_id = 100
        mock_sl.position_id = 200
        mock_sl.token_id = "token123"
        mock_sl.trigger_price = 0.50
        mock_sl.sell_percentage = 100.0

        await price_subscriber.add_stop_loss(mock_sl)

        assert "token123" in price_subscriber._active_stop_losses
        assert len(price_subscriber._active_stop_losses["token123"]) == 1
        assert price_subscriber._active_stop_losses["token123"][0]["id"] == 1
        assert price_subscriber._active_stop_losses["token123"][0]["trigger_price"] == 0.50

    @pytest.mark.asyncio
    async def test_remove_stop_loss(self, price_subscriber):
        """Test removing stop loss from monitoring."""
        # Add a stop loss first
        mock_sl = MagicMock()
        mock_sl.id = 1
        mock_sl.user_id = 100
        mock_sl.position_id = 200
        mock_sl.token_id = "token123"
        mock_sl.trigger_price = 0.50
        mock_sl.sell_percentage = 100.0

        await price_subscriber.add_stop_loss(mock_sl)
        assert len(price_subscriber._active_stop_losses["token123"]) == 1

        # Remove it
        await price_subscriber.remove_stop_loss(1)

        assert len(price_subscriber._active_stop_losses["token123"]) == 0

    @pytest.mark.asyncio
    async def test_add_position(self, price_subscriber):
        """Test adding position for price monitoring."""
        mock_position = MagicMock()
        mock_position.token_id = "token456"

        await price_subscriber.add_position(mock_position)

        assert "token456" in price_subscriber._monitored_positions

    @pytest.mark.asyncio
    async def test_check_stop_losses_triggers_when_price_drops(self, price_subscriber, temp_db):
        """Test stop loss triggers when price drops below threshold."""
        # Setup - add a stop loss
        price_subscriber._active_stop_losses["token123"] = [{
            "id": 1,
            "user_id": 100,
            "position_id": 200,
            "token_id": "token123",
            "trigger_price": 0.50,
            "sell_percentage": 100.0,
        }]

        # Mock the trigger function
        price_subscriber._trigger_stop_loss = AsyncMock()

        # Price drops below trigger
        await price_subscriber._check_stop_losses("token123", 0.45)

        # Should trigger
        price_subscriber._trigger_stop_loss.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_stop_losses_no_trigger_above_threshold(self, price_subscriber):
        """Test stop loss does not trigger when price is above threshold."""
        # Setup - add a stop loss
        price_subscriber._active_stop_losses["token123"] = [{
            "id": 1,
            "user_id": 100,
            "position_id": 200,
            "token_id": "token123",
            "trigger_price": 0.50,
            "sell_percentage": 100.0,
        }]

        # Mock the trigger function
        price_subscriber._trigger_stop_loss = AsyncMock()

        # Price above trigger
        await price_subscriber._check_stop_losses("token123", 0.55)

        # Should not trigger
        price_subscriber._trigger_stop_loss.assert_not_called()

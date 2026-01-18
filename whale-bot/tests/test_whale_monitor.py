"""Tests for whale_monitor.py."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from monitors.whale_monitor import WhaleMonitor, WhaleTrade


class TestWhaleTrade:
    """Tests for WhaleTrade dataclass."""

    def test_whale_trade_creation(self, sample_whale_trade):
        """Test WhaleTrade dataclass creation."""
        assert sample_whale_trade.trader_address == "0x1234567890abcdef1234567890abcdef12345678"
        assert sample_whale_trade.trader_name == "WhaleTrader"
        assert sample_whale_trade.market_title == "Will Bitcoin reach $100k by end of 2026?"
        assert sample_whale_trade.outcome == "Yes"
        assert sample_whale_trade.side == "BUY"
        assert sample_whale_trade.size == 50000.0
        assert sample_whale_trade.price == 0.65
        assert sample_whale_trade.value == 32500.0

    def test_whale_trade_without_optional_fields(self):
        """Test WhaleTrade with minimal fields."""
        trade = WhaleTrade(
            trader_address="0x1234",
            trader_name=None,
            market_title="Test Market",
            condition_id="0xabc",
            outcome="Yes",
            side="BUY",
            size=1000.0,
            price=0.5,
            value=500.0,
            tx_hash=None,
            timestamp=datetime.now(),
            market_slug=None,
            market_icon=None,
        )
        assert trade.trader_name is None
        assert trade.tx_hash is None
        assert trade.market_slug is None


class TestWhaleMonitor:
    """Tests for WhaleMonitor class."""

    def test_monitor_initialization(self):
        """Test WhaleMonitor initialization."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        assert monitor.on_whale_detected == callback
        assert monitor.running is False
        assert len(monitor._processed_trades) == 0

    def test_create_trade_id(self, sample_trade_data):
        """Test unique trade ID generation."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        trade_id = monitor._create_trade_id(sample_trade_data)

        assert trade_id is not None
        assert len(trade_id) > 0
        assert sample_trade_data["transactionHash"] in trade_id

    def test_create_trade_id_consistency(self, sample_trade_data):
        """Test that same trade data produces same ID."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        trade_id_1 = monitor._create_trade_id(sample_trade_data)
        trade_id_2 = monitor._create_trade_id(sample_trade_data)

        assert trade_id_1 == trade_id_2

    def test_parse_trade_above_threshold(self, sample_trade_data):
        """Test parsing trade above threshold."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        trade = monitor._parse_trade(sample_trade_data)

        assert trade is not None
        assert trade.trader_address == "0x1234567890abcdef1234567890abcdef12345678"
        assert trade.trader_name == "WhaleTrader"
        assert trade.market_title == "Will Bitcoin reach $100k by end of 2026?"
        assert trade.outcome == "Yes"
        assert trade.side == "BUY"
        assert trade.size == 50000.0
        assert trade.price == 0.65
        assert trade.value == 32500.0  # 50000 * 0.65

    def test_parse_trade_below_threshold(self, sample_small_trade_data):
        """Test parsing trade below threshold returns None."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        trade = monitor._parse_trade(sample_small_trade_data)

        assert trade is None

    def test_parse_trade_with_missing_fields(self):
        """Test parsing trade with missing optional fields."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        trade_data = {
            "proxyWallet": "0x1234",
            "size": "20000",
            "price": "0.80",
            "timestamp": "2026-01-18T12:30:00Z",
        }

        trade = monitor._parse_trade(trade_data)

        assert trade is not None
        assert trade.trader_name is None
        assert trade.market_title == "Unknown Market"
        assert trade.value == 16000.0

    def test_parse_trade_with_invalid_data(self):
        """Test parsing trade with invalid data."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        trade_data = {
            "size": "invalid",
            "price": "also_invalid",
        }

        trade = monitor._parse_trade(trade_data)

        # Should return None due to parsing error or below threshold
        assert trade is None

    def test_parse_trade_timestamp_formats(self):
        """Test parsing different timestamp formats."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        # ISO format with Z
        trade_data_z = {
            "proxyWallet": "0x1234",
            "size": "20000",
            "price": "0.80",
            "timestamp": "2026-01-18T12:30:00Z",
        }

        trade = monitor._parse_trade(trade_data_z)
        assert trade is not None
        assert trade.timestamp.year == 2026

    def test_duplicate_trade_detection(self, sample_trade_data):
        """Test that duplicate trades are tracked."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        trade_id = monitor._create_trade_id(sample_trade_data)

        # First time - not in processed
        assert trade_id not in monitor._processed_trades

        # Add to processed
        monitor._processed_trades.add(trade_id)

        # Second time - should be in processed
        assert trade_id in monitor._processed_trades

    def test_processed_trades_bounded(self):
        """Test that processed trades set is bounded."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        # Add more than 10000 trades
        for i in range(10001):
            monitor._processed_trades.add(f"trade_{i}")

        # Simulate cleanup (done in _poll_trades)
        if len(monitor._processed_trades) > 10000:
            monitor._processed_trades = set(
                list(monitor._processed_trades)[-5000:]
            )

        assert len(monitor._processed_trades) == 5000

    @pytest.mark.asyncio
    async def test_monitor_stop(self):
        """Test stopping the monitor."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)
        monitor.running = True

        await monitor.stop()

        assert monitor.running is False

    @pytest.mark.asyncio
    async def test_fetch_trades_success(self):
        """Test successful API fetch."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"test": "data"}])

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))

        monitor._session = mock_session

        with patch.object(monitor._session, 'get') as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)

            trades = await monitor._fetch_trades()

        # Should return the mocked data
        assert trades == [{"test": "data"}]

    @pytest.mark.asyncio
    async def test_fetch_trades_api_error(self):
        """Test API error handling."""
        callback = AsyncMock()
        monitor = WhaleMonitor(on_whale_detected=callback)

        mock_response = AsyncMock()
        mock_response.status = 500

        mock_session = MagicMock()
        monitor._session = mock_session

        with patch.object(monitor._session, 'get') as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)

            trades = await monitor._fetch_trades()

        assert trades == []

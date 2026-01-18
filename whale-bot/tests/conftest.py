"""Pytest configuration and fixtures for whale-bot tests."""

import os
import sys
from pathlib import Path

import pytest

# Add whale-bot to path
whale_bot_path = Path(__file__).parent.parent
sys.path.insert(0, str(whale_bot_path))

# Set test environment variables before importing config
os.environ["WHALE_BOT_TOKEN"] = "test_token_123"
os.environ["POLYBOT_USERNAME"] = "TestPolyBot"
os.environ["WHALE_THRESHOLD"] = "10000"
os.environ["POLL_INTERVAL"] = "30"
os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture
def sample_trade_data():
    """Sample trade data from Polymarket API."""
    return {
        "proxyWallet": "0x1234567890abcdef1234567890abcdef12345678",
        "name": "WhaleTrader",
        "pseudonym": None,
        "title": "Will Bitcoin reach $100k by end of 2026?",
        "conditionId": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "outcome": "Yes",
        "side": "BUY",
        "size": "50000",
        "price": "0.65",
        "timestamp": "2026-01-18T12:30:00Z",
        "transactionHash": "0x9876543210fedcba9876543210fedcba9876543210fedcba9876543210fedcba",
        "slug": "will-bitcoin-reach-100k",
        "icon": "https://example.com/icon.png",
    }


@pytest.fixture
def sample_small_trade_data():
    """Sample trade data below threshold."""
    return {
        "proxyWallet": "0x1234567890abcdef1234567890abcdef12345678",
        "title": "Small Market Trade",
        "conditionId": "0x1111111111111111111111111111111111111111111111111111111111111111",
        "outcome": "No",
        "side": "SELL",
        "size": "100",
        "price": "0.50",
        "timestamp": "2026-01-18T12:30:00Z",
        "transactionHash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    }


@pytest.fixture
def sample_whale_trade():
    """Sample WhaleTrade object."""
    from datetime import datetime
    from monitors.whale_monitor import WhaleTrade

    return WhaleTrade(
        trader_address="0x1234567890abcdef1234567890abcdef12345678",
        trader_name="WhaleTrader",
        market_title="Will Bitcoin reach $100k by end of 2026?",
        condition_id="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        outcome="Yes",
        side="BUY",
        size=50000.0,
        price=0.65,
        value=32500.0,
        tx_hash="0x9876543210fedcba9876543210fedcba9876543210fedcba9876543210fedcba",
        timestamp=datetime(2026, 1, 18, 12, 30, 0),
        market_slug="will-bitcoin-reach-100k",
        market_icon="https://example.com/icon.png",
    )

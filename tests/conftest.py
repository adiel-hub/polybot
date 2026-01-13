"""Shared pytest fixtures for PolyBot tests.

This module provides reusable fixtures for testing database, encryption,
and other core components. Uses real SQLite databases and encryption keys.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cryptography.fernet import Fernet

from database.connection import Database
from database.repositories.user_repo import UserRepository
from database.repositories.wallet_repo import WalletRepository
from core.wallet.encryption import KeyEncryption
from core.wallet.generator import WalletGenerator


# Real encryption key for testing (generated fresh)
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def encryption_key() -> str:
    """Provide a real Fernet encryption key for tests."""
    return TEST_ENCRYPTION_KEY


@pytest.fixture
def key_encryption(encryption_key: str) -> KeyEncryption:
    """Create a KeyEncryption instance with real key."""
    return KeyEncryption(encryption_key)


@pytest.fixture
def wallet_generator() -> WalletGenerator:
    """Create a WalletGenerator instance."""
    return WalletGenerator()


@pytest_asyncio.fixture
async def temp_db():
    """Create a temporary SQLite database for testing.

    Yields a real Database instance with all tables initialized.
    Database is cleaned up after test completes.
    """
    # Create temp file for database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        db = Database(db_path)
        await db.initialize()
        yield db
    finally:
        await db.close()
        # Clean up temp file
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest_asyncio.fixture
async def user_repo(temp_db: Database) -> UserRepository:
    """Create a UserRepository with real database."""
    return UserRepository(temp_db)


@pytest_asyncio.fixture
async def wallet_repo(temp_db: Database) -> WalletRepository:
    """Create a WalletRepository with real database."""
    return WalletRepository(temp_db)


@pytest.fixture
def sample_telegram_user() -> dict:
    """Provide sample Telegram user data for tests."""
    return {
        "telegram_id": 123456789,
        "telegram_username": "testuser",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def sample_wallet_address() -> str:
    """Provide a valid Ethereum address for tests."""
    return "0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD"


@pytest.fixture
def sample_private_key() -> str:
    """Provide a sample private key for tests.

    Note: This is a randomly generated key for testing only.
    Never use real private keys in tests.
    """
    # Generate a real but disposable private key
    address, private_key = WalletGenerator.create_wallet()
    return private_key


@pytest.fixture
def sample_market_data() -> dict:
    """Provide sample market data from Gamma API format."""
    return {
        "id": "0x1234567890abcdef",
        "conditionId": "0xabcdef1234567890",
        "question": "Will Bitcoin reach $100,000 by end of 2025?",
        "title": "Bitcoin $100K",
        "description": "This market resolves to Yes if Bitcoin reaches $100,000.",
        "category": "crypto",
        "image": "https://example.com/btc.png",
        "clobTokenIds": '["token_yes_123", "token_no_456"]',
        "outcomePrices": '["0.65", "0.35"]',
        "volume24hr": 50000.0,
        "volume": 1500000.0,
        "liquidity": 250000.0,
        "endDate": "2025-12-31T23:59:59Z",
        "active": True,
        "closed": False,
        "markets": [],
    }


@pytest.fixture
def sample_order_data() -> dict:
    """Provide sample order data for tests."""
    return {
        "market_condition_id": "0xabcdef1234567890",
        "market_question": "Will Bitcoin reach $100,000?",
        "token_id": "token_yes_123",
        "side": "BUY",
        "order_type": "MARKET",
        "price": None,
        "size": 10.0,
        "outcome": "YES",
    }

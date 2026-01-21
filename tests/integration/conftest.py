"""Shared pytest fixtures for integration tests.

CRITICAL: All fixtures use REAL bot implementations - NO MOCKS!
- Real UserService, TradingService, WithdrawalManager
- Real database operations with SQLite
- Real blockchain interactions via web3
- Real Polymarket CLOB API calls
- Real Alchemy WebSocket connections
"""

import os
import sys
import tempfile
import random
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account
from cryptography.fernet import Fernet

# Load test environment
load_dotenv("test.env")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import REAL bot services (no mocks!)
from database.connection import Database
from database.repositories.user_repo import UserRepository
from database.repositories.wallet_repo import WalletRepository
from database.repositories.order_repo import OrderRepository
from database.repositories.position_repo import PositionRepository
from services.user_service import UserService
from services.trading_service import TradingService
from core.wallet.encryption import KeyEncryption
from core.wallet.generator import WalletGenerator
from core.blockchain.withdrawals import WithdrawalManager
from core.polymarket.gamma_client import GammaMarketClient
from config.settings import settings
from config.constants import USDC_ADDRESS, USDC_E_ADDRESS, USDC_DECIMALS

# ERC20 ABI (minimal - just what we need for transfers)
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]


# ================================================================================
# Database Fixtures
# ================================================================================

@pytest_asyncio.fixture
async def integration_db():
    """Real SQLite database for integration tests.

    Creates a temporary database with all tables initialized.
    Database is cleaned up after test completes.
    """
    # Create temp file for database
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_integration_")
    os.close(fd)

    try:
        db = Database(db_path)
        await db.initialize()  # Real table creation
        yield db
    finally:
        await db.close()
        # Clean up temp file
        if os.path.exists(db_path):
            os.unlink(db_path)


# ================================================================================
# Encryption Fixtures
# ================================================================================

@pytest.fixture
def integration_encryption_key() -> str:
    """Generate a real encryption key for integration tests."""
    return Fernet.generate_key().decode()


@pytest.fixture
def key_encryption(integration_encryption_key: str) -> KeyEncryption:
    """Real KeyEncryption instance with generated key."""
    return KeyEncryption(integration_encryption_key)


# ================================================================================
# Service Fixtures (REAL implementations only!)
# ================================================================================

@pytest_asyncio.fixture
async def real_user_service(integration_db: Database, key_encryption: KeyEncryption) -> UserService:
    """Real UserService with real database and encryption.

    No mocks - uses actual bot implementation.
    """
    return UserService(integration_db, key_encryption)


@pytest_asyncio.fixture
async def real_trading_service(integration_db: Database, key_encryption: KeyEncryption) -> TradingService:
    """Real TradingService with real database and encryption.

    No mocks - uses actual bot implementation.
    """
    return TradingService(integration_db, key_encryption)


@pytest_asyncio.fixture
async def real_withdrawal_manager() -> WithdrawalManager:
    """Real WithdrawalManager for on-chain withdrawal operations.

    Connects to real Polygon RPC and signs real transactions.
    """
    return WithdrawalManager(
        rpc_url=settings.polygon_rpc_url,
        gas_sponsor_key=settings.gas_sponsor_private_key if settings.gas_sponsor_private_key else None
    )


@pytest_asyncio.fixture
async def real_gamma_client() -> GammaMarketClient:
    """Real GammaMarketClient for fetching market data from Polymarket."""
    return GammaMarketClient()


# ================================================================================
# Repository Fixtures (REAL implementations)
# ================================================================================

@pytest_asyncio.fixture
async def wallet_repo(integration_db: Database) -> WalletRepository:
    """Real WalletRepository with real database."""
    return WalletRepository(integration_db)


@pytest_asyncio.fixture
async def order_repo(integration_db: Database) -> OrderRepository:
    """Real OrderRepository with real database."""
    return OrderRepository(integration_db)


@pytest_asyncio.fixture
async def position_repo(integration_db: Database) -> PositionRepository:
    """Real PositionRepository with real database."""
    return PositionRepository(integration_db)


# ================================================================================
# Blockchain Fixtures
# ================================================================================

@pytest.fixture
def web3_polygon() -> Web3:
    """Real Web3 instance connected to Polygon mainnet."""
    w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
    assert w3.is_connected(), "Cannot connect to Polygon RPC"
    return w3


@pytest.fixture
def usdc_contract(web3_polygon: Web3):
    """Real USDC contract instance on Polygon."""
    return web3_polygon.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI
    )


@pytest.fixture
def external_wallet():
    """Your real external wallet for funding integration tests.

    This wallet must have:
    - USDC for test deposits
    - POL for gas fees

    Set in test.env as TEST_FUNDING_WALLET_PRIVATE_KEY
    """
    if not settings.test_funding_wallet_private_key:
        pytest.skip("TEST_FUNDING_WALLET_PRIVATE_KEY not configured")

    account = Account.from_key(settings.test_funding_wallet_private_key)
    return account


# ================================================================================
# User Fixtures (creates REAL users with REAL wallets)
# ================================================================================

@pytest_asyncio.fixture
async def test_user(real_user_service: UserService):
    """Create a real test user with real wallet.

    Uses actual UserService.register_user() - no mocks.
    """
    user, wallet = await real_user_service.register_user(
        telegram_id=random.randint(100000, 999999),
        telegram_username=f"test_user_{random.randint(1000, 9999)}",
        first_name="Test",
        last_name="User"
    )
    return user, wallet


@pytest_asyncio.fixture
async def funded_test_user(
    real_user_service: UserService,
    external_wallet,
    integration_db: Database,
    web3_polygon: Web3,
    usdc_contract,
):
    """Create real user and fund with real USDC from external wallet.

    This fixture:
    1. Creates real user via UserService
    2. Sends real USDC from your wallet to bot wallet
    3. Updates real database balance
    4. Returns user and wallet ready for testing

    Cost: ~10 USDC + gas (configurable via TEST_DEPOSIT_AMOUNT)
    """
    # Create real user
    user, wallet = await real_user_service.register_user(
        telegram_id=random.randint(100000, 999999),
        telegram_username=f"funded_test_{random.randint(1000, 9999)}",
        first_name="Funded",
        last_name="Test"
    )

    print(f"\n📋 Created test user: {wallet.address}")

    # Send real USDC to bot wallet
    deposit_amount = settings.test_deposit_amount
    amount_wei = int(deposit_amount * (10 ** USDC_DECIMALS))

    tx = usdc_contract.functions.transfer(
        Web3.to_checksum_address(wallet.address),
        amount_wei
    ).build_transaction({
        'from': external_wallet.address,
        'nonce': web3_polygon.eth.get_transaction_count(external_wallet.address),
        'gas': 100000,
        'gasPrice': web3_polygon.eth.gas_price,
        'chainId': 137,  # Polygon mainnet
    })

    signed = external_wallet.sign_transaction(tx)
    tx_hash = web3_polygon.eth.send_raw_transaction(signed.raw_transaction)

    print(f"🔄 Funding with {deposit_amount} USDC: {tx_hash.hex()}")

    # Wait for real confirmation
    receipt = web3_polygon.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    assert receipt.status == 1, f"USDC transfer failed: {tx_hash.hex()}"

    print(f"✅ Funding confirmed: {tx_hash.hex()}")

    # Update balance in database (simulate deposit detection)
    wallet_repo = WalletRepository(integration_db)
    await wallet_repo.add_balance(wallet.id, deposit_amount)

    # Verify balance
    updated_wallet = await wallet_repo.get_by_id(wallet.id)
    assert updated_wallet.usdc_balance == deposit_amount

    return user, updated_wallet


# ================================================================================
# Helper Functions
# ================================================================================

@pytest.fixture
def check_balance_on_chain(web3_polygon: Web3, usdc_contract):
    """Helper to check real USDC balance on-chain."""
    def _check(address: str) -> float:
        balance_wei = usdc_contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call()
        return balance_wei / (10 ** USDC_DECIMALS)
    return _check


@pytest.fixture
def send_pol_for_gas(web3_polygon: Web3, external_wallet):
    """Helper to send POL for gas fees to a wallet."""
    async def _send(to_address: str, amount_pol: float = 0.05):
        tx = {
            'from': external_wallet.address,
            'to': Web3.to_checksum_address(to_address),
            'value': web3_polygon.to_wei(amount_pol, 'ether'),
            'nonce': web3_polygon.eth.get_transaction_count(external_wallet.address),
            'gas': 21000,
            'gasPrice': web3_polygon.eth.gas_price,
            'chainId': 137,
        }

        signed = external_wallet.sign_transaction(tx)
        tx_hash = web3_polygon.eth.send_raw_transaction(signed.raw_transaction)
        receipt = web3_polygon.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        assert receipt.status == 1, f"POL transfer failed"
        print(f"✅ Sent {amount_pol} POL for gas: {tx_hash.hex()}")

    return _send


# ================================================================================
# Test Configuration Validation
# ================================================================================

def pytest_configure(config):
    """Validate test configuration before running integration tests."""
    # Check if we're running integration tests
    if "integration" in config.option.markexpr or "tests/integration" in str(config.args):
        # Validate required settings
        required_settings = [
            ("POLYGON_RPC_URL", settings.polygon_rpc_url),
            ("MASTER_ENCRYPTION_KEY", settings.master_encryption_key),
        ]

        missing = [name for name, value in required_settings if not value]
        if missing:
            raise ValueError(
                f"Missing required settings for integration tests: {', '.join(missing)}\n"
                "Please configure test.env with all required values."
            )

        print("\n" + "="*80)
        print("INTEGRATION TEST CONFIGURATION")
        print("="*80)
        print(f"Database: {settings.database_path}")
        print(f"RPC URL: {settings.polygon_rpc_url[:50]}...")
        print(f"Test amounts: Deposit=${settings.test_deposit_amount}, Trade=${settings.test_trade_amount}")
        print("="*80 + "\n")


def pytest_collection_modifyitems(config, items):
    """Add markers to test items and show cost warnings."""
    expensive_tests = []

    for item in items:
        # Auto-mark integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Check if test is expensive
        if "expensive" in [marker.name for marker in item.iter_markers()]:
            expensive_tests.append(item.name)

    if expensive_tests and config.option.markexpr != "not expensive":
        print("\n" + "⚠️ " * 20)
        print("WARNING: You are about to run tests that cost REAL MONEY!")
        print(f"Expensive tests: {len(expensive_tests)}")
        print(f"Estimated cost: ~${len(expensive_tests) * 20} + gas fees")
        print("To skip expensive tests, run: pytest -m 'not expensive'")
        print("⚠️ " * 20 + "\n")

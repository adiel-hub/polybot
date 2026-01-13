"""Tests for WalletRepository.

Tests the WalletRepository class which handles CRUD operations
for wallets in the SQLite database.
"""

import pytest

from database.repositories.wallet_repo import WalletRepository
from database.repositories.user_repo import UserRepository
from database.connection import Database


class TestWalletRepository:
    """Test suite for WalletRepository."""

    @pytest.fixture
    async def test_user(self, temp_db: Database):
        """Create a test user for wallet tests."""
        user_repo = UserRepository(temp_db)
        user = await user_repo.create(telegram_id=100000001)
        return user

    @pytest.mark.asyncio
    async def test_create_wallet(self, wallet_repo: WalletRepository, test_user):
        """Test creating a new wallet."""
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD"
        encrypted_key = b"encrypted_private_key_data"
        salt = b"random_salt_16by"

        wallet = await wallet_repo.create(
            user_id=test_user.id,
            address=address,
            encrypted_private_key=encrypted_key,
            encryption_salt=salt,
        )

        assert wallet is not None
        assert wallet.id is not None
        assert wallet.user_id == test_user.id
        assert wallet.address == address
        assert wallet.encrypted_private_key == encrypted_key
        assert wallet.encryption_salt == salt
        assert wallet.usdc_balance == 0.0

    @pytest.mark.asyncio
    async def test_get_by_id(self, wallet_repo: WalletRepository, test_user):
        """Test retrieving wallet by ID."""
        address = "0x1111111111111111111111111111111111111111"
        created = await wallet_repo.create(
            user_id=test_user.id,
            address=address,
            encrypted_private_key=b"key",
            encryption_salt=b"salt_16_bytes___",
        )

        retrieved = await wallet_repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.address == address

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, wallet_repo: WalletRepository):
        """Test get_by_id returns None for non-existent wallet."""
        result = await wallet_repo.get_by_id(99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_user_id(self, wallet_repo: WalletRepository, test_user):
        """Test retrieving wallet by user ID."""
        address = "0x2222222222222222222222222222222222222222"
        await wallet_repo.create(
            user_id=test_user.id,
            address=address,
            encrypted_private_key=b"key",
            encryption_salt=b"salt_16_bytes___",
        )

        retrieved = await wallet_repo.get_by_user_id(test_user.id)

        assert retrieved is not None
        assert retrieved.user_id == test_user.id
        assert retrieved.address == address

    @pytest.mark.asyncio
    async def test_get_by_user_id_not_found(self, wallet_repo: WalletRepository):
        """Test get_by_user_id returns None for non-existent user."""
        result = await wallet_repo.get_by_user_id(99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_address(self, wallet_repo: WalletRepository, test_user):
        """Test retrieving wallet by address."""
        address = "0x3333333333333333333333333333333333333333"
        await wallet_repo.create(
            user_id=test_user.id,
            address=address,
            encrypted_private_key=b"key",
            encryption_salt=b"salt_16_bytes___",
        )

        retrieved = await wallet_repo.get_by_address(address)

        assert retrieved is not None
        assert retrieved.address == address

    @pytest.mark.asyncio
    async def test_get_by_address_case_insensitive(
        self, wallet_repo: WalletRepository, test_user
    ):
        """Test that get_by_address is case insensitive."""
        address_mixed = "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12"
        await wallet_repo.create(
            user_id=test_user.id,
            address=address_mixed,
            encrypted_private_key=b"key",
            encryption_salt=b"salt_16_bytes___",
        )

        # Search with lowercase
        retrieved = await wallet_repo.get_by_address(address_mixed.lower())

        assert retrieved is not None
        assert retrieved.address == address_mixed

    @pytest.mark.asyncio
    async def test_update_balance(self, wallet_repo: WalletRepository, test_user):
        """Test updating wallet balance."""
        wallet = await wallet_repo.create(
            user_id=test_user.id,
            address="0x4444444444444444444444444444444444444444",
            encrypted_private_key=b"key",
            encryption_salt=b"salt_16_bytes___",
        )
        assert wallet.usdc_balance == 0.0

        await wallet_repo.update_balance(wallet.id, 100.50)

        updated = await wallet_repo.get_by_id(wallet.id)
        assert updated.usdc_balance == 100.50
        assert updated.last_balance_check is not None

    @pytest.mark.asyncio
    async def test_add_balance(self, wallet_repo: WalletRepository, test_user):
        """Test adding to wallet balance."""
        wallet = await wallet_repo.create(
            user_id=test_user.id,
            address="0x5555555555555555555555555555555555555555",
            encrypted_private_key=b"key",
            encryption_salt=b"salt_16_bytes___",
        )

        await wallet_repo.update_balance(wallet.id, 50.0)
        await wallet_repo.add_balance(wallet.id, 25.0)

        updated = await wallet_repo.get_by_id(wallet.id)
        assert updated.usdc_balance == 75.0

    @pytest.mark.asyncio
    async def test_subtract_balance(self, wallet_repo: WalletRepository, test_user):
        """Test subtracting from wallet balance."""
        wallet = await wallet_repo.create(
            user_id=test_user.id,
            address="0x6666666666666666666666666666666666666666",
            encrypted_private_key=b"key",
            encryption_salt=b"salt_16_bytes___",
        )

        await wallet_repo.update_balance(wallet.id, 100.0)
        await wallet_repo.subtract_balance(wallet.id, 30.0)

        updated = await wallet_repo.get_by_id(wallet.id)
        assert updated.usdc_balance == 70.0

    @pytest.mark.asyncio
    async def test_update_api_credentials(
        self, wallet_repo: WalletRepository, test_user
    ):
        """Test updating API credentials."""
        wallet = await wallet_repo.create(
            user_id=test_user.id,
            address="0x7777777777777777777777777777777777777777",
            encrypted_private_key=b"key",
            encryption_salt=b"salt_16_bytes___",
        )
        assert wallet.has_api_credentials is False

        await wallet_repo.update_api_credentials(
            wallet.id,
            api_key_encrypted=b"encrypted_api_key",
            api_secret_encrypted=b"encrypted_api_secret",
            api_passphrase_encrypted=b"encrypted_passphrase",
        )

        updated = await wallet_repo.get_by_id(wallet.id)
        assert updated.api_key_encrypted == b"encrypted_api_key"
        assert updated.api_secret_encrypted == b"encrypted_api_secret"
        assert updated.api_passphrase_encrypted == b"encrypted_passphrase"
        assert updated.has_api_credentials is True

    @pytest.mark.asyncio
    async def test_get_all_addresses(self, wallet_repo: WalletRepository, temp_db):
        """Test getting all wallet addresses."""
        user_repo = UserRepository(temp_db)

        # Create multiple users with wallets
        user1 = await user_repo.create(telegram_id=100000010)
        user2 = await user_repo.create(telegram_id=100000011)

        await wallet_repo.create(
            user_id=user1.id,
            address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            encrypted_private_key=b"key1",
            encryption_salt=b"salt_16_bytes___",
        )
        await wallet_repo.create(
            user_id=user2.id,
            address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            encrypted_private_key=b"key2",
            encryption_salt=b"salt_16_bytes___",
        )

        addresses = await wallet_repo.get_all_addresses()

        assert len(addresses) == 2
        assert "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in addresses
        assert "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" in addresses

"""Tests for UserService."""

import pytest
import pytest_asyncio

from database.connection import Database
from services.user_service import UserService
from core.wallet.encryption import KeyEncryption
from core.wallet.generator import WalletGenerator


@pytest_asyncio.fixture
async def user_service(temp_db: Database, key_encryption: KeyEncryption) -> UserService:
    """Create a UserService with real database and encryption."""
    return UserService(temp_db, key_encryption)


class TestUserService:
    """Test cases for UserService."""

    @pytest.mark.asyncio
    async def test_register_new_user(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test registering a new user creates user and wallet."""
        user, wallet = await user_service.register_user(**sample_telegram_user)

        # Check user was created
        assert user is not None
        assert user.id is not None
        assert user.telegram_id == sample_telegram_user["telegram_id"]
        assert user.telegram_username == sample_telegram_user["telegram_username"]
        assert user.first_name == sample_telegram_user["first_name"]

        # Check wallet was created
        assert wallet is not None
        assert wallet.user_id == user.id
        assert wallet.address.startswith("0x")
        assert len(wallet.address) == 42
        assert wallet.encrypted_private_key is not None
        assert wallet.usdc_balance == 0.0

    @pytest.mark.asyncio
    async def test_register_duplicate_telegram_id(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test registering same telegram_id returns existing user."""
        # Register first time
        user1, wallet1 = await user_service.register_user(**sample_telegram_user)

        # Try to register again
        user2, wallet2 = await user_service.register_user(**sample_telegram_user)

        # Should return same user and wallet
        assert user1.id == user2.id
        assert wallet1.id == wallet2.id

    @pytest.mark.asyncio
    async def test_get_user_by_telegram_id(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test retrieving user by Telegram ID."""
        # Register user
        user, _ = await user_service.register_user(**sample_telegram_user)

        # Retrieve by telegram_id
        retrieved = await user_service.get_user(sample_telegram_user["telegram_id"])

        assert retrieved is not None
        assert retrieved.id == user.id
        assert retrieved.telegram_id == sample_telegram_user["telegram_id"]

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, user_service: UserService):
        """Test retrieving non-existent user."""
        result = await user_service.get_user(99999999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_wallet(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test retrieving wallet for user."""
        user, wallet = await user_service.register_user(**sample_telegram_user)

        retrieved_wallet = await user_service.get_wallet(user.telegram_id)

        assert retrieved_wallet is not None
        assert retrieved_wallet.id == wallet.id
        assert retrieved_wallet.address == wallet.address

    @pytest.mark.asyncio
    async def test_get_private_key(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test decrypting private key."""
        user, wallet = await user_service.register_user(**sample_telegram_user)

        private_key = await user_service.get_private_key(user.id)

        assert private_key is not None
        assert private_key.startswith("0x")
        assert len(private_key) == 66

        # Validate it's a valid private key by trying to use it
        from eth_account import Account
        account = Account.from_key(private_key)
        assert account.address.lower() == wallet.address.lower()

    @pytest.mark.asyncio
    async def test_get_user_settings_default(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test getting default user settings."""
        user, _ = await user_service.register_user(**sample_telegram_user)

        settings = await user_service.get_user_settings(user.telegram_id)

        # Check default settings
        assert settings["trading_mode"] == "standard"
        assert settings["fast_mode_threshold"] == 100.0
        assert settings["quickbuy_presets"] == [10, 25, 50]
        assert settings["auto_claim"] is False
        assert settings["auto_apply_preset"] is False
        assert settings["two_factor_enabled"] is False

    @pytest.mark.asyncio
    async def test_update_user_setting(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test updating a single user setting."""
        user, _ = await user_service.register_user(**sample_telegram_user)

        # Update trading mode
        await user_service.update_user_setting(
            user.telegram_id,
            "trading_mode",
            "ludicrous",
        )

        settings = await user_service.get_user_settings(user.telegram_id)
        assert settings["trading_mode"] == "ludicrous"

        # Update fast mode threshold
        await user_service.update_user_setting(
            user.telegram_id,
            "fast_mode_threshold",
            250.0,
        )

        settings = await user_service.get_user_settings(user.telegram_id)
        assert settings["fast_mode_threshold"] == 250.0

    @pytest.mark.asyncio
    async def test_update_quickbuy_presets(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test updating quickbuy presets."""
        user, _ = await user_service.register_user(**sample_telegram_user)

        new_presets = [20, 50, 100]
        await user_service.update_user_setting(
            user.telegram_id,
            "quickbuy_presets",
            new_presets,
        )

        settings = await user_service.get_user_settings(user.telegram_id)
        assert settings["quickbuy_presets"] == new_presets

    @pytest.mark.asyncio
    async def test_toggle_boolean_settings(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test toggling boolean settings."""
        user, _ = await user_service.register_user(**sample_telegram_user)

        # Enable auto-claim
        await user_service.update_user_setting(user.telegram_id, "auto_claim", True)
        settings = await user_service.get_user_settings(user.telegram_id)
        assert settings["auto_claim"] is True

        # Disable auto-claim
        await user_service.update_user_setting(user.telegram_id, "auto_claim", False)
        settings = await user_service.get_user_settings(user.telegram_id)
        assert settings["auto_claim"] is False

    @pytest.mark.asyncio
    async def test_wallet_encryption_and_decryption(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test that private keys are properly encrypted and can be decrypted."""
        user, wallet = await user_service.register_user(**sample_telegram_user)

        # Private key should be encrypted (not plaintext)
        assert not wallet.encrypted_private_key.startswith("0x")

        # Should be able to decrypt it
        decrypted_key = await user_service.get_private_key(user.id)
        assert decrypted_key.startswith("0x")

        # Should be a valid Ethereum private key
        from eth_account import Account
        account = Account.from_key(decrypted_key)
        assert account.address.lower() == wallet.address.lower()

    @pytest.mark.asyncio
    async def test_multiple_users_separate_wallets(
        self,
        user_service: UserService,
    ):
        """Test that multiple users get unique wallets."""
        # Register two users
        user1, wallet1 = await user_service.register_user(
            telegram_id=111111,
            telegram_username="user1",
        )
        user2, wallet2 = await user_service.register_user(
            telegram_id=222222,
            telegram_username="user2",
        )

        # Should have different wallets
        assert wallet1.address != wallet2.address
        assert wallet1.id != wallet2.id

        # Each should be able to decrypt their own key
        key1 = await user_service.get_private_key(user1.id)
        key2 = await user_service.get_private_key(user2.id)

        assert key1 != key2

    @pytest.mark.asyncio
    async def test_user_settings_preserved_across_sessions(
        self,
        user_service: UserService,
        sample_telegram_user: dict,
    ):
        """Test that user settings persist correctly."""
        user, _ = await user_service.register_user(**sample_telegram_user)

        # Update multiple settings
        await user_service.update_user_setting(user.telegram_id, "trading_mode", "fast")
        await user_service.update_user_setting(user.telegram_id, "auto_claim", True)
        await user_service.update_user_setting(user.telegram_id, "quickbuy_presets", [15, 30, 60])

        # Retrieve settings
        settings = await user_service.get_user_settings(user.telegram_id)

        assert settings["trading_mode"] == "fast"
        assert settings["auto_claim"] is True
        assert settings["quickbuy_presets"] == [15, 30, 60]
        # Other settings should remain default
        assert settings["two_factor_enabled"] is False
        assert settings["auto_apply_preset"] is False

"""Tests for Two-Factor Authentication implementation."""

import pytest
import pytest_asyncio
from io import BytesIO

from database.connection import Database
from services.user_service import UserService
from core.wallet.encryption import KeyEncryption
from core.security.two_factor import TwoFactorAuth


@pytest_asyncio.fixture
async def user_service(temp_db: Database, key_encryption: KeyEncryption) -> UserService:
    """Create a UserService with real database and encryption."""
    return UserService(temp_db, key_encryption)


@pytest_asyncio.fixture
async def test_user_2fa(
    user_service: UserService,
    sample_telegram_user: dict,
):
    """Create a test user for 2FA testing."""
    user, wallet = await user_service.register_user(**sample_telegram_user)
    return user


class TestTwoFactorAuth:
    """Test cases for 2FA service."""

    def test_generate_secret(self):
        """Test TOTP secret generation."""
        secret = TwoFactorAuth.generate_secret()

        assert secret is not None
        assert len(secret) == 32  # Base32 encoded, should be 32 chars
        assert secret.isalnum()  # Should be alphanumeric

    def test_get_provisioning_uri(self):
        """Test provisioning URI generation."""
        secret = "JBSWY3DPEHPK3PXP"
        username = "testuser"

        uri = TwoFactorAuth.get_provisioning_uri(secret, username)

        assert uri.startswith("otpauth://totp/")
        assert username in uri
        assert secret in uri
        assert "PolyBot" in uri

    def test_generate_qr_code(self):
        """Test QR code image generation."""
        uri = "otpauth://totp/PolyBot:testuser?secret=JBSWY3DPEHPK3PXP&issuer=PolyBot"

        qr_code = TwoFactorAuth.generate_qr_code(uri)

        assert isinstance(qr_code, BytesIO)
        assert qr_code.tell() == 0  # Should be at start
        content = qr_code.read()
        assert len(content) > 0  # Should have image data
        assert content.startswith(b'\x89PNG')  # PNG magic bytes

    def test_verify_token_valid(self):
        """Test TOTP token verification with valid token."""
        secret = "JBSWY3DPEHPK3PXP"

        # Get current token
        current_token = TwoFactorAuth.get_current_token(secret)

        # Verify it
        is_valid = TwoFactorAuth.verify_token(secret, current_token)

        assert is_valid is True

    def test_verify_token_invalid(self):
        """Test TOTP token verification with invalid token."""
        secret = "JBSWY3DPEHPK3PXP"

        # Use a clearly wrong token
        is_valid = TwoFactorAuth.verify_token(secret, "000000")

        assert is_valid is False

    def test_verify_token_wrong_format(self):
        """Test TOTP token verification with wrong format."""
        secret = "JBSWY3DPEHPK3PXP"

        # Test various invalid formats
        assert TwoFactorAuth.verify_token(secret, "12345") is False  # Too short
        assert TwoFactorAuth.verify_token(secret, "1234567") is False  # Too long
        assert TwoFactorAuth.verify_token(secret, "abcdef") is False  # Not numbers

    def test_setup_2fa(self):
        """Test complete 2FA setup flow."""
        username = "testuser"

        secret, provisioning_uri, qr_code = TwoFactorAuth.setup_2fa(username)

        # Check secret
        assert secret is not None
        assert len(secret) == 32

        # Check provisioning URI
        assert provisioning_uri.startswith("otpauth://totp/")
        assert username in provisioning_uri

        # Check QR code
        assert isinstance(qr_code, BytesIO)


class TestUserService2FA:
    """Test cases for UserService 2FA methods."""

    @pytest.mark.asyncio
    async def test_setup_2fa(
        self,
        user_service: UserService,
        test_user_2fa,
    ):
        """Test 2FA setup via UserService."""
        telegram_id = test_user_2fa.telegram_id

        secret, qr_code = await user_service.setup_2fa(telegram_id)

        # Check return values
        assert secret is not None
        assert len(secret) == 32
        assert isinstance(qr_code, BytesIO)

        # Check database was updated
        user = await user_service.get_user(telegram_id)
        assert user.totp_secret is not None
        assert user.totp_secret_salt is not None
        assert user.totp_verified_at is None  # Not verified yet

    @pytest.mark.asyncio
    async def test_verify_2fa_token_valid(
        self,
        user_service: UserService,
        test_user_2fa,
    ):
        """Test verifying valid 2FA token."""
        telegram_id = test_user_2fa.telegram_id

        # Setup 2FA
        secret, _ = await user_service.setup_2fa(telegram_id)

        # Get current token
        current_token = TwoFactorAuth.get_current_token(secret)

        # Verify it
        is_valid = await user_service.verify_2fa_token(telegram_id, current_token)

        assert is_valid is True

        # Check user was marked as verified
        user = await user_service.get_user(telegram_id)
        assert user.totp_verified_at is not None

    @pytest.mark.asyncio
    async def test_verify_2fa_token_invalid(
        self,
        user_service: UserService,
        test_user_2fa,
    ):
        """Test verifying invalid 2FA token."""
        telegram_id = test_user_2fa.telegram_id

        # Setup 2FA
        await user_service.setup_2fa(telegram_id)

        # Try invalid token
        is_valid = await user_service.verify_2fa_token(telegram_id, "000000")

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_2fa_token_no_setup(
        self,
        user_service: UserService,
        test_user_2fa,
    ):
        """Test verifying token when 2FA not set up."""
        telegram_id = test_user_2fa.telegram_id

        # Try to verify without setup
        is_valid = await user_service.verify_2fa_token(telegram_id, "123456")

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_is_2fa_enabled_not_setup(
        self,
        user_service: UserService,
        test_user_2fa,
    ):
        """Test is_2fa_enabled when not set up."""
        telegram_id = test_user_2fa.telegram_id

        is_enabled = await user_service.is_2fa_enabled(telegram_id)

        assert is_enabled is False

    @pytest.mark.asyncio
    async def test_is_2fa_enabled_setup_not_verified(
        self,
        user_service: UserService,
        test_user_2fa,
    ):
        """Test is_2fa_enabled when set up but not verified."""
        telegram_id = test_user_2fa.telegram_id

        # Setup but don't verify
        await user_service.setup_2fa(telegram_id)

        is_enabled = await user_service.is_2fa_enabled(telegram_id)

        assert is_enabled is False  # Not enabled until verified

    @pytest.mark.asyncio
    async def test_is_2fa_enabled_fully_setup(
        self,
        user_service: UserService,
        test_user_2fa,
    ):
        """Test is_2fa_enabled when fully set up and verified."""
        telegram_id = test_user_2fa.telegram_id

        # Setup and verify
        secret, _ = await user_service.setup_2fa(telegram_id)
        current_token = TwoFactorAuth.get_current_token(secret)
        await user_service.verify_2fa_token(telegram_id, current_token)

        # Enable in settings
        await user_service.update_user_setting(telegram_id, "two_factor_enabled", True)

        is_enabled = await user_service.is_2fa_enabled(telegram_id)

        assert is_enabled is True

    @pytest.mark.asyncio
    async def test_disable_2fa(
        self,
        user_service: UserService,
        test_user_2fa,
    ):
        """Test disabling 2FA."""
        telegram_id = test_user_2fa.telegram_id

        # Setup and enable 2FA
        secret, _ = await user_service.setup_2fa(telegram_id)
        current_token = TwoFactorAuth.get_current_token(secret)
        await user_service.verify_2fa_token(telegram_id, current_token)
        await user_service.update_user_setting(telegram_id, "two_factor_enabled", True)

        # Verify it's enabled
        assert await user_service.is_2fa_enabled(telegram_id) is True

        # Disable it
        await user_service.disable_2fa(telegram_id)

        # Verify it's disabled
        assert await user_service.is_2fa_enabled(telegram_id) is False

        # Check database was cleared
        user = await user_service.get_user(telegram_id)
        assert user.totp_secret is None
        assert user.totp_secret_salt is None
        assert user.totp_verified_at is None

    @pytest.mark.asyncio
    async def test_encryption_of_secret(
        self,
        user_service: UserService,
        test_user_2fa,
    ):
        """Test that TOTP secret is properly encrypted."""
        telegram_id = test_user_2fa.telegram_id

        # Setup 2FA
        secret, _ = await user_service.setup_2fa(telegram_id)

        # Get user from database
        user = await user_service.get_user(telegram_id)

        # Secret should be encrypted (not plaintext)
        assert user.totp_secret != secret.encode()

        # Should be able to decrypt and verify
        current_token = TwoFactorAuth.get_current_token(secret)
        is_valid = await user_service.verify_2fa_token(telegram_id, current_token)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_multiple_verifications(
        self,
        user_service: UserService,
        test_user_2fa,
    ):
        """Test multiple token verifications."""
        telegram_id = test_user_2fa.telegram_id

        # Setup 2FA
        secret, _ = await user_service.setup_2fa(telegram_id)

        # Verify multiple times
        for _ in range(3):
            current_token = TwoFactorAuth.get_current_token(secret)
            is_valid = await user_service.verify_2fa_token(telegram_id, current_token)
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_2fa_for_nonexistent_user(
        self,
        user_service: UserService,
    ):
        """Test 2FA operations for non-existent user."""
        fake_telegram_id = 999999999

        # Should handle gracefully
        assert await user_service.is_2fa_enabled(fake_telegram_id) is False
        assert await user_service.verify_2fa_token(fake_telegram_id, "123456") is False

        # Setup should raise error
        with pytest.raises(ValueError):
            await user_service.setup_2fa(fake_telegram_id)

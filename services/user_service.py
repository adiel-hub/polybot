"""User service for registration and wallet management."""

import asyncio
import logging
from typing import Optional, Dict, Any

from database.connection import Database
from database.repositories import UserRepository, WalletRepository
from database.models import User, Wallet
from core.wallet import WalletGenerator, KeyEncryption

logger = logging.getLogger(__name__)


class UserService:
    """Service for user operations."""

    def __init__(
        self,
        db: Database,
        encryption: KeyEncryption,
    ):
        self.user_repo = UserRepository(db)
        self.wallet_repo = WalletRepository(db)
        self.encryption = encryption
        self._trading_service = None  # Set via set_trading_service() to avoid circular import
        self._websocket_service = None  # Set via set_websocket_service() for deposit monitoring (legacy)
        self._webhook_manager = None  # Set via set_webhook_manager() for Alchemy webhook

    def set_trading_service(self, trading_service) -> None:
        """Set trading service reference for CLOB client pre-initialization."""
        self._trading_service = trading_service

    def set_websocket_service(self, websocket_service) -> None:
        """Set websocket service reference for deposit monitoring of new wallets (legacy)."""
        self._websocket_service = websocket_service

    def set_webhook_manager(self, webhook_manager) -> None:
        """Set Alchemy webhook manager for deposit monitoring of new wallets."""
        self._webhook_manager = webhook_manager

    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        return await self.user_repo.get_by_telegram_id(telegram_id)

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by internal ID."""
        return await self.user_repo.get_by_id(user_id)

    async def register_user(
        self,
        telegram_id: int,
        telegram_username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> tuple[User, Wallet]:
        """
        Register a new user and generate EOA wallet.

        Args:
            telegram_id: Telegram user ID
            telegram_username: Telegram username
            first_name: User's first name
            last_name: User's last name

        Returns:
            Tuple of (User, Wallet) objects
        """
        # Create user
        user = await self.user_repo.create(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            first_name=first_name,
            last_name=last_name,
        )

        # Generate EOA wallet (standard Ethereum wallet)
        address, private_key = WalletGenerator.create_wallet()

        # Encrypt private key
        encrypted_key, salt = self.encryption.encrypt(private_key)

        # Store wallet as EOA
        wallet = await self.wallet_repo.create(
            user_id=user.id,
            address=address,
            eoa_address=address,  # EOA address is the same
            wallet_type="EOA",
            encrypted_private_key=encrypted_key,
            encryption_salt=salt,
        )

        # Accept license
        await self.user_repo.accept_license(user.id)

        logger.info(f"Registered user {telegram_id} with EOA wallet {address[:10]}...")

        # Add wallet to deposit monitoring (webhook or legacy websocket)
        if self._webhook_manager:
            # Register address with Alchemy webhook
            asyncio.create_task(self._register_webhook_address(address))
        elif self._websocket_service:
            # Legacy: add to websocket monitoring
            await self._websocket_service.add_wallet(address)

        # Pre-initialize CLOB client so first trade is faster
        if self._trading_service:
            asyncio.create_task(self._init_clob_client(user.id))

        return user, wallet

    async def _init_clob_client(self, user_id: int) -> None:
        """Pre-initialize CLOB client for faster first trade."""
        try:
            if self._trading_service:
                await self._trading_service._get_clob_client(user_id)
                logger.info(f"CLOB client pre-initialized for user {user_id}")
        except Exception as e:
            # Don't fail registration if CLOB init fails
            logger.warning(f"Failed to pre-initialize CLOB client: {e}")

    async def _register_webhook_address(self, address: str) -> None:
        """Register wallet address with Alchemy webhook for deposit monitoring."""
        try:
            if self._webhook_manager:
                await self._webhook_manager.add_addresses([address])
                logger.info(f"Registered {address[:10]}... with Alchemy webhook")
        except Exception as e:
            # Don't fail registration if webhook registration fails
            logger.warning(f"Failed to register address with webhook: {e}")

    async def generate_referral_code_for_user(self, user_id: int) -> str:
        """
        Generate and set a unique referral code for a user.

        Args:
            user_id: User ID

        Returns:
            Generated referral code
        """
        # Import here to avoid circular dependency
        from services.referral_service import ReferralService

        # Get database from user_repo
        referral_service = ReferralService(self.user_repo.db)
        code = await referral_service.generate_referral_code()

        # Set the code
        await self.user_repo.set_referral_code(user_id, code)

        logger.info(f"Generated referral code {code} for user {user_id}")
        return code

    async def get_wallet(self, telegram_id: int) -> Optional[Wallet]:
        """Get wallet for user."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return None
        return await self.wallet_repo.get_by_user_id(user.id)

    async def get_wallet_by_user_id(self, user_id: int) -> Optional[Wallet]:
        """Get wallet by user ID."""
        return await self.wallet_repo.get_by_user_id(user_id)

    async def get_private_key(self, user_id: int) -> Optional[str]:
        """
        Get decrypted private key for user.

        Args:
            user_id: User ID

        Returns:
            Decrypted private key or None
        """
        wallet = await self.wallet_repo.get_by_user_id(user_id)
        if not wallet:
            return None

        return self.encryption.decrypt(
            wallet.encrypted_private_key,
            wallet.encryption_salt,
        )

    async def get_user_stats(self, telegram_id: int) -> Dict[str, Any]:
        """
        Get user statistics for main menu.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Dict with portfolio_value, usdc_balance, open_orders
        """
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return {
                "portfolio_value": 0.0,
                "usdc_balance": 0.0,
                "open_orders": 0,
                "net_worth": 0.0,
            }

        wallet = await self.wallet_repo.get_by_user_id(user.id)

        # Import here to avoid circular imports
        from database.repositories import OrderRepository, PositionRepository

        # Get database from wallet repo
        db = self.wallet_repo.db
        order_repo = OrderRepository(db)
        position_repo = PositionRepository(db)

        open_orders = await order_repo.count_open_orders(user.id)
        portfolio_value = await position_repo.get_total_value(user.id)

        # Get real-time USDC.e balance from blockchain
        from core.blockchain.balance import get_balance_service
        balance_service = get_balance_service()
        usdc_balance = balance_service.get_balance(wallet.address) if wallet else 0.0

        return {
            "portfolio_value": portfolio_value,
            "usdc_balance": usdc_balance,
            "open_orders": open_orders,
            "net_worth": portfolio_value + usdc_balance,
        }

    async def is_registered(self, telegram_id: int) -> bool:
        """Check if user is registered."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        return user is not None and user.license_accepted

    async def get_user_settings(self, telegram_id: int) -> Dict[str, Any]:
        """
        Get user settings with defaults applied.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Settings dict with all defaults
        """
        from database.models.user import get_settings_with_defaults

        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return get_settings_with_defaults({})

        return get_settings_with_defaults(user.settings)

    async def update_user_setting(
        self,
        telegram_id: int,
        key: str,
        value: Any,
    ) -> Dict[str, Any]:
        """
        Update a single setting for user.

        Args:
            telegram_id: Telegram user ID
            key: Setting key to update
            value: New value

        Returns:
            Updated settings dict
        """
        from database.models.user import get_settings_with_defaults

        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            raise ValueError("User not found")

        # Get current settings and update
        current = get_settings_with_defaults(user.settings)
        current[key] = value

        # Save to database
        await self.user_repo.update_settings(user.id, current)

        logger.info(f"Updated setting {key}={value} for user {telegram_id}")

        return current

    async def get_user_setting(
        self,
        telegram_id: int,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a single setting value.

        Args:
            telegram_id: Telegram user ID
            key: Setting key
            default: Default if not set

        Returns:
            Setting value or default
        """
        settings = await self.get_user_settings(telegram_id)
        return settings.get(key, default)

    # Two-Factor Authentication Methods

    async def setup_2fa(self, telegram_id: int) -> tuple[str, Any]:
        """
        Generate and store TOTP secret, return QR code.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Tuple of (secret_for_display, qr_code_image)
        """
        from core.security.two_factor import TwoFactorAuth

        user = await self.get_user(telegram_id)
        if not user:
            raise ValueError("User not found")

        # Generate 2FA secret and QR code
        username = user.telegram_username or f"user_{telegram_id}"
        secret, provisioning_uri, qr_code = TwoFactorAuth.setup_2fa(username)

        # Encrypt and store the secret
        encrypted_secret, salt = self.encryption.encrypt(secret)
        await self.user_repo.update_totp_secret(user.id, encrypted_secret, salt)

        return secret, qr_code

    async def verify_2fa_token(self, telegram_id: int, token: str) -> bool:
        """
        Verify TOTP token for a user.

        Args:
            telegram_id: Telegram user ID
            token: 6-digit TOTP code

        Returns:
            True if token is valid
        """
        from core.security.two_factor import TwoFactorAuth

        user = await self.get_user(telegram_id)
        if not user or not user.totp_secret or not user.totp_secret_salt:
            return False

        # Decrypt the secret
        secret = self.encryption.decrypt(user.totp_secret, user.totp_secret_salt)

        # Verify the token
        is_valid = TwoFactorAuth.verify_token(secret, token)

        # Mark as verified on first successful verification
        if is_valid and not user.totp_verified_at:
            await self.user_repo.mark_totp_verified(user.id)

        return is_valid

    async def is_2fa_enabled(self, telegram_id: int) -> bool:
        """
        Check if user has 2FA enabled and verified.

        Args:
            telegram_id: Telegram user ID

        Returns:
            True if 2FA is enabled and verified
        """
        user = await self.get_user(telegram_id)
        if not user:
            return False

        # Check both settings flag and that secret exists and was verified
        settings = await self.get_user_settings(telegram_id)
        has_2fa_enabled = settings.get("two_factor_enabled", False)

        return (
            has_2fa_enabled
            and user.totp_secret is not None
            and user.totp_verified_at is not None
        )

    async def disable_2fa(self, telegram_id: int) -> None:
        """
        Disable 2FA for user.

        Args:
            telegram_id: Telegram user ID
        """
        user = await self.get_user(telegram_id)
        if not user:
            return

        # Clear TOTP secret from database
        await self.user_repo.clear_totp_secret(user.id)

        # Update settings
        await self.update_user_setting(telegram_id, "two_factor_enabled", False)

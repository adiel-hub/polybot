"""User service for registration and wallet management."""

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
    ) -> str:
        """
        Register a new user and generate wallet.

        Args:
            telegram_id: Telegram user ID
            telegram_username: Telegram username
            first_name: User's first name
            last_name: User's last name

        Returns:
            Generated wallet address
        """
        # Create user
        user = await self.user_repo.create(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            first_name=first_name,
            last_name=last_name,
        )

        # Generate wallet
        address, private_key = WalletGenerator.create_wallet()

        # Encrypt private key
        encrypted_key, salt = self.encryption.encrypt(private_key)

        # Store wallet
        await self.wallet_repo.create(
            user_id=user.id,
            address=address,
            encrypted_private_key=encrypted_key,
            encryption_salt=salt,
        )

        # Accept license
        await self.user_repo.accept_license(user.id)

        logger.info(f"Registered user {telegram_id} with wallet {address[:10]}...")

        return address

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
        from database.connection import Database

        # Get database from wallet repo
        db = self.wallet_repo.db
        order_repo = OrderRepository(db)
        position_repo = PositionRepository(db)

        open_orders = await order_repo.count_open_orders(user.id)
        portfolio_value = await position_repo.get_total_value(user.id)
        usdc_balance = wallet.usdc_balance if wallet else 0.0

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

"""User service for registration and wallet management."""

import asyncio
import logging
from typing import Optional, Dict, Any

from database.connection import Database
from database.repositories import UserRepository, WalletRepository
from database.models import User, Wallet
from core.wallet import WalletGenerator, KeyEncryption
from core.polymarket import PolymarketRelayer

logger = logging.getLogger(__name__)

# Polymarket CLOB exchange contract for USDC approval
CLOB_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"


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
    ) -> tuple[User, Wallet]:
        """
        Register a new user and generate Safe wallet.

        New users get Safe wallets for full gasless experience.
        Safe wallets don't require token approvals.

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

        # Generate Safe wallet (EOA + derived Safe address)
        safe_address, eoa_address, private_key = WalletGenerator.create_safe_wallet()

        # Encrypt private key (EOA signer key)
        encrypted_key, salt = self.encryption.encrypt(private_key)

        # Store wallet with Safe configuration
        wallet = await self.wallet_repo.create(
            user_id=user.id,
            address=safe_address,  # Safe address is the primary address
            eoa_address=eoa_address,  # EOA is the signer
            wallet_type="SAFE",
            encrypted_private_key=encrypted_key,
            encryption_salt=salt,
        )

        # Accept license
        await self.user_repo.accept_license(user.id)

        logger.info(
            f"Registered user {telegram_id} with Safe wallet {safe_address[:10]}... "
            f"(signer: {eoa_address[:10]}...)"
        )

        # Trigger background task to deploy Safe and set up all 6 approvals
        # This ensures first trade is instant - no waiting for approvals
        logger.info(
            f"Starting background approval setup for Safe {safe_address[:10]}..."
        )
        asyncio.create_task(
            self._setup_wallet_approvals(
                safe_address=safe_address,
                eoa_address=eoa_address,
                private_key=private_key,
            )
        )

        return user, wallet

    async def _setup_wallet_approvals(
        self,
        safe_address: str,
        eoa_address: str,
        private_key: str,
    ) -> None:
        """
        Set up all 6 token approvals for a new Safe wallet via relayer (gasless).

        Polymarket requires these approvals for trading:
        1. USDC approval for CTF Exchange
        2. USDC approval for Neg Risk CTF Exchange
        3. USDC approval for Neg Risk Adapter
        4. CTF operator approval for CTF Exchange
        5. CTF operator approval for Neg Risk CTF Exchange
        6. CTF operator approval for Neg Risk Adapter

        This runs in the background after wallet creation so the first trade is instant.

        Args:
            safe_address: Safe wallet address
            eoa_address: EOA signer address
            private_key: Decrypted private key for signing
        """
        try:
            relayer = PolymarketRelayer()
            if not relayer.is_configured():
                logger.info("Relayer not configured, skipping pre-approval")
                return

            logger.info(f"Setting up all 6 approvals for Safe wallet {safe_address[:10]}...")

            # First check if Safe is deployed - if not, deploy it
            is_deployed = await relayer.verify_safe_deployed(safe_address)
            if not is_deployed:
                logger.info(f"Safe {safe_address[:10]}... not deployed yet, deploying first...")
                deploy_result = await relayer.deploy_safe(
                    private_key=private_key,
                    eoa_address=eoa_address,
                    safe_address=safe_address,
                )
                if not deploy_result.success:
                    logger.warning(
                        f"Safe deployment failed for {safe_address[:10]}...: {deploy_result.error}"
                    )
                    await relayer.close()
                    return

                # Wait for deployment to confirm
                if deploy_result.tx_hash:
                    confirmed = await relayer.wait_for_transaction(deploy_result.tx_hash, timeout=60)
                    if not confirmed:
                        logger.warning(f"Safe deployment not confirmed for {safe_address[:10]}...")
                        await relayer.close()
                        return

                logger.info(f"Safe {safe_address[:10]}... deployed successfully")

                # Update database to mark Safe as deployed
                wallet = await self.wallet_repo.get_by_address(safe_address)
                if wallet:
                    await self.wallet_repo.mark_safe_deployed(wallet.id)

            # Now set up all allowances
            result = await relayer.setup_all_allowances(
                safe_address=safe_address,
                private_key=private_key,
            )
            await relayer.close()

            if result.success:
                logger.info(
                    f"All 6 approvals set for Safe {safe_address[:10]}... "
                    f"({result.data.get('approvals_count', 6)} approvals)"
                )
                # Mark wallet as approved in database
                wallet = await self.wallet_repo.get_by_address(safe_address)
                if wallet:
                    await self.wallet_repo.mark_usdc_approved(wallet.id)
            else:
                # Don't fail registration if approval fails - it can be done on first trade
                logger.warning(
                    f"Pre-approval setup incomplete for {safe_address[:10]}...: {result.error}"
                )

        except Exception as e:
            # Don't fail registration if approval fails
            logger.error(f"Pre-approval setup failed: {e}")

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
        from database.connection import Database

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

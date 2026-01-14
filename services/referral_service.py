"""Referral service for managing referral program."""

import logging
import secrets
import string
from typing import Dict, Any, Optional, Tuple

from database.connection import Database
from database.repositories import UserRepository, WalletRepository, ReferralRepository

logger = logging.getLogger(__name__)


class ReferralService:
    """Service for referral program operations."""

    TIER_RATES = {1: 0.25, 2: 0.05, 3: 0.03}
    TRADING_FEE_RATE = 0.005  # 0.5% Polymarket fee
    MIN_CLAIM_AMOUNT = 5.0

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.wallet_repo = WalletRepository(db)
        self.referral_repo = ReferralRepository(db)

    async def generate_referral_code(self) -> str:
        """
        Generate unique 7-character alphanumeric referral code.

        Format: lowercase letters and digits (e.g., '1184qzv')
        """
        chars = string.ascii_lowercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(7))
            # Check if code already exists
            existing = await self.user_repo.get_by_referral_code(code)
            if not existing:
                return code

    async def link_referral(self, new_user_id: int, referral_code: str) -> bool:
        """
        Link new user to referrer during registration.

        Args:
            new_user_id: The new user's ID
            referral_code: The referral code used

        Returns:
            True if successfully linked, False otherwise
        """
        try:
            # Find referrer by code
            referrer = await self.user_repo.get_by_referral_code(referral_code)
            if not referrer:
                logger.warning(f"Referral code {referral_code} not found")
                return False

            # Don't allow self-referral
            if referrer.id == new_user_id:
                logger.warning(f"User {new_user_id} attempted self-referral")
                return False

            # Link the referral
            await self.user_repo.set_referrer(new_user_id, referrer.id)
            logger.info(f"User {new_user_id} linked to referrer {referrer.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to link referral: {e}")
            return False

    async def process_trade_commission(
        self,
        user_id: int,
        order_id: int,
        trade_amount: float,
    ) -> None:
        """
        Calculate and credit commissions to referral chain (up to 3 tiers).

        Args:
            user_id: The user who placed the trade
            order_id: The order ID
            trade_amount: The trade amount in USDC
        """
        try:
            # Calculate trade fee
            trade_fee = trade_amount * self.TRADING_FEE_RATE

            # Get referral chain (who should receive commissions)
            chain = await self.referral_repo.get_referral_chain(user_id)

            if not chain:
                # No referrers to pay
                return

            # Process each tier
            for referrer_id, tier in chain:
                commission_rate = self.TIER_RATES.get(tier, 0.0)
                commission_amount = trade_fee * commission_rate

                # Create commission record
                await self.referral_repo.create_commission(
                    referrer_id=referrer_id,
                    referee_id=user_id,
                    order_id=order_id,
                    tier=tier,
                    trade_amount=trade_amount,
                    trade_fee=trade_fee,
                    commission_rate=commission_rate,
                    commission_amount=commission_amount,
                )

                # Credit commission balance
                await self.user_repo.add_commission_balance(referrer_id, commission_amount)

                logger.info(
                    f"Credited ${commission_amount:.2f} to user {referrer_id} "
                    f"(Tier {tier}) for order {order_id}"
                )

        except Exception as e:
            logger.error(f"Failed to process trade commission: {e}")

    async def get_referral_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get user's referral statistics.

        Returns:
            {
                "referral_counts": {"t1": 5, "t2": 12, "t3": 8},
                "total_referrals": 25,
                "lifetime_earned": 150.50,
                "total_claimed": 100.00,
                "claimable": 50.50,
                "referral_code": "1184qzv"
            }
        """
        try:
            logger.info(f"[GET_REFERRAL_STATS] Getting stats for user_id={user_id}")
            # Get user info
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                logger.warning(f"[GET_REFERRAL_STATS] User {user_id} not found, returning empty stats")
                return self._empty_stats()

            logger.info(f"[GET_REFERRAL_STATS] User {user_id} found. referral_code='{user.referral_code}'")

            # Get referral counts and commission stats
            stats = await self.referral_repo.get_referral_stats(user_id)

            result = {
                "referral_counts": stats["referral_counts"],
                "total_referrals": stats["total_referrals"],
                "lifetime_earned": user.total_earned,
                "total_claimed": user.total_claimed,
                "claimable": user.commission_balance,
                "referral_code": user.referral_code or "",
            }
            logger.info(f"[GET_REFERRAL_STATS] Returning stats for user {user_id}: {result}")
            return result

        except Exception as e:
            logger.error(f"[GET_REFERRAL_STATS] Failed to get referral stats for user {user_id}: {e}", exc_info=True)
            return self._empty_stats()

    def _empty_stats(self) -> Dict[str, Any]:
        """Return empty stats structure."""
        return {
            "referral_counts": {"t1": 0, "t2": 0, "t3": 0},
            "total_referrals": 0,
            "lifetime_earned": 0.0,
            "total_claimed": 0.0,
            "claimable": 0.0,
            "referral_code": "",
        }

    async def get_referral_link(self, user_id: int, bot_username: str = "TradePolyBot") -> str:
        """
        Get referral link for a user.

        Args:
            user_id: The user's ID
            bot_username: Telegram bot username (default: TradePolyBot)

        Returns:
            Referral link (e.g., https://t.me/TradePolyBot?start=ref_1184qzv)
        """
        logger.info(f"[GET_REFERRAL_LINK] Getting link for user_id={user_id}, bot_username={bot_username}")
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            logger.error(f"[GET_REFERRAL_LINK] User {user_id} not found in database")
            return ""

        if not user.referral_code:
            logger.warning(f"[GET_REFERRAL_LINK] User {user_id} has no referral_code (value: {user.referral_code})")
            return ""

        link = f"https://t.me/{bot_username}?start=ref_{user.referral_code}"
        logger.info(f"[GET_REFERRAL_LINK] Generated link for user {user_id}: '{link}'")
        return link

    async def claim_earnings(self, user_id: int) -> Tuple[bool, str]:
        """
        Transfer commission balance to user's wallet.

        Args:
            user_id: The user's ID

        Returns:
            (success, message)
        """
        try:
            # Get user
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                return False, "User not found"

            # Check minimum claim amount
            if user.commission_balance < self.MIN_CLAIM_AMOUNT:
                return False, f"Minimum claim amount is ${self.MIN_CLAIM_AMOUNT:.2f}"

            # Get wallet
            wallet = await self.wallet_repo.get_by_user_id(user_id)
            if not wallet:
                return False, "Wallet not found"

            claim_amount = user.commission_balance

            # Transfer commission to wallet balance
            await self.wallet_repo.add_balance(wallet.id, claim_amount)

            # Update commission balances
            success = await self.user_repo.claim_commission(user_id, claim_amount)

            if success:
                logger.info(f"User {user_id} claimed ${claim_amount:.2f} in referral earnings")
                return True, f"Successfully claimed ${claim_amount:.2f}"
            else:
                return False, "Claim failed"

        except Exception as e:
            logger.error(f"Failed to claim earnings: {e}")
            return False, f"Claim failed: {str(e)}"

    async def get_commission_history(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list:
        """
        Get recent commission earnings history.

        Args:
            user_id: The user's ID
            limit: Maximum number of records to return

        Returns:
            List of commission records
        """
        try:
            return await self.referral_repo.get_user_commissions(user_id, limit)
        except Exception as e:
            logger.error(f"Failed to get commission history: {e}")
            return []

"""Referral repository for database operations."""

from typing import Optional, List, Dict, Any
from datetime import datetime

from database.connection import Database
from database.models import ReferralCommission


class ReferralRepository:
    """Repository for referral operations."""

    def __init__(self, db: Database):
        self.db = db

    async def create_commission(
        self,
        referrer_id: int,
        referee_id: int,
        order_id: int,
        tier: int,
        trade_amount: float,
        trade_fee: float,
        commission_rate: float,
        commission_amount: float,
    ) -> ReferralCommission:
        """Create a new referral commission record."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            INSERT INTO referral_commissions
            (referrer_id, referee_id, order_id, tier, trade_amount, trade_fee, commission_rate, commission_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (referrer_id, referee_id, order_id, tier, trade_amount, trade_fee, commission_rate, commission_amount),
        )
        await conn.commit()

        return await self.get_by_id(cursor.lastrowid)

    async def get_by_id(self, commission_id: int) -> Optional[ReferralCommission]:
        """Get commission by ID."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM referral_commissions WHERE id = ?",
            (commission_id,),
        )
        row = await cursor.fetchone()
        if row:
            return ReferralCommission.from_row(row)
        return None

    async def get_user_commissions(
        self,
        user_id: int,
        limit: int = 50,
    ) -> List[ReferralCommission]:
        """Get recent commission earnings for a user."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT * FROM referral_commissions
            WHERE referrer_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [ReferralCommission.from_row(row) for row in rows]

    async def get_referral_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get referral statistics for a user.

        Returns counts per tier and total earnings.
        """
        conn = await self.db.get_connection()

        # Count referrals per tier
        tier_counts = {"t1": 0, "t2": 0, "t3": 0}

        # Tier 1: direct referrals (users where referrer_id = user_id)
        cursor = await conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE referrer_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        tier_counts["t1"] = row["count"]

        # Tier 2: referrals of Tier 1 users
        cursor = await conn.execute(
            """
            SELECT COUNT(*) as count FROM users
            WHERE referrer_id IN (SELECT id FROM users WHERE referrer_id = ?)
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        tier_counts["t2"] = row["count"]

        # Tier 3: referrals of Tier 2 users
        cursor = await conn.execute(
            """
            SELECT COUNT(*) as count FROM users
            WHERE referrer_id IN (
                SELECT id FROM users WHERE referrer_id IN (
                    SELECT id FROM users WHERE referrer_id = ?
                )
            )
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        tier_counts["t3"] = row["count"]

        # Get total commission earned from this user's referrals
        cursor = await conn.execute(
            "SELECT SUM(commission_amount) as total FROM referral_commissions WHERE referrer_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        total_from_commissions = row["total"] or 0.0

        return {
            "referral_counts": tier_counts,
            "total_referrals": tier_counts["t1"] + tier_counts["t2"] + tier_counts["t3"],
            "total_commission_earned": total_from_commissions,
        }

    async def get_referral_chain(self, user_id: int) -> List[tuple]:
        """
        Get the referral chain for a user (who should receive commissions).

        Returns: [(referrer_id, tier), ...] up to 3 tiers
        """
        conn = await self.db.get_connection()
        chain = []

        current_id = user_id
        for tier in range(1, 4):  # Tiers 1, 2, 3
            cursor = await conn.execute(
                "SELECT referrer_id FROM users WHERE id = ?",
                (current_id,),
            )
            row = await cursor.fetchone()
            if not row or not row["referrer_id"]:
                break

            referrer_id = row["referrer_id"]
            chain.append((referrer_id, tier))
            current_id = referrer_id

        return chain

    async def get_commissions_by_order(self, order_id: int) -> List[ReferralCommission]:
        """Get all commissions generated by a specific order."""
        conn = await self.db.get_connection()
        cursor = await conn.execute(
            "SELECT * FROM referral_commissions WHERE order_id = ?",
            (order_id,),
        )
        rows = await cursor.fetchall()
        return [ReferralCommission.from_row(row) for row in rows]

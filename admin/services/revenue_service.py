"""Revenue analytics service for admin panel."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List
from database.connection import Database

logger = logging.getLogger(__name__)


class RevenueService:
    """Service for revenue and commission analytics."""

    def __init__(self, db: Database):
        self.db = db

    async def get_total_revenue(self) -> Dict:
        """Get total revenue (commissions) with pending/claimed breakdown."""
        conn = await self.db.get_connection()

        # Total commissions from referral_commissions table
        cursor = await conn.execute(
            "SELECT SUM(commission_amount) as total FROM referral_commissions"
        )
        row = await cursor.fetchone()
        total_commissions = row[0] if row and row[0] else 0.0

        # Pending and claimed from users table
        cursor = await conn.execute(
            """
            SELECT
                SUM(commission_balance) as pending,
                SUM(total_claimed) as claimed
            FROM users
            """
        )
        row = await cursor.fetchone()
        pending = row[0] if row and row[0] else 0.0
        claimed = row[1] if row and row[1] else 0.0

        return {
            "total": total_commissions,
            "pending": pending,
            "claimed": claimed,
        }

    async def get_revenue_by_tier(self) -> List[Dict]:
        """Get commission breakdown by tier (1, 2, 3)."""
        conn = await self.db.get_connection()

        cursor = await conn.execute(
            """
            SELECT
                tier,
                SUM(commission_amount) as total,
                COUNT(*) as count
            FROM referral_commissions
            GROUP BY tier
            ORDER BY tier
            """
        )
        rows = await cursor.fetchall()

        tiers = []
        for row in rows:
            tiers.append({
                "tier": row[0],
                "total": row[1],
                "count": row[2],
            })

        return tiers

    async def get_revenue_by_period(self, days: int = 30) -> List[Dict]:
        """Get daily revenue for last N days."""
        conn = await self.db.get_connection()

        cursor = await conn.execute(
            f"""
            SELECT
                DATE(created_at) as date,
                SUM(commission_amount) as revenue,
                COUNT(*) as transactions
            FROM referral_commissions
            WHERE created_at >= datetime('now', '-{days} days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            """
        )
        rows = await cursor.fetchall()

        daily_revenue = []
        for row in rows:
            daily_revenue.append({
                "date": row[0],
                "revenue": row[1],
                "transactions": row[2],
            })

        return daily_revenue

    async def get_top_earners(self, limit: int = 10) -> List[Dict]:
        """Get top earning referrers."""
        conn = await self.db.get_connection()

        cursor = await conn.execute(
            f"""
            SELECT
                rc.referrer_id,
                u.telegram_username,
                u.first_name,
                SUM(rc.commission_amount) as total_earned,
                COUNT(*) as total_commissions,
                u.commission_balance as pending
            FROM referral_commissions rc
            JOIN users u ON rc.referrer_id = u.id
            GROUP BY rc.referrer_id
            ORDER BY total_earned DESC
            LIMIT {limit}
            """
        )
        rows = await cursor.fetchall()

        top_earners = []
        for row in rows:
            top_earners.append({
                "user_id": row[0],
                "username": row[1] or "Unknown",
                "first_name": row[2] or "",
                "total_earned": row[3],
                "commission_count": row[4],
                "pending": row[5] or 0.0,
            })

        return top_earners

    async def get_revenue_trends(self) -> Dict:
        """Get revenue growth trends and projections."""
        conn = await self.db.get_connection()

        # Last 30 days average
        cursor = await conn.execute(
            """
            SELECT AVG(daily_revenue) as avg_daily
            FROM (
                SELECT DATE(created_at) as date, SUM(commission_amount) as daily_revenue
                FROM referral_commissions
                WHERE created_at >= datetime('now', '-30 days')
                GROUP BY DATE(created_at)
            )
            """
        )
        row = await cursor.fetchone()
        avg_daily_30d = row[0] if row and row[0] else 0.0

        # Last 7 days average
        cursor = await conn.execute(
            """
            SELECT AVG(daily_revenue) as avg_daily
            FROM (
                SELECT DATE(created_at) as date, SUM(commission_amount) as daily_revenue
                FROM referral_commissions
                WHERE created_at >= datetime('now', '-7 days')
                GROUP BY DATE(created_at)
            )
            """
        )
        row = await cursor.fetchone()
        avg_daily_7d = row[0] if row and row[0] else 0.0

        # Calculate growth
        growth_rate = 0.0
        if avg_daily_30d > 0:
            growth_rate = ((avg_daily_7d - avg_daily_30d) / avg_daily_30d) * 100

        # Projected monthly revenue
        projected_monthly = avg_daily_7d * 30

        return {
            "avg_daily_30d": avg_daily_30d,
            "avg_daily_7d": avg_daily_7d,
            "growth_rate": growth_rate,
            "projected_monthly": projected_monthly,
            "trend": "increasing" if growth_rate > 5 else "decreasing" if growth_rate < -5 else "stable",
        }

    async def get_commission_rate(self) -> Dict:
        """Get average commission per order and conversion metrics."""
        conn = await self.db.get_connection()

        # Average commission amount
        cursor = await conn.execute(
            "SELECT AVG(commission_amount), COUNT(*) FROM referral_commissions"
        )
        row = await cursor.fetchone()
        avg_commission = row[0] if row and row[0] else 0.0
        total_commissions = row[1] if row else 0

        # Total orders (to calculate commission conversion)
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'FILLED'"
        )
        row = await cursor.fetchone()
        total_orders = row[0] if row else 0

        # Commission conversion rate
        conversion_rate = 0.0
        if total_orders > 0:
            conversion_rate = (total_commissions / total_orders) * 100

        return {
            "avg_commission": avg_commission,
            "total_commissions": total_commissions,
            "total_orders": total_orders,
            "conversion_rate": conversion_rate,
        }

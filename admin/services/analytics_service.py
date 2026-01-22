"""Advanced analytics service for admin panel."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List
from database.connection import Database

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for comprehensive business analytics."""

    def __init__(self, db: Database):
        self.db = db

    # ==================== USER ANALYTICS ====================

    async def get_user_growth(self, period: str = "daily", days: int = 30) -> Dict:
        """
        Get user growth statistics.

        Args:
            period: 'daily', 'weekly', or 'monthly'
            days: Number of days to analyze
        """
        conn = await self.db.get_connection()

        # Total users
        row = await conn.fetchrow("SELECT COUNT(*) FROM users")
        row = row
        total_users = row[0] if row else 0

        # New users in period
        row = await conn.fetchrow(
            f"""
            SELECT COUNT(*) FROM users
            WHERE created_at >= NOW() - INTERVAL '{days} days'
            """
        )
        new_users = row[0] if row else 0

        # Daily breakdown
        row = await conn.fetchrow(
            f"""
            SELECT
                created_at::DATE as date,
                COUNT(*) as count
            FROM users
            WHERE created_at >= NOW() - INTERVAL '{days} days'
            GROUP BY created_at::DATE
            ORDER BY date DESC
            """
        )

        daily_growth = [{"date": row[0], "count": row[1]} for row in rows]

        return {
            "total_users": total_users,
            "new_users": new_users,
            "period_days": days,
            "daily_growth": daily_growth,
            "avg_daily": new_users / days if days > 0 else 0,
        }

    async def get_active_user_rate(self) -> Dict:
        """Get active vs inactive user statistics."""
        conn = await self.db.get_connection()

        rows = await conn.fetch(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as inactive
            FROM users
            """
        )

        total = row[0] if row else 0
        active = row[1] if row else 0
        inactive = row[2] if row else 0

        active_rate = (active / total * 100) if total > 0 else 0

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "active_rate": active_rate,
        }

    async def get_referral_conversion(self) -> Dict:
        """Get referral conversion statistics."""
        conn = await self.db.get_connection()

        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN referrer_id IS NOT NULL THEN 1 ELSE 0 END) as with_referrer
            FROM users
            """
        )

        total = row[0] if row else 0
        with_referrer = row[1] if row and row[1] else 0

        conversion_rate = (with_referrer / total * 100) if total > 0 else 0

        return {
            "total_users": total,
            "referred_users": with_referrer,
            "organic_users": total - with_referrer,
            "conversion_rate": conversion_rate,
        }

    # ==================== TRADING ANALYTICS ====================

    async def get_total_volume(self, days: int = None) -> Dict:
        """Get trading volume statistics."""
        conn = await self.db.get_connection()

        # Build query with optional time filter
        time_filter = f"WHERE created_at >= NOW() - INTERVAL '{days} days'" if days else ""

        # Total volume
        row = await conn.fetchrow(
            f"""
            SELECT
                SUM(size) as total_volume,
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'FILLED' THEN size ELSE 0 END) as filled_volume,
                SUM(CASE WHEN status = 'FILLED' THEN 1 ELSE 0 END) as filled_orders
            FROM orders
            {time_filter}
            """
        )

        total_volume = row[0] if row and row[0] else 0.0
        total_orders = row[1] if row else 0
        filled_volume = row[2] if row and row[2] else 0.0
        filled_orders = row[3] if row else 0

        return {
            "total_volume": total_volume,
            "filled_volume": filled_volume,
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "period_days": days,
        }

    async def get_average_order_size(self) -> float:
        """Get average order size."""
        conn = await self.db.get_connection()

        row = await conn.fetchrow(
            "SELECT AVG(size) FROM orders WHERE status = 'FILLED'"
        )

        return row[0] if row and row[0] else 0.0

    async def get_order_completion_rate(self) -> Dict:
        """Get order fill/completion rate."""
        conn = await self.db.get_connection()

        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'FILLED' THEN 1 ELSE 0 END) as filled,
                SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) as cancelled,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed
            FROM orders
            """
        )

        total = row[0] if row else 0
        filled = row[1] if row else 0
        cancelled = row[2] if row else 0
        failed = row[3] if row else 0

        fill_rate = (filled / total * 100) if total > 0 else 0

        return {
            "total": total,
            "filled": filled,
            "cancelled": cancelled,
            "failed": failed,
            "fill_rate": fill_rate,
        }

    async def get_volume_by_outcome(self) -> Dict:
        """Get volume breakdown by YES/NO."""
        conn = await self.db.get_connection()

        row = await conn.fetchrow(
            """
            SELECT
                outcome,
                SUM(size) as volume,
                COUNT(*) as count
            FROM orders
            WHERE status = 'FILLED'
            GROUP BY outcome
            """
        )

        yes_volume = 0.0
        no_volume = 0.0
        yes_count = 0
        no_count = 0

        for row in rows:
            if row[0] == "YES":
                yes_volume = row[1]
                yes_count = row[2]
            elif row[0] == "NO":
                no_volume = row[1]
                no_count = row[2]

        total_volume = yes_volume + no_volume

        return {
            "yes_volume": yes_volume,
            "no_volume": no_volume,
            "yes_count": yes_count,
            "no_count": no_count,
            "yes_percentage": (yes_volume / total_volume * 100) if total_volume > 0 else 0,
            "no_percentage": (no_volume / total_volume * 100) if total_volume > 0 else 0,
        }

    # ==================== FINANCIAL ANALYTICS ====================

    async def get_total_aum(self) -> float:
        """Get total Assets Under Management (sum of all wallet balances)."""
        conn = await self.db.get_connection()

        row = await conn.fetchrow(
            "SELECT SUM(usdc_balance) FROM wallets"
        )

        return row[0] if row and row[0] else 0.0

    async def get_net_deposits(self) -> Dict:
        """Get net deposits (deposits - withdrawals)."""
        conn = await self.db.get_connection()

        # Total confirmed deposits
        row = await conn.fetchrow(
            """
            SELECT SUM(amount) FROM deposits
            WHERE status = 'CONFIRMED'
            """
        )
        total_deposits = row[0] if row and row[0] else 0.0

        # Total confirmed withdrawals
        row = await conn.fetchrow(
            """
            SELECT SUM(amount) FROM withdrawals
            WHERE status = 'CONFIRMED'
            """
        )
        total_withdrawals = row[0] if row and row[0] else 0.0

        net_flow = total_deposits - total_withdrawals

        return {
            "total_deposits": total_deposits,
            "total_withdrawals": total_withdrawals,
            "net_flow": net_flow,
        }

    async def get_deposit_withdrawal_trends(self, days: int = 30) -> Dict:
        """Get deposit/withdrawal trends over time."""
        conn = await self.db.get_connection()

        # Daily deposits
        row = await conn.fetchrow(
            f"""
            SELECT
                detected_at::DATE as date,
                SUM(amount) as amount,
                COUNT(*) as count
            FROM deposits
            WHERE status = 'CONFIRMED'
            AND detected_at >= NOW() - INTERVAL '{days} days'
            GROUP BY detected_at::DATE
            ORDER BY date DESC
            """
        )
        deposits = [{"date": row[0], "amount": row[1], "count": row[2]} for row in rows]

        # Daily withdrawals
        rows = await conn.fetch(
            f"""
            SELECT
                created_at::DATE as date,
                SUM(amount) as amount,
                COUNT(*) as count
            FROM withdrawals
            WHERE status = 'CONFIRMED'
            AND created_at >= NOW() - INTERVAL '{days} days'
            GROUP BY created_at::DATE
            ORDER BY date DESC
            """
        )
        withdrawals = [{"date": row[0], "amount": row[1], "count": row[2]} for row in rows]

        return {
            "deposits": deposits,
            "withdrawals": withdrawals,
            "period_days": days,
        }

    async def get_financial_health(self) -> Dict:
        """Get overall financial health metrics."""
        aum = await self.get_total_aum()
        net_deposits_data = await self.get_net_deposits()
        user_count = (await self.get_active_user_rate())["total"]

        avg_balance = aum / user_count if user_count > 0 else 0

        return {
            "aum": aum,
            "total_deposits": net_deposits_data["total_deposits"],
            "total_withdrawals": net_deposits_data["total_withdrawals"],
            "net_flow": net_deposits_data["net_flow"],
            "avg_balance": avg_balance,
            "user_count": user_count,
        }

    # ==================== P&L ANALYTICS ====================

    async def get_platform_pnl(self) -> Dict:
        """Get platform-wide P&L statistics."""
        conn = await self.db.get_connection()

        # Total realized P&L
        row = await conn.fetchrow(
            "SELECT SUM(realized_pnl) FROM positions WHERE realized_pnl IS NOT NULL"
        )
        realized_pnl = row[0] if row and row[0] else 0.0

        # Total unrealized P&L (current open positions)
        row = await conn.fetchrow(
            "SELECT SUM(unrealized_pnl) FROM positions WHERE size > 0"
        )
        unrealized_pnl = row[0] if row and row[0] else 0.0

        total_pnl = realized_pnl + unrealized_pnl

        return {
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
        }

    async def get_win_rate(self) -> Dict:
        """Get win rate statistics."""
        conn = await self.db.get_connection()

        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN realized_pnl = 0 THEN 1 ELSE 0 END) as breakeven
            FROM positions
            WHERE realized_pnl IS NOT NULL
            """
        )

        total = row[0] if row else 0
        wins = row[1] if row else 0
        losses = row[2] if row else 0
        breakeven = row[3] if row else 0

        win_rate = (wins / total * 100) if total > 0 else 0

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": win_rate,
        }

    async def get_user_pnl_distribution(self, limit: int = 10) -> Dict:
        """Get top/bottom performers by P&L."""
        conn = await self.db.get_connection()

        # Top performers
        rows = await conn.fetch(
            f"""
            SELECT
                p.user_id,
                u.telegram_username,
                u.first_name,
                SUM(p.realized_pnl) as total_pnl,
                COUNT(*) as trade_count
            FROM positions p
            JOIN users u ON p.user_id = u.id
            WHERE p.realized_pnl IS NOT NULL
            GROUP BY p.user_id
            ORDER BY total_pnl DESC
            LIMIT {limit}
            """
        )
        top_performers = [
            {
                "user_id": row[0],
                "username": row[1] or "Unknown",
                "first_name": row[2] or "",
                "total_pnl": row[3],
                "trade_count": row[4],
            }
            for row in rows
        ]

        # Bottom performers
        rows = await conn.fetch(
            f"""
            SELECT
                p.user_id,
                u.telegram_username,
                u.first_name,
                SUM(p.realized_pnl) as total_pnl,
                COUNT(*) as trade_count
            FROM positions p
            JOIN users u ON p.user_id = u.id
            WHERE p.realized_pnl IS NOT NULL
            GROUP BY p.user_id
            ORDER BY total_pnl ASC
            LIMIT {limit}
            """
        )
        bottom_performers = [
            {
                "user_id": row[0],
                "username": row[1] or "Unknown",
                "first_name": row[2] or "",
                "total_pnl": row[3],
                "trade_count": row[4],
            }
            for row in rows
        ]

        return {
            "top_performers": top_performers,
            "bottom_performers": bottom_performers,
        }

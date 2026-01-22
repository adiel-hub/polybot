"""Statistics service for admin dashboard."""

import logging
from typing import Any
from database.connection import Database

logger = logging.getLogger(__name__)


class StatsService:
    """Service for aggregating statistics."""

    def __init__(self, db: Database):
        self.db = db

    async def get_quick_stats(self) -> dict[str, Any]:
        """Get quick stats for admin menu."""
        conn = await self.db.get_connection()

        # Total users
        row = await conn.fetchrow("SELECT COUNT(*) FROM users")
        total_users = row[0] if row else 0

        # Active users
        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM users WHERE is_active = TRUE"
        )
        active_users = row[0] if row else 0

        # Total balance
        row = await conn.fetchrow("SELECT COALESCE(SUM(usdc_balance), 0) FROM wallets")
        total_balance = row[0] if row else 0

        # Open orders
        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM orders WHERE status IN ('PENDING', 'OPEN')"
        )
        open_orders = row[0] if row else 0

        # Active positions
        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM positions WHERE size > 0"
        )
        active_positions = row[0] if row else 0

        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_balance": total_balance,
            "open_orders": open_orders,
            "active_positions": active_positions,
        }

    async def get_dashboard_stats(self) -> dict[str, Any]:
        """Get comprehensive stats for dashboard."""
        conn = await self.db.get_connection()

        # User stats
        row = await conn.fetchrow("SELECT COUNT(*) FROM users")
        total_users = row[0] if row else 0

        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM users WHERE is_active = TRUE"
        )
        active_users = row[0] if row else 0

        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM users WHERE is_active = FALSE"
        )
        suspended_users = row[0] if row else 0

        # Financial stats
        row = await conn.fetchrow("SELECT COALESCE(SUM(usdc_balance), 0) FROM wallets")
        total_balance = row[0] if row else 0

        row = await conn.fetchrow(
            "SELECT COALESCE(SUM(amount), 0) FROM deposits WHERE status = 'CONFIRMED'"
        )
        total_deposits = row[0] if row else 0

        row = await conn.fetchrow(
            "SELECT COALESCE(SUM(amount), 0) FROM withdrawals WHERE status = 'CONFIRMED'"
        )
        total_withdrawals = row[0] if row else 0

        # Order stats
        row = await conn.fetchrow("SELECT COUNT(*) FROM orders")
        total_orders = row[0] if row else 0

        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM orders WHERE status IN ('PENDING', 'OPEN')"
        )
        open_orders = row[0] if row else 0

        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM orders WHERE status = 'FILLED'"
        )
        filled_orders = row[0] if row else 0

        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM orders WHERE status = 'FAILED'"
        )
        failed_orders = row[0] if row else 0

        # Position stats
        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM positions WHERE size > 0"
        )
        active_positions = row[0] if row else 0

        row = await conn.fetchrow(
            "SELECT COALESCE(SUM(size * current_price), 0) FROM positions WHERE size > 0"
        )
        total_position_value = row[0] if row else 0

        row = await conn.fetchrow(
            "SELECT COALESCE(SUM(unrealized_pnl), 0) FROM positions WHERE size > 0"
        )
        total_unrealized_pnl = row[0] if row else 0

        # Stop loss stats
        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM stop_loss_orders WHERE is_active = TRUE"
        )
        active_stop_losses = row[0] if row else 0

        # Copy trading stats
        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM copy_traders WHERE is_active = TRUE"
        )
        active_copy_subscriptions = row[0] if row else 0

        row = await conn.fetchrow(
            "SELECT COUNT(DISTINCT trader_address) FROM copy_traders WHERE is_active = TRUE"
        )
        unique_traders_followed = row[0] if row else 0

        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "suspended": suspended_users,
            },
            "financial": {
                "total_balance": total_balance,
                "total_deposits": total_deposits,
                "total_withdrawals": total_withdrawals,
            },
            "orders": {
                "total": total_orders,
                "open": open_orders,
                "filled": filled_orders,
                "failed": failed_orders,
            },
            "positions": {
                "active": active_positions,
                "total_value": total_position_value,
                "unrealized_pnl": total_unrealized_pnl,
            },
            "stop_losses": {
                "active": active_stop_losses,
            },
            "copy_trading": {
                "active_subscriptions": active_copy_subscriptions,
                "unique_traders": unique_traders_followed,
            },
        }

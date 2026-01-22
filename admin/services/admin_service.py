"""Admin service for CRUD operations."""

import logging
from typing import Any, Optional
from database.connection import Database
from database.models.user import User
from database.models.wallet import Wallet
from database.models.order import Order, OrderSide, OrderType, OrderStatus, Outcome
from database.models.position import Position
from database.models.stop_loss import StopLoss
from database.models.copy_trader import CopyTrader

logger = logging.getLogger(__name__)


class AdminService:
    """Service for admin operations."""

    def __init__(self, db: Database):
        self.db = db

    # ==================== USER OPERATIONS ====================

    async def get_users(
        self, limit: int = 10, offset: int = 0, active_only: bool = False
    ) -> list[User]:
        """Get paginated user list."""
        conn = await self.db.get_connection()
        query = "SELECT * FROM users"
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY created_at DESC LIMIT $1 OFFSET $2"

        rows = await conn.fetch(query, (limit, offset))

        return [User(**dict(row)) for row in rows]

    async def count_users(self, active_only: bool = False) -> int:
        """Count total users."""
        conn = await self.db.get_connection()
        query = "SELECT COUNT(*) FROM users"
        if active_only:
            query += " WHERE is_active = TRUE"
        row = await conn.fetchrow(query)
        return row[0] if row else 0

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by internal ID."""
        conn = await self.db.get_connection()
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", (user_id,))
        return User(**dict(row)) if row else None

    async def search_users(self, query: str) -> list[User]:
        """Search users by Telegram ID or username."""
        conn = await self.db.get_connection()
        # Try to find by Telegram ID first
        if query.isdigit():
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1 OR id = $2",
                (int(query), int(query)),
            )
        else:
            # Search by username (remove @ if present)
            search_term = query.lstrip("@")
            rows = await conn.fetch(
                "SELECT * FROM users WHERE telegram_username LIKE $1",
                (f"%{search_term}%",),
            )
        return [User(**dict(row)) for row in rows]

    async def suspend_user(self, user_id: int) -> bool:
        """Suspend a user."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE users SET is_active = FALSE WHERE id = $1", (user_id,)
        )
        await conn.commit()
        return True

    async def activate_user(self, user_id: int) -> bool:
        """Activate a user."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE users SET is_active = TRUE WHERE id = $1", (user_id,)
        )
        await conn.commit()
        return True

    # ==================== WALLET OPERATIONS ====================

    async def get_wallet_by_user_id(self, user_id: int) -> Optional[Wallet]:
        """Get wallet by user ID."""
        conn = await self.db.get_connection()
        rows = await conn.fetch(
            "SELECT * FROM wallets WHERE user_id = $1", (user_id,)
        )
        return Wallet(**dict(row)) if row else None

    async def get_wallets(self, limit: int = 10, offset: int = 0) -> list[Wallet]:
        """Get paginated wallet list."""
        conn = await self.db.get_connection()
        row = await conn.fetchrow(
            "SELECT * FROM wallets ORDER BY usdc_balance DESC LIMIT $1 OFFSET $2",
            (limit, offset),
        )
        return [Wallet(**dict(row)) for row in rows]

    async def count_wallets(self) -> int:
        """Count total wallets."""
        conn = await self.db.get_connection()
        row = await conn.fetchrow("SELECT COUNT(*) FROM wallets")
        return row[0] if row else 0

    async def get_wallet_by_id(self, wallet_id: int) -> Optional[Wallet]:
        """Get wallet by ID."""
        conn = await self.db.get_connection()
        row = await conn.fetchrow(
            "SELECT * FROM wallets WHERE id = $1", (wallet_id,)
        )
        return Wallet(**dict(row)) if row else None

    # ==================== ORDER OPERATIONS ====================

    async def get_orders(
        self,
        limit: int = 10,
        offset: int = 0,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> list[Order]:
        """Get paginated order list."""
        conn = await self.db.get_connection()
        query = "SELECT * FROM orders WHERE 1=1"
        params: list[Any] = []

        if status:
            query += " AND status = $1"
            params.append(status)

        if user_id:
            query += " AND user_id = $1"
            params.append(user_id)

        query += " ORDER BY created_at DESC LIMIT $1 OFFSET $2"
        params.extend([limit, offset])

        row = await conn.fetchrow(query, params)

        orders = []
        for row in rows:
            data = dict(row)
            data["side"] = OrderSide[data["side"]]
            data["order_type"] = OrderType[data["order_type"]]
            data["status"] = OrderStatus[data["status"]]
            data["outcome"] = Outcome[data["outcome"]]
            orders.append(Order(**data))

        return orders

    async def count_orders(
        self, status: Optional[str] = None, user_id: Optional[int] = None
    ) -> int:
        """Count orders."""
        conn = await self.db.get_connection()
        query = "SELECT COUNT(*) FROM orders WHERE 1=1"
        params: list[Any] = []

        if status:
            query += " AND status = $1"
            params.append(status)

        if user_id:
            query += " AND user_id = $1"
            params.append(user_id)

        rows = await conn.fetch(query, params)
        return row[0] if row else 0

    async def get_order_by_id(self, order_id: int) -> Optional[Order]:
        """Get order by ID."""
        conn = await self.db.get_connection()
        row = await conn.fetchrow(
            "SELECT * FROM orders WHERE id = $1", (order_id,)
        )
        if not row:
            return None

        data = dict(row)
        data["side"] = OrderSide[data["side"]]
        data["order_type"] = OrderType[data["order_type"]]
        data["status"] = OrderStatus[data["status"]]
        data["outcome"] = Outcome[data["outcome"]]
        return Order(**data)

    async def cancel_order(self, order_id: int) -> bool:
        """Cancel an order (admin action)."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE orders SET status = 'CANCELLED' WHERE id = $1 AND status IN ('PENDING', 'OPEN')",
            (order_id,),
        )
        await conn.commit()
        return True

    # ==================== POSITION OPERATIONS ====================

    async def get_positions(
        self, limit: int = 10, offset: int = 0, user_id: Optional[int] = None
    ) -> list[Position]:
        """Get paginated position list."""
        conn = await self.db.get_connection()
        query = "SELECT * FROM positions WHERE size > 0"
        params: list[Any] = []

        if user_id:
            query += " AND user_id = $1"
            params.append(user_id)

        query += " ORDER BY created_at DESC LIMIT $1 OFFSET $2"
        params.extend([limit, offset])

        row = await conn.fetchrow(query, params)
        return [Position(**dict(row)) for row in rows]

    async def count_positions(self, user_id: Optional[int] = None) -> int:
        """Count active positions."""
        conn = await self.db.get_connection()
        query = "SELECT COUNT(*) FROM positions WHERE size > 0"
        params: list[Any] = []

        if user_id:
            query += " AND user_id = $1"
            params.append(user_id)

        rows = await conn.fetch(query, params)
        return row[0] if row else 0

    async def get_position_by_id(self, position_id: int) -> Optional[Position]:
        """Get position by ID."""
        conn = await self.db.get_connection()
        row = await conn.fetchrow(
            "SELECT * FROM positions WHERE id = $1", (position_id,)
        )
        return Position(**dict(row)) if row else None

    # ==================== STOP LOSS OPERATIONS ====================

    async def get_stop_losses(
        self, limit: int = 10, offset: int = 0, active_only: bool = True
    ) -> list[StopLoss]:
        """Get paginated stop loss list."""
        conn = await self.db.get_connection()
        query = "SELECT * FROM stop_loss_orders"
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY created_at DESC LIMIT $1 OFFSET $2"

        rows = await conn.fetch(query, (limit, offset))
        return [StopLoss(**dict(row)) for row in rows]

    async def count_stop_losses(self, active_only: bool = True) -> int:
        """Count stop losses."""
        conn = await self.db.get_connection()
        query = "SELECT COUNT(*) FROM stop_loss_orders"
        if active_only:
            query += " WHERE is_active = TRUE"
        rows = await conn.fetch(query)
        return row[0] if row else 0

    async def deactivate_stop_loss(self, stop_loss_id: int) -> bool:
        """Deactivate a stop loss."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE stop_loss_orders SET is_active = FALSE WHERE id = $1", (stop_loss_id,)
        )
        await conn.commit()
        return True

    # ==================== COPY TRADING OPERATIONS ====================

    async def get_copy_subscriptions(
        self, limit: int = 10, offset: int = 0, active_only: bool = False
    ) -> list[CopyTrader]:
        """Get paginated copy trading subscriptions."""
        conn = await self.db.get_connection()
        query = "SELECT * FROM copy_traders"
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY created_at DESC LIMIT $1 OFFSET $2"

        row = await conn.fetchrow(query, (limit, offset))
        return [CopyTrader(**dict(row)) for row in rows]

    async def count_copy_subscriptions(self, active_only: bool = False) -> int:
        """Count copy trading subscriptions."""
        conn = await self.db.get_connection()
        query = "SELECT COUNT(*) FROM copy_traders"
        if active_only:
            query += " WHERE is_active = TRUE"
        rows = await conn.fetch(query)
        return row[0] if row else 0

    async def deactivate_subscription(self, subscription_id: int) -> bool:
        """Deactivate a copy trading subscription."""
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE copy_traders SET is_active = FALSE WHERE id = $1",
            (subscription_id,),
        )
        await conn.commit()
        return True

    # ==================== DEPOSIT/WITHDRAWAL OPERATIONS ====================

    async def get_deposits(
        self, limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get paginated deposit list."""
        conn = await self.db.get_connection()
        row = await conn.fetchrow(
            "SELECT * FROM deposits ORDER BY detected_at DESC LIMIT $1 OFFSET $2",
            (limit, offset),
        )
        return [dict(row) for row in rows]

    async def count_deposits(self) -> int:
        """Count deposits."""
        conn = await self.db.get_connection()
        row = await conn.fetchrow("SELECT COUNT(*) FROM deposits")
        return row[0] if row else 0

    async def get_withdrawals(
        self, limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get paginated withdrawal list."""
        conn = await self.db.get_connection()
        row = await conn.fetchrow(
            "SELECT * FROM withdrawals ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            (limit, offset),
        )
        return [dict(row) for row in rows]

    async def count_withdrawals(self) -> int:
        """Count withdrawals."""
        conn = await self.db.get_connection()
        row = await conn.fetchrow("SELECT COUNT(*) FROM withdrawals")
        return row[0] if row else 0

    # ==================== FULL USER DETAILS ====================

    async def get_user_full_details(self, user_id: int) -> dict[str, Any]:
        """Get complete user info including wallet, positions, orders."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return {}

        wallet = await self.get_wallet_by_user_id(user_id)
        positions = await self.get_positions(limit=100, user_id=user_id)
        orders = await self.get_orders(limit=10, user_id=user_id)
        order_count = await self.count_orders(user_id=user_id)

        return {
            "user": user,
            "wallet": wallet,
            "positions": positions,
            "recent_orders": orders,
            "total_orders": order_count,
        }

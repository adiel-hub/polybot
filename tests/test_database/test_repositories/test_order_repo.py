"""Tests for OrderRepository."""

import pytest
import pytest_asyncio

from database.connection import Database
from database.repositories.order_repo import OrderRepository
from database.repositories.user_repo import UserRepository


@pytest_asyncio.fixture
async def order_repo(temp_db: Database) -> OrderRepository:
    """Create an OrderRepository with real database."""
    return OrderRepository(temp_db)


@pytest_asyncio.fixture
async def test_user(temp_db: Database, sample_telegram_user: dict) -> int:
    """Create a test user and return their ID."""
    user_repo = UserRepository(temp_db)
    user = await user_repo.create(**sample_telegram_user)
    return user.id


class TestOrderRepository:
    """Test cases for OrderRepository."""

    @pytest.mark.asyncio
    async def test_create_market_order(
        self,
        order_repo: OrderRepository,
        test_user: int,
        sample_order_data: dict,
    ):
        """Test creating a market order."""
        order = await order_repo.create(
            user_id=test_user,
            **sample_order_data,
        )

        assert order is not None
        assert order.id is not None
        assert order.user_id == test_user
        assert order.market_condition_id == sample_order_data["market_condition_id"]
        assert order.token_id == sample_order_data["token_id"]
        assert order.side == "BUY"
        assert order.order_type == "MARKET"
        assert order.size == 10.0
        assert order.outcome == "YES"
        assert order.status == "PENDING"

    @pytest.mark.asyncio
    async def test_create_limit_order(
        self,
        order_repo: OrderRepository,
        test_user: int,
    ):
        """Test creating a limit order with price."""
        order = await order_repo.create(
            user_id=test_user,
            market_condition_id="0xtest123",
            token_id="token_yes_123",
            side="BUY",
            order_type="LIMIT",
            size=50.0,
            outcome="NO",
            price=0.45,
            market_question="Test market question?",
        )

        assert order is not None
        assert order.order_type == "LIMIT"
        assert order.price == 0.45
        assert order.outcome == "NO"
        assert order.market_question == "Test market question?"

    @pytest.mark.asyncio
    async def test_get_by_id(
        self,
        order_repo: OrderRepository,
        test_user: int,
        sample_order_data: dict,
    ):
        """Test retrieving an order by ID."""
        created = await order_repo.create(user_id=test_user, **sample_order_data)
        retrieved = await order_repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.user_id == test_user

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, order_repo: OrderRepository):
        """Test retrieving a non-existent order."""
        result = await order_repo.get_by_id(99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_polymarket_id(
        self,
        order_repo: OrderRepository,
        test_user: int,
        sample_order_data: dict,
    ):
        """Test retrieving an order by Polymarket ID."""
        created = await order_repo.create(user_id=test_user, **sample_order_data)
        await order_repo.update_polymarket_id(created.id, "poly_order_123")

        retrieved = await order_repo.get_by_polymarket_id("poly_order_123")

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.polymarket_order_id == "poly_order_123"

    @pytest.mark.asyncio
    async def test_update_polymarket_id(
        self,
        order_repo: OrderRepository,
        test_user: int,
        sample_order_data: dict,
    ):
        """Test updating the Polymarket order ID."""
        order = await order_repo.create(user_id=test_user, **sample_order_data)
        assert order.polymarket_order_id is None

        await order_repo.update_polymarket_id(order.id, "new_poly_id_456")

        updated = await order_repo.get_by_id(order.id)
        assert updated.polymarket_order_id == "new_poly_id_456"

    @pytest.mark.asyncio
    async def test_update_status(
        self,
        order_repo: OrderRepository,
        test_user: int,
        sample_order_data: dict,
    ):
        """Test updating order status."""
        order = await order_repo.create(user_id=test_user, **sample_order_data)
        assert order.status == "PENDING"

        await order_repo.update_status(order.id, "OPEN")
        updated = await order_repo.get_by_id(order.id)
        assert updated.status == "OPEN"

    @pytest.mark.asyncio
    async def test_update_status_with_filled_size(
        self,
        order_repo: OrderRepository,
        test_user: int,
        sample_order_data: dict,
    ):
        """Test updating order status with filled size."""
        order = await order_repo.create(user_id=test_user, **sample_order_data)

        await order_repo.update_status(order.id, "PARTIALLY_FILLED", filled_size=5.0)

        updated = await order_repo.get_by_id(order.id)
        assert updated.status == "PARTIALLY_FILLED"
        assert updated.filled_size == 5.0

    @pytest.mark.asyncio
    async def test_update_status_with_error(
        self,
        order_repo: OrderRepository,
        test_user: int,
        sample_order_data: dict,
    ):
        """Test updating order status with error message."""
        order = await order_repo.create(user_id=test_user, **sample_order_data)

        await order_repo.update_status(
            order.id,
            "FAILED",
            error_message="Insufficient liquidity",
        )

        updated = await order_repo.get_by_id(order.id)
        assert updated.status == "FAILED"
        assert updated.error_message == "Insufficient liquidity"

    @pytest.mark.asyncio
    async def test_get_open_orders(
        self,
        order_repo: OrderRepository,
        test_user: int,
        sample_order_data: dict,
    ):
        """Test getting open orders for a user."""
        # Create multiple orders with different statuses
        order1 = await order_repo.create(user_id=test_user, **sample_order_data)
        await order_repo.update_status(order1.id, "OPEN")

        order2 = await order_repo.create(user_id=test_user, **sample_order_data)
        await order_repo.update_status(order2.id, "PARTIALLY_FILLED", filled_size=3.0)

        order3 = await order_repo.create(user_id=test_user, **sample_order_data)
        await order_repo.update_status(order3.id, "FILLED", filled_size=10.0)

        order4 = await order_repo.create(user_id=test_user, **sample_order_data)
        await order_repo.update_status(order4.id, "CANCELLED")

        open_orders = await order_repo.get_open_orders(test_user)

        # Should include PENDING, OPEN, PARTIALLY_FILLED but not FILLED or CANCELLED
        assert len(open_orders) == 2
        statuses = [o.status for o in open_orders]
        assert "OPEN" in statuses
        assert "PARTIALLY_FILLED" in statuses
        assert "FILLED" not in statuses
        assert "CANCELLED" not in statuses

    @pytest.mark.asyncio
    async def test_get_user_orders(
        self,
        order_repo: OrderRepository,
        test_user: int,
        sample_order_data: dict,
    ):
        """Test getting user orders with pagination."""
        # Create 5 orders
        for _ in range(5):
            await order_repo.create(user_id=test_user, **sample_order_data)

        # Get first 3
        orders = await order_repo.get_user_orders(test_user, limit=3)
        assert len(orders) == 3

        # Get with offset
        orders_offset = await order_repo.get_user_orders(test_user, limit=3, offset=3)
        assert len(orders_offset) == 2

    @pytest.mark.asyncio
    async def test_get_pending_orders(
        self,
        order_repo: OrderRepository,
        temp_db: Database,
        sample_order_data: dict,
    ):
        """Test getting all pending orders across users."""
        # Create two users
        user_repo = UserRepository(temp_db)
        user1 = await user_repo.create(telegram_id=111, telegram_username="user1")
        user2 = await user_repo.create(telegram_id=222, telegram_username="user2")

        # Create pending orders for both
        order1 = await order_repo.create(user_id=user1.id, **sample_order_data)
        order2 = await order_repo.create(user_id=user2.id, **sample_order_data)
        await order_repo.update_status(order2.id, "OPEN")

        # Create a filled order (should not appear)
        order3 = await order_repo.create(user_id=user1.id, **sample_order_data)
        await order_repo.update_status(order3.id, "FILLED", filled_size=10.0)

        pending = await order_repo.get_pending_orders()

        assert len(pending) == 2
        user_ids = [o.user_id for o in pending]
        assert user1.id in user_ids
        assert user2.id in user_ids

    @pytest.mark.asyncio
    async def test_count_open_orders(
        self,
        order_repo: OrderRepository,
        test_user: int,
        sample_order_data: dict,
    ):
        """Test counting open orders for a user."""
        # Initially no orders
        count = await order_repo.count_open_orders(test_user)
        assert count == 0

        # Add some orders
        order1 = await order_repo.create(user_id=test_user, **sample_order_data)
        order2 = await order_repo.create(user_id=test_user, **sample_order_data)
        await order_repo.update_status(order2.id, "OPEN")

        count = await order_repo.count_open_orders(test_user)
        assert count == 2

        # Fill one order
        await order_repo.update_status(order1.id, "FILLED", filled_size=10.0)

        count = await order_repo.count_open_orders(test_user)
        assert count == 1

    @pytest.mark.asyncio
    async def test_order_fills_and_pnl_properties(
        self,
        order_repo: OrderRepository,
        test_user: int,
    ):
        """Test order model properties for fill percentage and remaining size."""
        order = await order_repo.create(
            user_id=test_user,
            market_condition_id="0xtest",
            token_id="token_123",
            side="BUY",
            order_type="LIMIT",
            size=100.0,
            outcome="YES",
            price=0.50,
        )

        # Update with partial fill
        await order_repo.update_status(order.id, "PARTIALLY_FILLED", filled_size=25.0)
        updated = await order_repo.get_by_id(order.id)

        assert updated.fill_percentage == 25.0
        assert updated.remaining_size == 75.0

    @pytest.mark.asyncio
    async def test_sell_order(
        self,
        order_repo: OrderRepository,
        test_user: int,
    ):
        """Test creating a sell order."""
        order = await order_repo.create(
            user_id=test_user,
            market_condition_id="0xtest",
            token_id="token_123",
            side="SELL",
            order_type="MARKET",
            size=50.0,
            outcome="YES",
        )

        assert order.side == "SELL"
        assert order.order_type == "MARKET"

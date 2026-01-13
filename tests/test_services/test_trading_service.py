"""Tests for TradingService."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from database.connection import Database
from services.trading_service import TradingService
from services.user_service import UserService
from core.wallet.encryption import KeyEncryption


@pytest_asyncio.fixture
async def trading_service(temp_db: Database, key_encryption: KeyEncryption) -> TradingService:
    """Create a TradingService with real database and encryption."""
    return TradingService(temp_db, key_encryption)


@pytest_asyncio.fixture
async def test_user_with_wallet(
    temp_db: Database,
    key_encryption: KeyEncryption,
    sample_telegram_user: dict,
):
    """Create a test user with wallet and some balance."""
    user_service = UserService(temp_db, key_encryption)
    user, wallet = await user_service.register_user(**sample_telegram_user)

    # Add balance to wallet
    from database.repositories import WalletRepository
    wallet_repo = WalletRepository(temp_db)
    await wallet_repo.add_balance(wallet.id, 1000.0)

    return user, wallet


class TestTradingService:
    """Test cases for TradingService."""

    @pytest.mark.asyncio
    async def test_place_market_order_insufficient_balance(
        self,
        trading_service: TradingService,
        test_user_with_wallet,
    ):
        """Test that market order fails with insufficient balance."""
        user, wallet = test_user_with_wallet

        # Try to place order exceeding balance
        result = await trading_service.place_order(
            user_id=user.id,
            market_condition_id="0xtest",
            token_id="token_yes",
            outcome="YES",
            order_type="MARKET",
            amount=5000.0,  # More than balance
        )

        assert result["success"] is False
        assert "insufficient" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_place_market_order_creates_order_record(
        self,
        trading_service: TradingService,
        test_user_with_wallet,
    ):
        """Test that placing a market order creates an order record."""
        user, wallet = test_user_with_wallet

        # Mock the CLOB client to fail (so we don't need actual API)
        with patch.object(trading_service, "_get_clob_client", return_value=None):
            result = await trading_service.place_order(
                user_id=user.id,
                market_condition_id="0xtest123",
                token_id="token_yes_456",
                outcome="YES",
                order_type="MARKET",
                amount=50.0,
                market_question="Test market?",
            )

        # Should fail due to no client, but order record should exist
        assert result["success"] is False

        # Check order was recorded
        orders = await trading_service.get_user_orders(user.id)
        assert len(orders) == 1
        assert orders[0].status == "FAILED"
        assert orders[0].side == "BUY"
        assert orders[0].order_type == "MARKET"
        assert orders[0].size == 50.0

    @pytest.mark.asyncio
    async def test_place_limit_order_requires_price(
        self,
        trading_service: TradingService,
        test_user_with_wallet,
    ):
        """Test that limit orders require a price."""
        user, _ = test_user_with_wallet

        # Mock the CLOB client
        mock_client = AsyncMock()
        with patch.object(trading_service, "_get_clob_client", return_value=mock_client):
            result = await trading_service.place_order(
                user_id=user.id,
                market_condition_id="0xtest",
                token_id="token_yes",
                outcome="YES",
                order_type="LIMIT",
                amount=50.0,
                price=None,  # Missing price
            )

        assert result["success"] is False
        assert "price required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_open_orders(
        self,
        trading_service: TradingService,
        test_user_with_wallet,
    ):
        """Test retrieving open orders."""
        user, _ = test_user_with_wallet

        # Create some orders
        from database.repositories import OrderRepository
        order_repo = OrderRepository(trading_service.db)

        # Create OPEN order
        await order_repo.create(
            user_id=user.id,
            market_condition_id="0xtest1",
            token_id="token_1",
            side="BUY",
            order_type="MARKET",
            size=10.0,
            outcome="YES",
        )

        # Create FILLED order (should not appear in open orders)
        order2 = await order_repo.create(
            user_id=user.id,
            market_condition_id="0xtest2",
            token_id="token_2",
            side="BUY",
            order_type="LIMIT",
            size=20.0,
            outcome="NO",
            price=0.50,
        )
        await order_repo.update_status(order2.id, "FILLED", filled_size=20.0)

        # Get open orders
        open_orders = await trading_service.get_open_orders(user.id)

        assert len(open_orders) == 1
        assert open_orders[0].status in ["PENDING", "OPEN", "PARTIALLY_FILLED"]

    @pytest.mark.asyncio
    async def test_cancel_order(
        self,
        trading_service: TradingService,
        test_user_with_wallet,
    ):
        """Test cancelling an order."""
        user, _ = test_user_with_wallet

        # Create an order
        from database.repositories import OrderRepository
        order_repo = OrderRepository(trading_service.db)

        order = await order_repo.create(
            user_id=user.id,
            market_condition_id="0xtest",
            token_id="token_yes",
            side="BUY",
            order_type="LIMIT",
            size=50.0,
            outcome="YES",
            price=0.55,
        )

        # Cancel it
        success = await trading_service.cancel_order(user.id, order.id)

        # Should succeed even without polymarket_order_id
        assert success is True

        # Check order status
        updated_order = await order_repo.get_by_id(order.id)
        assert updated_order.status == "CANCELLED"

    @pytest.mark.asyncio
    async def test_get_positions(
        self,
        trading_service: TradingService,
        test_user_with_wallet,
    ):
        """Test retrieving user positions."""
        user, _ = test_user_with_wallet

        # Create some positions
        from database.repositories import PositionRepository
        position_repo = PositionRepository(trading_service.db)

        await position_repo.create_or_update(
            user_id=user.id,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=100.0,
            average_entry_price=0.55,
        )

        await position_repo.create_or_update(
            user_id=user.id,
            market_condition_id="market_2",
            token_id="token_2",
            outcome="NO",
            size=50.0,
            average_entry_price=0.45,
        )

        # Get positions
        positions = await trading_service.get_positions(user.id)

        assert len(positions) == 2

    @pytest.mark.asyncio
    async def test_get_portfolio_value(
        self,
        trading_service: TradingService,
        test_user_with_wallet,
    ):
        """Test calculating portfolio value."""
        user, _ = test_user_with_wallet

        # Create positions
        from database.repositories import PositionRepository
        position_repo = PositionRepository(trading_service.db)

        pos1 = await position_repo.create_or_update(
            user_id=user.id,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=100.0,
            average_entry_price=0.50,
        )
        await position_repo.update_current_price(pos1.id, 0.60)

        pos2 = await position_repo.create_or_update(
            user_id=user.id,
            market_condition_id="market_2",
            token_id="token_2",
            outcome="NO",
            size=50.0,
            average_entry_price=0.40,
        )
        await position_repo.update_current_price(pos2.id, 0.35)

        # Get portfolio value
        total_value = await trading_service.get_portfolio_value(user.id)

        # (100 * 0.60) + (50 * 0.35) = 60 + 17.5 = 77.5
        assert abs(total_value - 77.5) < 0.01

    @pytest.mark.asyncio
    async def test_sell_position_insufficient_shares(
        self,
        trading_service: TradingService,
        test_user_with_wallet,
    ):
        """Test that selling more shares than owned fails."""
        user, _ = test_user_with_wallet

        # Create a position with 50 shares
        from database.repositories import PositionRepository
        position_repo = PositionRepository(trading_service.db)

        position = await position_repo.create_or_update(
            user_id=user.id,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=50.0,
            average_entry_price=0.50,
        )

        # Try to sell 100 shares (more than owned)
        result = await trading_service.sell_position(
            user_id=user.id,
            position_id=position.id,
            token_id="token_1",
            size=100.0,
            market_condition_id="market_1",
        )

        assert result["success"] is False
        assert "insufficient" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_sell_position_creates_sell_order(
        self,
        trading_service: TradingService,
        test_user_with_wallet,
    ):
        """Test that selling creates a SELL order."""
        user, _ = test_user_with_wallet

        # Create a position
        from database.repositories import PositionRepository
        position_repo = PositionRepository(trading_service.db)

        position = await position_repo.create_or_update(
            user_id=user.id,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=100.0,
            average_entry_price=0.50,
        )

        # Mock CLOB client to fail
        with patch.object(trading_service, "_get_clob_client", return_value=None):
            result = await trading_service.sell_position(
                user_id=user.id,
                position_id=position.id,
                token_id="token_1",
                size=50.0,
                market_condition_id="market_1",
            )

        # Check sell order was created
        orders = await trading_service.get_user_orders(user.id)
        sell_orders = [o for o in orders if o.side == "SELL"]

        assert len(sell_orders) == 1
        assert sell_orders[0].size == 50.0
        assert sell_orders[0].order_type == "MARKET"

    @pytest.mark.asyncio
    async def test_sell_position_wrong_user(
        self,
        trading_service: TradingService,
        test_user_with_wallet,
        temp_db: Database,
        key_encryption: KeyEncryption,
    ):
        """Test that users cannot sell other users' positions."""
        user1, _ = test_user_with_wallet

        # Create second user
        user_service = UserService(temp_db, key_encryption)
        user2, _ = await user_service.register_user(
            telegram_id=987654,
            telegram_username="user2",
        )

        # Create position for user1
        from database.repositories import PositionRepository
        position_repo = PositionRepository(temp_db)

        position = await position_repo.create_or_update(
            user_id=user1.id,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=100.0,
            average_entry_price=0.50,
        )

        # Try to sell user1's position as user2
        result = await trading_service.sell_position(
            user_id=user2.id,
            position_id=position.id,
            token_id="token_1",
            size=50.0,
            market_condition_id="market_1",
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

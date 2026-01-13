"""Tests for PositionRepository."""

import pytest
import pytest_asyncio

from database.connection import Database
from database.repositories.position_repo import PositionRepository
from database.repositories.user_repo import UserRepository


@pytest_asyncio.fixture
async def position_repo(temp_db: Database) -> PositionRepository:
    """Create a PositionRepository with real database."""
    return PositionRepository(temp_db)


@pytest_asyncio.fixture
async def test_user(temp_db: Database, sample_telegram_user: dict) -> int:
    """Create a test user and return their ID."""
    user_repo = UserRepository(temp_db)
    user = await user_repo.create(**sample_telegram_user)
    return user.id


@pytest_asyncio.fixture
def sample_position_data() -> dict:
    """Sample position data."""
    return {
        "market_condition_id": "0xtest_market_123",
        "token_id": "token_yes_456",
        "outcome": "YES",
        "size": 100.0,
        "average_entry_price": 0.55,
        "market_question": "Will this test pass?",
    }


class TestPositionRepository:
    """Test cases for PositionRepository."""

    @pytest.mark.asyncio
    async def test_create_or_update_new_position(
        self,
        position_repo: PositionRepository,
        test_user: int,
        sample_position_data: dict,
    ):
        """Test creating a new position."""
        position = await position_repo.create_or_update(
            user_id=test_user,
            **sample_position_data,
        )

        assert position is not None
        assert position.id is not None
        assert position.user_id == test_user
        assert position.token_id == sample_position_data["token_id"]
        assert position.outcome == "YES"
        assert position.size == 100.0
        assert position.average_entry_price == 0.55
        assert position.market_question == "Will this test pass?"

    @pytest.mark.asyncio
    async def test_create_or_update_existing_position(
        self,
        position_repo: PositionRepository,
        test_user: int,
        sample_position_data: dict,
    ):
        """Test updating an existing position (averaging entry price)."""
        # Create initial position
        initial = await position_repo.create_or_update(
            user_id=test_user,
            **sample_position_data,
        )

        # Add more to the same position at a different price
        updated = await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id=sample_position_data["market_condition_id"],
            token_id=sample_position_data["token_id"],
            outcome="YES",
            size=50.0,
            average_entry_price=0.65,
            market_question=sample_position_data["market_question"],
        )

        # Should be the same position ID
        assert updated.id == initial.id
        # Size should be combined
        assert updated.size == 150.0
        # Entry price should be weighted average
        # (100 * 0.55 + 50 * 0.65) / 150 = (55 + 32.5) / 150 = 87.5 / 150 = 0.583333...
        assert abs(updated.average_entry_price - 0.5833333) < 0.0001

    @pytest.mark.asyncio
    async def test_get_by_id(
        self,
        position_repo: PositionRepository,
        test_user: int,
        sample_position_data: dict,
    ):
        """Test retrieving a position by ID."""
        created = await position_repo.create_or_update(
            user_id=test_user,
            **sample_position_data,
        )
        retrieved = await position_repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.user_id == test_user

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, position_repo: PositionRepository):
        """Test retrieving a non-existent position."""
        result = await position_repo.get_by_id(99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_token_id(
        self,
        position_repo: PositionRepository,
        test_user: int,
        sample_position_data: dict,
    ):
        """Test retrieving a position by token ID."""
        created = await position_repo.create_or_update(
            user_id=test_user,
            **sample_position_data,
        )

        retrieved = await position_repo.get_by_token_id(
            test_user,
            sample_position_data["token_id"],
        )

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.token_id == sample_position_data["token_id"]

    @pytest.mark.asyncio
    async def test_get_user_positions(
        self,
        position_repo: PositionRepository,
        test_user: int,
    ):
        """Test getting all positions for a user."""
        # Create 3 positions
        await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=50.0,
            average_entry_price=0.50,
        )
        await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id="market_2",
            token_id="token_2",
            outcome="NO",
            size=75.0,
            average_entry_price=0.60,
        )
        await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id="market_3",
            token_id="token_3",
            outcome="YES",
            size=100.0,
            average_entry_price=0.45,
        )

        positions = await position_repo.get_user_positions(test_user)

        assert len(positions) == 3
        token_ids = [p.token_id for p in positions]
        assert "token_1" in token_ids
        assert "token_2" in token_ids
        assert "token_3" in token_ids

    @pytest.mark.asyncio
    async def test_update_current_price(
        self,
        position_repo: PositionRepository,
        test_user: int,
        sample_position_data: dict,
    ):
        """Test updating current price for a position."""
        position = await position_repo.create_or_update(
            user_id=test_user,
            **sample_position_data,
        )

        # Initially no current price
        assert position.current_price is None

        # Update current price
        await position_repo.update_current_price(position.id, 0.65)

        updated = await position_repo.get_by_id(position.id)
        assert updated.current_price == 0.65

    @pytest.mark.asyncio
    async def test_reduce_position(
        self,
        position_repo: PositionRepository,
        test_user: int,
        sample_position_data: dict,
    ):
        """Test reducing a position (selling shares)."""
        position = await position_repo.create_or_update(
            user_id=test_user,
            **sample_position_data,
        )

        assert position.size == 100.0

        # Sell 40 shares
        await position_repo.reduce_position(position.id, 40.0, 0.60)

        updated = await position_repo.get_by_id(position.id)
        assert updated.size == 60.0

    @pytest.mark.asyncio
    async def test_reduce_position_to_zero(
        self,
        position_repo: PositionRepository,
        test_user: int,
        sample_position_data: dict,
    ):
        """Test reducing position to zero deletes it."""
        position = await position_repo.create_or_update(
            user_id=test_user,
            **sample_position_data,
        )

        # Sell all shares
        await position_repo.reduce_position(position.id, 100.0, 0.60)

        # Position should be deleted
        deleted = await position_repo.get_by_id(position.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delete_position(
        self,
        position_repo: PositionRepository,
        test_user: int,
        sample_position_data: dict,
    ):
        """Test deleting a position."""
        position = await position_repo.create_or_update(
            user_id=test_user,
            **sample_position_data,
        )

        success = await position_repo.delete(position.id)
        assert success is True

        deleted = await position_repo.get_by_id(position.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_get_total_value(
        self,
        position_repo: PositionRepository,
        test_user: int,
    ):
        """Test calculating total portfolio value."""
        # Create positions with current prices
        pos1 = await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=100.0,
            average_entry_price=0.50,
        )
        await position_repo.update_current_price(pos1.id, 0.60)

        pos2 = await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id="market_2",
            token_id="token_2",
            outcome="NO",
            size=50.0,
            average_entry_price=0.40,
        )
        await position_repo.update_current_price(pos2.id, 0.45)

        total_value = await position_repo.get_total_value(test_user)

        # (100 * 0.60) + (50 * 0.45) = 60 + 22.5 = 82.5
        assert abs(total_value - 82.5) < 0.01

    @pytest.mark.asyncio
    async def test_get_total_unrealized_pnl(
        self,
        position_repo: PositionRepository,
        test_user: int,
    ):
        """Test calculating total unrealized P&L."""
        # Position 1: Profit
        pos1 = await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=100.0,
            average_entry_price=0.50,
        )
        await position_repo.update_current_price(pos1.id, 0.60)
        # PnL = (0.60 - 0.50) * 100 = +10

        # Position 2: Loss
        pos2 = await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id="market_2",
            token_id="token_2",
            outcome="NO",
            size=50.0,
            average_entry_price=0.60,
        )
        await position_repo.update_current_price(pos2.id, 0.45)
        # PnL = (0.45 - 0.60) * 50 = -7.5

        total_pnl = await position_repo.get_total_unrealized_pnl(test_user)

        # 10 + (-7.5) = 2.5
        assert abs(total_pnl - 2.5) < 0.01

    @pytest.mark.asyncio
    async def test_position_properties(
        self,
        position_repo: PositionRepository,
        test_user: int,
    ):
        """Test position model properties: cost_basis, current_value, pnl_percentage."""
        position = await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=100.0,
            average_entry_price=0.50,
        )
        await position_repo.update_current_price(position.id, 0.60)

        updated = await position_repo.get_by_id(position.id)

        # cost_basis = size * average_entry_price = 100 * 0.50 = 50
        assert abs(updated.cost_basis - 50.0) < 0.01

        # current_value = size * current_price = 100 * 0.60 = 60
        assert abs(updated.current_value - 60.0) < 0.01

        # unrealized_pnl = current_value - cost_basis = 60 - 50 = 10
        assert abs(updated.unrealized_pnl - 10.0) < 0.01

        # pnl_percentage = (current_price - entry_price) / entry_price * 100
        # = (0.60 - 0.50) / 0.50 * 100 = 20%
        assert abs(updated.pnl_percentage - 20.0) < 0.01

    @pytest.mark.asyncio
    async def test_multiple_users_separate_positions(
        self,
        position_repo: PositionRepository,
        temp_db: Database,
    ):
        """Test that positions are correctly separated by user."""
        user_repo = UserRepository(temp_db)
        user1 = await user_repo.create(telegram_id=111, telegram_username="user1")
        user2 = await user_repo.create(telegram_id=222, telegram_username="user2")

        # User 1 has 2 positions
        await position_repo.create_or_update(
            user_id=user1.id,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=50.0,
            average_entry_price=0.50,
        )
        await position_repo.create_or_update(
            user_id=user1.id,
            market_condition_id="market_2",
            token_id="token_2",
            outcome="NO",
            size=75.0,
            average_entry_price=0.60,
        )

        # User 2 has 1 position
        await position_repo.create_or_update(
            user_id=user2.id,
            market_condition_id="market_3",
            token_id="token_3",
            outcome="YES",
            size=100.0,
            average_entry_price=0.45,
        )

        user1_positions = await position_repo.get_user_positions(user1.id)
        user2_positions = await position_repo.get_user_positions(user2.id)

        assert len(user1_positions) == 2
        assert len(user2_positions) == 1

    @pytest.mark.asyncio
    async def test_position_without_current_price(
        self,
        position_repo: PositionRepository,
        test_user: int,
        sample_position_data: dict,
    ):
        """Test position values when current_price is None."""
        position = await position_repo.create_or_update(
            user_id=test_user,
            **sample_position_data,
        )

        # current_value should use average_entry_price when current_price is None
        assert position.current_price is None
        assert abs(position.current_value - 55.0) < 0.01  # 100 * 0.55
        assert position.unrealized_pnl == 0.0
        assert position.pnl_percentage == 0.0

    @pytest.mark.asyncio
    async def test_position_average_price_calculation(
        self,
        position_repo: PositionRepository,
        test_user: int,
    ):
        """Test weighted average entry price calculation."""
        # Buy 100 shares at 0.50
        await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=100.0,
            average_entry_price=0.50,
        )

        # Buy 50 more shares at 0.70
        updated = await position_repo.create_or_update(
            user_id=test_user,
            market_condition_id="market_1",
            token_id="token_1",
            outcome="YES",
            size=50.0,
            average_entry_price=0.70,
        )

        # Weighted average = (100 * 0.50 + 50 * 0.70) / 150
        # = (50 + 35) / 150 = 85 / 150 = 0.566666...
        assert updated.size == 150.0
        assert abs(updated.average_entry_price - 0.5666667) < 0.0001

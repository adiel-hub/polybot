"""Tests for UserRepository.

Tests the UserRepository class which handles CRUD operations
for users in the SQLite database.
"""

import pytest

from database.repositories.user_repo import UserRepository
from database.connection import Database


class TestUserRepository:
    """Test suite for UserRepository."""

    @pytest.mark.asyncio
    async def test_create_user(self, user_repo: UserRepository):
        """Test creating a new user."""
        user = await user_repo.create(
            telegram_id=123456789,
            telegram_username="testuser",
            first_name="Test",
            last_name="User",
        )

        assert user is not None
        assert user.id is not None
        assert user.telegram_id == 123456789
        assert user.telegram_username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.license_accepted is False
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_create_user_minimal_data(self, user_repo: UserRepository):
        """Test creating user with minimal data (only telegram_id)."""
        user = await user_repo.create(telegram_id=987654321)

        assert user is not None
        assert user.telegram_id == 987654321
        assert user.telegram_username is None
        assert user.first_name is None
        assert user.last_name is None

    @pytest.mark.asyncio
    async def test_get_by_id(self, user_repo: UserRepository):
        """Test retrieving user by ID."""
        created = await user_repo.create(telegram_id=111111111)

        retrieved = await user_repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.telegram_id == created.telegram_id

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, user_repo: UserRepository):
        """Test get_by_id returns None for non-existent user."""
        result = await user_repo.get_by_id(99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_telegram_id(self, user_repo: UserRepository):
        """Test retrieving user by Telegram ID."""
        await user_repo.create(telegram_id=222222222, telegram_username="user2")

        retrieved = await user_repo.get_by_telegram_id(222222222)

        assert retrieved is not None
        assert retrieved.telegram_id == 222222222
        assert retrieved.telegram_username == "user2"

    @pytest.mark.asyncio
    async def test_get_by_telegram_id_not_found(self, user_repo: UserRepository):
        """Test get_by_telegram_id returns None for non-existent user."""
        result = await user_repo.get_by_telegram_id(999999999)

        assert result is None

    @pytest.mark.asyncio
    async def test_accept_license(self, user_repo: UserRepository):
        """Test accepting license for user."""
        user = await user_repo.create(telegram_id=333333333)
        assert user.license_accepted is False

        await user_repo.accept_license(user.id)

        updated = await user_repo.get_by_id(user.id)
        assert updated.license_accepted is True
        assert updated.license_accepted_at is not None

    @pytest.mark.asyncio
    async def test_update_settings(self, user_repo: UserRepository):
        """Test updating user settings."""
        user = await user_repo.create(telegram_id=444444444)
        assert user.settings == {}

        new_settings = {
            "trading_mode": "fast",
            "fast_mode_threshold": 50.0,
            "auto_claim": True,
        }
        await user_repo.update_settings(user.id, new_settings)

        updated = await user_repo.get_by_id(user.id)
        assert updated.settings == new_settings

    @pytest.mark.asyncio
    async def test_deactivate_user(self, user_repo: UserRepository):
        """Test deactivating a user."""
        user = await user_repo.create(telegram_id=555555555)
        assert user.is_active is True

        await user_repo.deactivate(user.id)

        updated = await user_repo.get_by_id(user.id)
        assert updated.is_active is False

    @pytest.mark.asyncio
    async def test_get_all_active(self, user_repo: UserRepository):
        """Test getting all active users."""
        # Create some users
        user1 = await user_repo.create(telegram_id=666666661)
        user2 = await user_repo.create(telegram_id=666666662)
        user3 = await user_repo.create(telegram_id=666666663)

        # Deactivate one
        await user_repo.deactivate(user2.id)

        active_users = await user_repo.get_all_active()

        active_ids = [u.telegram_id for u in active_users]
        assert 666666661 in active_ids
        assert 666666662 not in active_ids  # Deactivated
        assert 666666663 in active_ids

    @pytest.mark.asyncio
    async def test_count_active(self, user_repo: UserRepository):
        """Test counting active users."""
        # Create some users
        await user_repo.create(telegram_id=777777771)
        user2 = await user_repo.create(telegram_id=777777772)
        await user_repo.create(telegram_id=777777773)

        # Deactivate one
        await user_repo.deactivate(user2.id)

        count = await user_repo.count_active()

        assert count == 2

    @pytest.mark.asyncio
    async def test_create_duplicate_telegram_id_fails(
        self, user_repo: UserRepository
    ):
        """Test that creating user with duplicate telegram_id fails."""
        await user_repo.create(telegram_id=888888888)

        with pytest.raises(Exception):  # IntegrityError
            await user_repo.create(telegram_id=888888888)

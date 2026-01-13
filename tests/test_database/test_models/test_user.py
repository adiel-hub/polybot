"""Tests for User model.

Tests the User dataclass and related helper functions
for settings management.
"""

import json
from datetime import datetime

import pytest

from database.models.user import (
    User,
    DEFAULT_SETTINGS,
    get_settings_with_defaults,
)


class TestDefaultSettings:
    """Tests for DEFAULT_SETTINGS constant."""

    def test_default_settings_contains_required_keys(self):
        """Test that DEFAULT_SETTINGS has all required keys."""
        required_keys = [
            "trading_mode",
            "fast_mode_threshold",
            "quickbuy_presets",
            "auto_claim",
            "auto_apply_preset",
            "two_factor_enabled",
        ]

        for key in required_keys:
            assert key in DEFAULT_SETTINGS

    def test_default_trading_mode_is_standard(self):
        """Test that default trading mode is 'standard'."""
        assert DEFAULT_SETTINGS["trading_mode"] == "standard"

    def test_default_fast_mode_threshold_is_100(self):
        """Test that default fast mode threshold is 100.0."""
        assert DEFAULT_SETTINGS["fast_mode_threshold"] == 100.0

    def test_default_quickbuy_presets(self):
        """Test that default quickbuy presets are [10, 25, 50]."""
        assert DEFAULT_SETTINGS["quickbuy_presets"] == [10, 25, 50]

    def test_default_boolean_settings_are_false(self):
        """Test that boolean settings default to False."""
        assert DEFAULT_SETTINGS["auto_claim"] is False
        assert DEFAULT_SETTINGS["auto_apply_preset"] is False
        assert DEFAULT_SETTINGS["two_factor_enabled"] is False


class TestGetSettingsWithDefaults:
    """Tests for get_settings_with_defaults function."""

    def test_empty_settings_returns_defaults(self):
        """Test that empty settings dict returns all defaults."""
        result = get_settings_with_defaults({})

        assert result == DEFAULT_SETTINGS

    def test_partial_settings_merged_with_defaults(self):
        """Test that partial settings are merged with defaults."""
        partial = {"trading_mode": "fast", "auto_claim": True}

        result = get_settings_with_defaults(partial)

        assert result["trading_mode"] == "fast"
        assert result["auto_claim"] is True
        # Other values should be defaults
        assert result["fast_mode_threshold"] == 100.0
        assert result["quickbuy_presets"] == [10, 25, 50]
        assert result["auto_apply_preset"] is False
        assert result["two_factor_enabled"] is False

    def test_user_settings_override_defaults(self):
        """Test that user settings override defaults."""
        user_settings = {
            "trading_mode": "ludicrous",
            "fast_mode_threshold": 50.0,
            "quickbuy_presets": [5, 10, 20],
        }

        result = get_settings_with_defaults(user_settings)

        assert result["trading_mode"] == "ludicrous"
        assert result["fast_mode_threshold"] == 50.0
        assert result["quickbuy_presets"] == [5, 10, 20]

    def test_does_not_mutate_original_settings(self):
        """Test that function doesn't mutate the input dict."""
        original = {"trading_mode": "fast"}
        original_copy = original.copy()

        get_settings_with_defaults(original)

        assert original == original_copy

    def test_does_not_mutate_defaults(self):
        """Test that function doesn't mutate DEFAULT_SETTINGS."""
        defaults_copy = DEFAULT_SETTINGS.copy()

        get_settings_with_defaults({"trading_mode": "ludicrous"})

        assert DEFAULT_SETTINGS == defaults_copy


class TestUserModel:
    """Tests for User dataclass."""

    def _create_mock_row(self, **kwargs):
        """Create a dictionary that mimics a database row."""
        defaults = {
            "id": 1,
            "telegram_id": 123456789,
            "telegram_username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "license_accepted": 1,
            "license_accepted_at": datetime.utcnow(),
            "is_active": 1,
            "settings": "{}",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        return defaults

    def test_from_row_creates_user(self):
        """Test that from_row creates User from database row."""
        row = self._create_mock_row()

        user = User.from_row(row)

        assert user.id == 1
        assert user.telegram_id == 123456789
        assert user.telegram_username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.license_accepted is True
        assert user.is_active is True

    def test_from_row_parses_settings_json(self):
        """Test that from_row parses settings from JSON."""
        settings = {"trading_mode": "fast", "auto_claim": True}
        row = self._create_mock_row(settings=json.dumps(settings))

        user = User.from_row(row)

        assert user.settings == settings

    def test_from_row_handles_empty_settings(self):
        """Test that from_row handles empty settings string."""
        row = self._create_mock_row(settings=None)

        user = User.from_row(row)

        assert user.settings == {}

    def test_from_row_handles_license_not_accepted(self):
        """Test that from_row handles license_accepted=0."""
        row = self._create_mock_row(
            license_accepted=0, license_accepted_at=None
        )

        user = User.from_row(row)

        assert user.license_accepted is False
        assert user.license_accepted_at is None

    def test_display_name_with_full_name(self):
        """Test display_name returns full name when available."""
        row = self._create_mock_row(first_name="John", last_name="Doe")
        user = User.from_row(row)

        assert user.display_name == "John Doe"

    def test_display_name_with_first_name_only(self):
        """Test display_name returns first name when last is missing."""
        row = self._create_mock_row(first_name="John", last_name=None)
        user = User.from_row(row)

        assert user.display_name == "John"

    def test_display_name_with_username_only(self):
        """Test display_name returns @username when name is missing."""
        row = self._create_mock_row(
            first_name=None, last_name=None, telegram_username="johndoe"
        )
        user = User.from_row(row)

        assert user.display_name == "@johndoe"

    def test_display_name_fallback_to_telegram_id(self):
        """Test display_name falls back to User ID when nothing else available."""
        row = self._create_mock_row(
            first_name=None, last_name=None, telegram_username=None
        )
        user = User.from_row(row)

        assert user.display_name == "User 123456789"

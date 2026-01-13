"""User model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any
import json


# Default settings for new users
DEFAULT_SETTINGS = {
    "trading_mode": "standard",        # standard | fast | ludicrous
    "fast_mode_threshold": 100.0,      # USD threshold for fast mode
    "quickbuy_presets": [10, 25, 50],  # Customizable preset amounts
    "auto_claim": False,               # Auto-claim resolved positions
    "auto_apply_preset": False,        # Auto-apply default preset
    "two_factor_enabled": False,       # 2FA for sensitive actions
}


def get_settings_with_defaults(settings: dict) -> dict:
    """Merge user settings with defaults."""
    result = DEFAULT_SETTINGS.copy()
    result.update(settings)
    return result


@dataclass
class User:
    """User data model."""

    id: int
    telegram_id: int
    telegram_username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    license_accepted: bool
    license_accepted_at: Optional[datetime]
    is_active: bool
    settings: dict
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row) -> "User":
        """Create User from database row."""
        settings = json.loads(row["settings"]) if row["settings"] else {}
        return cls(
            id=row["id"],
            telegram_id=row["telegram_id"],
            telegram_username=row["telegram_username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            license_accepted=bool(row["license_accepted"]),
            license_accepted_at=row["license_accepted_at"],
            is_active=bool(row["is_active"]),
            settings=settings,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @property
    def display_name(self) -> str:
        """Get user display name."""
        if self.first_name:
            name = self.first_name
            if self.last_name:
                name += f" {self.last_name}"
            return name
        if self.telegram_username:
            return f"@{self.telegram_username}"
        return f"User {self.telegram_id}"

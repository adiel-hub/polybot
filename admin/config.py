"""Admin panel configuration."""

import os

# Admin Telegram user IDs (comma-separated in env)
_admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "")
ADMIN_IDS: list[int] = [
    int(id.strip()) for id in _admin_ids_str.split(",") if id.strip()
]

# Pagination settings
ITEMS_PER_PAGE = 10

# Broadcast settings
BROADCAST_BATCH_SIZE = 50
BROADCAST_DELAY = 0.1  # seconds between messages


def is_admin(telegram_id: int) -> bool:
    """Check if a user is an admin."""
    return telegram_id in ADMIN_IDS

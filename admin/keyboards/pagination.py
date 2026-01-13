"""Pagination keyboard utilities."""

from typing import Callable, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_pagination_keyboard(
    items: list[Any],
    page: int,
    total_pages: int,
    callback_prefix: str,
    item_formatter: Callable[[Any], tuple[str, str]],
    back_callback: str = "admin_menu",
    extra_buttons: list[list[InlineKeyboardButton]] = None,
) -> InlineKeyboardMarkup:
    """
    Build a paginated keyboard with items.

    Args:
        items: List of items to display
        page: Current page (0-indexed)
        total_pages: Total number of pages
        callback_prefix: Prefix for item callbacks (e.g., "admin_user")
        item_formatter: Function that takes an item and returns (label, callback_data)
        back_callback: Callback data for back button
        extra_buttons: Additional button rows to add before navigation

    Returns:
        InlineKeyboardMarkup with items and pagination
    """
    keyboard = []

    # Item buttons
    for item in items:
        label, callback = item_formatter(item)
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    # Extra buttons
    if extra_buttons:
        keyboard.extend(extra_buttons)

    # Pagination buttons
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"{callback_prefix}_page_{page - 1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"{callback_prefix}_page_{page + 1}")
            )
        keyboard.append(nav_buttons)

    # Back button
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=back_callback)])

    return InlineKeyboardMarkup(keyboard)


def get_page_from_callback(callback_data: str, prefix: str) -> int:
    """Extract page number from callback data."""
    if callback_data.startswith(f"{prefix}_page_"):
        try:
            return int(callback_data.split("_")[-1])
        except (ValueError, IndexError):
            pass
    return 0

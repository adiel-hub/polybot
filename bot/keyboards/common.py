"""Common keyboard components."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_back_keyboard(back_callback: str = "menu_main") -> InlineKeyboardMarkup:
    """Get keyboard with back button."""
    keyboard = [
        [
            InlineKeyboardButton("🔙 Back", callback_data=back_callback),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard(cancel_callback: str = "menu_main") -> InlineKeyboardMarkup:
    """Get keyboard with cancel button."""
    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data=cancel_callback)]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_keyboard(
    confirm_callback: str,
    cancel_callback: str = "menu_main",
) -> InlineKeyboardMarkup:
    """Get keyboard with confirm and cancel buttons."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data=confirm_callback),
            InlineKeyboardButton("❌ Cancel", callback_data=cancel_callback),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
    back_callback: str = "menu_browse",
) -> InlineKeyboardMarkup:
    """Get pagination keyboard."""
    keyboard = []

    # Navigation row
    nav_row = []
    if current_page > 1:
        nav_row.append(
            InlineKeyboardButton("◀️ Prev", callback_data=f"{callback_prefix}_page_{current_page - 1}")
        )

    nav_row.append(
        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="noop")
    )

    if current_page < total_pages:
        nav_row.append(
            InlineKeyboardButton("Next ▶️", callback_data=f"{callback_prefix}_page_{current_page + 1}")
        )

    keyboard.append(nav_row)

    # Back row
    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data=back_callback),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    return InlineKeyboardMarkup(keyboard)

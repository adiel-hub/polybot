"""Admin menu keyboards."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_admin_main_menu() -> InlineKeyboardMarkup:
    """Build admin main menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")],
        [
            InlineKeyboardButton("👥 Users", callback_data="admin_users"),
            InlineKeyboardButton("📋 Orders", callback_data="admin_orders"),
        ],
        [
            InlineKeyboardButton("🎯 Positions", callback_data="admin_positions"),
            InlineKeyboardButton("🛑 Stop Loss", callback_data="admin_stoploss"),
        ],
        [
            InlineKeyboardButton("👥 Copy Trading", callback_data="admin_copy"),
            InlineKeyboardButton("💰 Wallets", callback_data="admin_wallets"),
        ],
        [
            InlineKeyboardButton("⚙️ System", callback_data="admin_system"),
            InlineKeyboardButton("🔧 Settings", callback_data="admin_settings"),
        ],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard(callback_data: str = "admin_menu") -> InlineKeyboardMarkup:
    """Build simple back button keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data=callback_data)]
    ])


def get_confirmation_keyboard(
    confirm_callback: str,
    cancel_callback: str,
    confirm_text: str = "✅ Confirm",
    cancel_text: str = "❌ Cancel",
) -> InlineKeyboardMarkup:
    """Build confirmation keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(confirm_text, callback_data=confirm_callback),
            InlineKeyboardButton(cancel_text, callback_data=cancel_callback),
        ]
    ])


def get_filter_keyboard(
    filters: list[tuple[str, str]],
    current_filter: str,
    back_callback: str = "admin_menu",
) -> InlineKeyboardMarkup:
    """Build filter selection keyboard."""
    keyboard = []

    row = []
    for label, callback in filters:
        prefix = "✅ " if callback.endswith(current_filter) else ""
        row.append(InlineKeyboardButton(f"{prefix}{label}", callback_data=callback))
        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=back_callback)])

    return keyboard

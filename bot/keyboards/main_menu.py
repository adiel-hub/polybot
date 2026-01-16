"""Main menu keyboard."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main menu inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Portfolio", callback_data="menu_portfolio"),
            InlineKeyboardButton("📋 Orders", callback_data="menu_orders"),
            InlineKeyboardButton("💰 Wallet", callback_data="menu_wallet"),
        ],
        [
            InlineKeyboardButton("💹 Browse Markets", callback_data="menu_browse"),
            InlineKeyboardButton("👥 Copy Trading", callback_data="menu_copy"),
        ],
        [
            InlineKeyboardButton("🛡️ Stop Loss", callback_data="menu_stoploss"),
            InlineKeyboardButton("🔔 Alerts", callback_data="menu_alerts"),
        ],
        [
            InlineKeyboardButton("🎁 Earn Rewards", callback_data="menu_rewards"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
            InlineKeyboardButton("🔄 Refresh", callback_data="menu_refresh"),
            InlineKeyboardButton("💬 Support", callback_data="menu_support"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_wallet_keyboard() -> InlineKeyboardMarkup:
    """Get wallet menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("📱 Generate QR Code", callback_data="wallet_qr")],
        [InlineKeyboardButton("💸 Withdraw", callback_data="wallet_withdraw")],
        [
            InlineKeyboardButton("🔙 Back", callback_data="menu_main"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_browse_keyboard() -> InlineKeyboardMarkup:
    """Get market browsing keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Volume", callback_data="browse_volume"),
            InlineKeyboardButton("🏷️ Category", callback_data="browse_category"),
        ],
        [
            InlineKeyboardButton("🔥 Trending", callback_data="browse_trending"),
            InlineKeyboardButton("✨ New", callback_data="browse_new"),
        ],
        [InlineKeyboardButton("⏱️ 15m Up or Down", callback_data="browse_15m")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

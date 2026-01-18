"""Admin panel entry point and main menu."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.utils.decorators import admin_only
from admin.services import StatsService

logger = logging.getLogger(__name__)


def get_admin_main_menu_keyboard() -> InlineKeyboardMarkup:
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
        [
            InlineKeyboardButton("🏗️ Builder", callback_data="admin_builder"),
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ]
    return InlineKeyboardMarkup(keyboard)


@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /admin command - entry point to admin panel."""
    db = context.bot_data["db"]
    stats_service = StatsService(db)

    # Get quick stats for menu
    stats = await stats_service.get_quick_stats()

    text = (
        "🔐 *Admin Panel*\n\n"
        f"👥 Users: {stats['total_users']} ({stats['active_users']} active)\n"
        f"💰 Total Balance: ${stats['total_balance']:.2f}\n"
        f"📋 Open Orders: {stats['open_orders']}\n"
        f"🎯 Active Positions: {stats['active_positions']}\n\n"
        "Select an option below:"
    )

    keyboard = get_admin_main_menu_keyboard()

    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )

    return AdminState.ADMIN_MENU


@admin_only
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display admin main menu."""
    query = update.callback_query
    if query:
        await query.answer()

    return await admin_command(update, context)


async def close_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Close the admin panel."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Admin panel closed.")
    return -1  # End conversation

"""Admin dashboard handler."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.utils.decorators import admin_only
from admin.utils.formatters import format_number, format_pnl_emoji
from admin.services import StatsService

logger = logging.getLogger(__name__)


def format_dashboard_text(stats: dict) -> str:
    """Format dashboard statistics for display."""
    users = stats["users"]
    financial = stats["financial"]
    orders = stats["orders"]
    positions = stats["positions"]
    stop_losses = stats["stop_losses"]
    copy_trading = stats["copy_trading"]

    return f"""📊 *Admin Dashboard*

👥 *Users*
├ Total: {users['total']}
├ Active: {users['active']}
└ Suspended: {users['suspended']}

💰 *Financial*
├ Total Balance: {format_number(financial['total_balance'])}
├ Total Deposits: {format_number(financial['total_deposits'])}
└ Total Withdrawals: {format_number(financial['total_withdrawals'])}

📋 *Orders*
├ Total: {orders['total']}
├ Open: {orders['open']}
├ Filled: {orders['filled']}
└ Failed: {orders['failed']}

🎯 *Positions*
├ Active: {positions['active']}
├ Total Value: {format_number(positions['total_value'])}
└ Unrealized P&L: {format_pnl_emoji(positions['unrealized_pnl'])}

🛑 *Stop Losses*
└ Active: {stop_losses['active']}

👥 *Copy Trading*
├ Active Subscriptions: {copy_trading['active_subscriptions']}
└ Unique Traders: {copy_trading['unique_traders']}"""


def get_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Build dashboard keyboard."""
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_dashboard_refresh")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="admin_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


@admin_only
async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display admin dashboard with comprehensive stats."""
    query = update.callback_query
    if query:
        await query.answer()

    db = context.bot_data["db"]
    stats_service = StatsService(db)

    stats = await stats_service.get_dashboard_stats()
    text = format_dashboard_text(stats)
    keyboard = get_dashboard_keyboard()

    if query:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

    return AdminState.DASHBOARD


@admin_only
async def refresh_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Refresh dashboard stats."""
    query = update.callback_query
    await query.answer("Refreshing...")
    return await show_dashboard(update, context)

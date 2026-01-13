"""Admin system monitoring handler."""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.utils.decorators import admin_only
from admin.services import StatsService

logger = logging.getLogger(__name__)


@admin_only
async def show_system_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display system monitoring dashboard."""
    query = update.callback_query
    if query:
        await query.answer()

    db = context.bot_data["db"]

    # Get WebSocket status if available
    ws_service = context.bot_data.get("ws_service")
    ws_status = "Unknown"
    if ws_service:
        # Check if WebSocket manager has active connections
        try:
            ws_status = "🟢 Connected" if ws_service.is_connected() else "🔴 Disconnected"
        except AttributeError:
            ws_status = "⚪ Not Available"

    # Get database stats
    stats_service = StatsService(db)
    stats = await stats_service.get_quick_stats()

    # Check database connectivity
    db_status = "🟢 Connected"
    try:
        async with db.connection() as conn:
            await conn.execute("SELECT 1")
    except Exception as e:
        db_status = f"🔴 Error: {str(e)[:30]}"

    text = f"""⚙️ *System Monitor*

📅 *Server Time*
└ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

🔌 *WebSocket Status*
└ {ws_status}

💾 *Database Status*
└ {db_status}

📊 *Quick Stats*
├ Users: {stats['total_users']}
├ Active Users: {stats['active_users']}
├ Total Balance: ${stats['total_balance']:.2f}
├ Open Orders: {stats['open_orders']}
└ Active Positions: {stats['active_positions']}

🔗 *External Services*
├ Polymarket CLOB: ⚪ Check manually
├ Gamma API: ⚪ Check manually
└ Polygon RPC: ⚪ Check manually"""

    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_system_refresh")],
        [InlineKeyboardButton("🔌 Check WebSocket", callback_data="admin_check_ws")],
        [InlineKeyboardButton("🌐 Check APIs", callback_data="admin_check_apis")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_menu")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    return AdminState.SYSTEM_MONITOR


@admin_only
async def check_component_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Check status of a specific component."""
    query = update.callback_query
    await query.answer("Checking...")

    if query.data == "admin_system_refresh":
        return await show_system_monitor(update, context)

    elif query.data == "admin_check_ws":
        ws_service = context.bot_data.get("ws_service")
        if ws_service:
            try:
                is_connected = ws_service.is_connected()
                status = "🟢 Connected" if is_connected else "🔴 Disconnected"
            except AttributeError:
                status = "⚪ Method not available"
        else:
            status = "⚪ WebSocket service not initialized"

        await query.answer(f"WebSocket: {status}", show_alert=True)

    elif query.data == "admin_check_apis":
        # Basic API check would go here
        await query.answer(
            "API checks require manual verification.\n"
            "Check logs for recent API errors.",
            show_alert=True,
        )

    return AdminState.SYSTEM_MONITOR

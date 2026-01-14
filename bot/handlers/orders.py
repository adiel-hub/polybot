"""Orders handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.keyboards.common import get_back_keyboard

logger = logging.getLogger(__name__)


async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show user's orders."""
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]
    trading_service = context.bot_data["trading_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        text = "❌ User not found. Please /start to register."
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationState.MAIN_MENU

    # Get orders
    all_orders = await trading_service.get_user_orders(db_user.id, limit=20)

    # Filter out failed orders
    orders = [o for o in all_orders if o.status.value != 'FAILED']
    open_orders = await trading_service.get_open_orders(db_user.id)

    if not orders:
        text = (
            "📋 *Orders*\n\n"
            "📭 You don't have any orders yet.\n\n"
            "💹 Browse markets to start trading!"
        )

        keyboard = [
            [InlineKeyboardButton("💹 Browse Markets", callback_data="menu_browse")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]

        if query:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        return ConversationState.ORDERS_LIST

    # Build orders text with summary
    message_lines = [
        "📋 *Your Orders*",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "📊 *Summary*",
        "",
        f"✅ Filled: `{sum(1 for o in orders if o.status.value == 'FILLED')}`",
        f"📖 Open: `{len(open_orders)}`",
        f"🚫 Cancelled: `{sum(1 for o in orders if o.status.value == 'CANCELLED')}`",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🗂️ *Recent Orders*",
        "",
        "_Click an order to view details_",
        "",
    ]

    text = "\n".join(message_lines)

    keyboard = []

    # Create buttons for each order
    for i, order in enumerate(orders[:10], 1):
        # Status emoji
        status_emoji = {
            "PENDING": "⏳",
            "OPEN": "📖",
            "PARTIALLY_FILLED": "📊",
            "FILLED": "✅",
            "CANCELLED": "🚫",
            "FAILED": "❌",
        }.get(order.status.value, "❓")

        # Create button label
        question = order.market_question or "Unknown Market"
        short_question = question[:25] + "..." if len(question) > 25 else question

        button_label = f"{status_emoji} {short_question}"

        # Add button for order details
        keyboard.append([
            InlineKeyboardButton(
                button_label,
                callback_data=f"order_view_{order.id}",
            )
        ])

    # Navigation buttons
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="menu_orders"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    if query:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    return ConversationState.ORDERS_LIST


async def show_order_details(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show detailed view of a specific order."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    order_id = int(callback_data.replace("order_view_", ""))

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Get order details
    from database.repositories.order_repo import OrderRepository
    order_repo = OrderRepository(context.bot_data["db"])
    order = await order_repo.get_by_id(order_id)

    if not order or order.user_id != db_user.id:
        await query.edit_message_text("❌ Order not found.")
        return await show_orders(update, context)

    # Build detailed order view
    message_lines = [
        "📋 *Order Details*",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🎯 *Market*",
        "",
    ]

    market_question = order.market_question or "Unknown Market"
    # Show full market question without truncation
    message_lines.append(f"_{market_question}_")
    message_lines.append("")

    # Status
    status_emoji = {
        "PENDING": "⏳",
        "OPEN": "📖",
        "PARTIALLY_FILLED": "📊",
        "FILLED": "✅",
        "CANCELLED": "🚫",
        "FAILED": "❌",
    }.get(order.status.value, "❓")

    message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    message_lines.append("📊 *Order Info*")
    message_lines.append("")
    message_lines.append(f"🔄 Type: *{order.order_type.value}*")
    message_lines.append(f"📈 Side: *{order.side.value}*")
    message_lines.append(f"🎯 Outcome: *{order.outcome.value if order.outcome else 'N/A'}*")
    message_lines.append(f"📦 Size: `{order.size:.4f}`")

    if order.price:
        message_lines.append(f"💰 Price: `${order.price:.4f}` ({order.price * 100:.1f}c)")

    message_lines.append("")
    message_lines.append(f"{status_emoji} Status: *{order.status.value}*")

    # Transaction info
    if order.polymarket_order_id:
        message_lines.append("")
        message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        message_lines.append("🔗 *Transaction*")
        message_lines.append("")
        short_id = order.polymarket_order_id[:16] + "..." if len(order.polymarket_order_id) > 16 else order.polymarket_order_id
        message_lines.append(f"📝 Order ID: `{short_id}`")

    # Timestamps
    message_lines.append("")
    message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    message_lines.append("🕒 *Timestamps*")
    message_lines.append("")

    from datetime import datetime
    created_time = datetime.fromisoformat(order.created_at).strftime("%Y-%m-%d %H:%M:%S")
    message_lines.append(f"📅 Created: {created_time}")

    if order.updated_at:
        updated_time = datetime.fromisoformat(order.updated_at).strftime("%Y-%m-%d %H:%M:%S")
        message_lines.append(f"🔄 Updated: {updated_time}")

    # Error message if failed
    if order.status.value == "FAILED" and order.error_message:
        message_lines.append("")
        message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        message_lines.append("⚠️ *Error*")
        message_lines.append("")
        error_msg = order.error_message[:100] + "..." if len(order.error_message) > 100 else order.error_message
        message_lines.append(f"`{error_msg}`")

    text = "\n".join(message_lines)

    # Action buttons
    keyboard = []

    # Add cancel button for open orders
    if order.is_open:
        keyboard.append([
            InlineKeyboardButton("🚫 Cancel Order", callback_data=f"cancel_order_{order.id}")
        ])

    # Navigation
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Orders", callback_data="menu_orders"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.ORDERS_LIST


async def handle_cancel_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle order cancellation."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    order_id = int(callback_data.replace("cancel_order_", ""))

    user = update.effective_user
    user_service = context.bot_data["user_service"]
    trading_service = context.bot_data["trading_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    await query.edit_message_text("⏳ Cancelling order...")

    success = await trading_service.cancel_order(db_user.id, order_id)

    if success:
        await query.edit_message_text(
            "✅ Order cancelled successfully!",
        )
    else:
        await query.edit_message_text(
            "❌ Failed to cancel order. It may have already been filled.",
        )

    return await show_orders(update, context)

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
    orders = await trading_service.get_user_orders(db_user.id, limit=20)
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

    # Build orders text
    text = f"📋 *Orders*\n\n📊 Open Orders: `{len(open_orders)}`\n\n"

    keyboard = []

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

        question = order.market_question or "Unknown Market"

        text += (
            f"{i}. {status_emoji} {question[:35]}{'...' if len(question) > 35 else ''}\n"
            f"   {order.side.value} {order.outcome.value if order.outcome else ''} "
            f"| {order.order_type.value}\n"
            f"   Size: {order.size:.2f} | "
            f"Price: {order.price * 100:.0f}c" if order.price else f"   Size: {order.size:.2f}"
        )
        text += f"\n   Status: {order.status.value}\n\n"

        # Add cancel button for open orders
        if order.is_open:
            keyboard.append([
                InlineKeyboardButton(
                    f"🚫 {i}. Cancel",
                    callback_data=f"cancel_order_{order.id}",
                )
            ])

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

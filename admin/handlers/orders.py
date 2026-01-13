"""Admin order management handler."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.config import ITEMS_PER_PAGE
from admin.utils.decorators import admin_only
from admin.utils.formatters import format_order_summary, format_datetime
from admin.services import AdminService

logger = logging.getLogger(__name__)

# Order status filters
ORDER_FILTERS = [
    ("All", "all"),
    ("Open", "OPEN"),
    ("Pending", "PENDING"),
    ("Filled", "FILLED"),
    ("Cancelled", "CANCELLED"),
    ("Failed", "FAILED"),
]


@admin_only
async def show_order_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display paginated order list with filters."""
    query = update.callback_query
    if query:
        await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    # Get page and filter from callback data
    page = 0
    status_filter = context.user_data.get("admin_order_filter", None)

    if query:
        if query.data.startswith("admin_orders_page_"):
            page = int(query.data.split("_")[-1])
        elif query.data.startswith("admin_orders_filter_"):
            filter_value = query.data.replace("admin_orders_filter_", "")
            status_filter = None if filter_value == "all" else filter_value
            context.user_data["admin_order_filter"] = status_filter
            page = 0

    offset = page * ITEMS_PER_PAGE
    orders = await admin_service.get_orders(
        limit=ITEMS_PER_PAGE, offset=offset, status=status_filter
    )
    total = await admin_service.count_orders(status=status_filter)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    # Header with filter info
    filter_label = status_filter or "All"
    text = f"📋 *Order Management*\n\nFilter: {filter_label} | Total: {total} | Page {page + 1}/{total_pages}"

    keyboard = []

    # Filter buttons
    filter_row = []
    for label, value in ORDER_FILTERS[:3]:
        current = "all" if status_filter is None else status_filter
        prefix = "✅" if value == current else ""
        filter_row.append(
            InlineKeyboardButton(
                f"{prefix}{label}", callback_data=f"admin_orders_filter_{value}"
            )
        )
    keyboard.append(filter_row)

    filter_row2 = []
    for label, value in ORDER_FILTERS[3:]:
        current = "all" if status_filter is None else status_filter
        prefix = "✅" if value == current else ""
        filter_row2.append(
            InlineKeyboardButton(
                f"{prefix}{label}", callback_data=f"admin_orders_filter_{value}"
            )
        )
    keyboard.append(filter_row2)

    # Order list
    if orders:
        for order in orders:
            status_emoji = {
                "PENDING": "⏳",
                "OPEN": "📋",
                "PARTIALLY_FILLED": "📊",
                "FILLED": "✅",
                "CANCELLED": "❌",
                "FAILED": "🚫",
            }
            emoji = status_emoji.get(order.status.name, "❓")
            side = "BUY" if order.side.name == "BUY" else "SELL"
            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} #{order.id} {side} {order.outcome.name} ${order.size:.2f}",
                    callback_data=f"admin_order_{order.id}",
                )
            ])
    else:
        text += "\n\nNo orders found."

    # Pagination
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"admin_orders_page_{page - 1}")
            )
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"admin_orders_page_{page + 1}")
            )
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    return AdminState.ORDER_LIST


@admin_only
async def show_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show detailed order information."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    order_id = int(query.data.split("_")[-1])
    order = await admin_service.get_order_by_id(order_id)

    if not order:
        await query.edit_message_text(
            "Order not found.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_orders")]
            ]),
        )
        return AdminState.ORDER_LIST

    text = format_order_summary(order)

    keyboard = []

    # Cancel button for open orders
    if order.status.name in ["PENDING", "OPEN"]:
        keyboard.append([
            InlineKeyboardButton("❌ Cancel Order", callback_data=f"admin_cancel_order_{order.id}")
        ])

    keyboard.append([
        InlineKeyboardButton("👤 View User", callback_data=f"admin_user_{order.user_id}"),
    ])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_orders")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.ORDER_DETAIL


@admin_only
async def handle_order_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle order filter selection."""
    return await show_order_list(update, context)


@admin_only
async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel an order (admin action)."""
    query = update.callback_query
    await query.answer("Cancelling order...")

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    order_id = int(query.data.split("_")[-1])
    await admin_service.cancel_order(order_id)

    logger.info(f"Admin cancelled order {order_id}")

    # Show updated order detail
    query.data = f"admin_order_{order_id}"
    return await show_order_detail(update, context)

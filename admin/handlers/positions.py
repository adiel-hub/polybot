"""Admin position management handler."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.config import ITEMS_PER_PAGE
from admin.utils.decorators import admin_only
from admin.utils.formatters import format_position_summary, format_pnl_emoji
from admin.services import AdminService

logger = logging.getLogger(__name__)


@admin_only
async def show_position_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display paginated position list."""
    query = update.callback_query
    if query:
        await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    # Get page from callback data
    page = 0
    if query and query.data.startswith("admin_positions_page_"):
        page = int(query.data.split("_")[-1])

    offset = page * ITEMS_PER_PAGE
    positions = await admin_service.get_positions(limit=ITEMS_PER_PAGE, offset=offset)
    total = await admin_service.count_positions()
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    text = f"🎯 *Position Management*\n\nTotal: {total} active positions | Page {page + 1}/{total_pages}"

    keyboard = []

    if positions:
        for pos in positions:
            pnl = pos.unrealized_pnl or 0
            pnl_indicator = "📈" if pnl > 0 else "📉" if pnl < 0 else "➖"
            market_short = (pos.market_question or "Unknown")[:25]
            keyboard.append([
                InlineKeyboardButton(
                    f"{pnl_indicator} #{pos.id} {pos.outcome} {pos.size:.1f}",
                    callback_data=f"admin_position_{pos.id}",
                )
            ])
    else:
        text += "\n\nNo active positions found."

    # Pagination
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"admin_positions_page_{page - 1}")
            )
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"admin_positions_page_{page + 1}")
            )
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    return AdminState.POSITION_LIST


@admin_only
async def show_position_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show detailed position information."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    position_id = int(query.data.split("_")[-1])
    position = await admin_service.get_position_by_id(position_id)

    if not position:
        await query.edit_message_text(
            "Position not found.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_positions")]
            ]),
        )
        return AdminState.POSITION_LIST

    text = format_position_summary(position)

    keyboard = [
        [InlineKeyboardButton("👤 View User", callback_data=f"admin_user_{position.user_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_positions")],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.POSITION_DETAIL

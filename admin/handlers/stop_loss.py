"""Admin stop loss management handler."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.config import ITEMS_PER_PAGE
from admin.utils.decorators import admin_only
from admin.utils.formatters import format_stop_loss_summary, format_datetime
from admin.services import AdminService

logger = logging.getLogger(__name__)


@admin_only
async def show_stop_loss_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display paginated stop loss list."""
    query = update.callback_query
    if query:
        await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    # Get page from callback data
    page = 0
    if query and query.data.startswith("admin_stoploss_page_"):
        page = int(query.data.split("_")[-1])

    offset = page * ITEMS_PER_PAGE
    stop_losses = await admin_service.get_stop_losses(
        limit=ITEMS_PER_PAGE, offset=offset, active_only=True
    )
    total = await admin_service.count_stop_losses(active_only=True)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    text = f"🛑 *Stop Loss Management*\n\nTotal: {total} active | Page {page + 1}/{total_pages}"

    keyboard = []

    if stop_losses:
        for sl in stop_losses:
            status = "🟢" if sl.is_active else "🔴"
            keyboard.append([
                InlineKeyboardButton(
                    f"{status} #{sl.id} Pos#{sl.position_id} @ ${sl.trigger_price:.4f}",
                    callback_data=f"admin_sl_{sl.id}",
                )
            ])
    else:
        text += "\n\nNo active stop losses found."

    # Pagination
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"admin_stoploss_page_{page - 1}")
            )
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"admin_stoploss_page_{page + 1}")
            )
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    return AdminState.STOP_LOSS_LIST


@admin_only
async def show_stop_loss_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show detailed stop loss information."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    sl_id = int(query.data.split("_")[-1])

    # Get stop loss from list
    stop_losses = await admin_service.get_stop_losses(limit=100, active_only=False)
    stop_loss = next((sl for sl in stop_losses if sl.id == sl_id), None)

    if not stop_loss:
        await query.edit_message_text(
            "Stop loss not found.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_stoploss")]
            ]),
        )
        return AdminState.STOP_LOSS_LIST

    text = format_stop_loss_summary(stop_loss)

    keyboard = []

    if stop_loss.is_active:
        keyboard.append([
            InlineKeyboardButton(
                "⚠️ Deactivate", callback_data=f"admin_sl_deactivate_{stop_loss.id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("👤 View User", callback_data=f"admin_user_{stop_loss.user_id}"),
    ])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_stoploss")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.STOP_LOSS_LIST


@admin_only
async def deactivate_stop_loss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Deactivate a stop loss."""
    query = update.callback_query
    await query.answer("Deactivating...")

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    sl_id = int(query.data.split("_")[-1])
    await admin_service.deactivate_stop_loss(sl_id)

    logger.info(f"Admin deactivated stop loss {sl_id}")

    # Return to list
    return await show_stop_loss_list(update, context)

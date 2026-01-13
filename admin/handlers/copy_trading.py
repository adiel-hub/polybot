"""Admin copy trading management handler."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.config import ITEMS_PER_PAGE
from admin.utils.decorators import admin_only
from admin.utils.formatters import format_copy_trader_summary, format_pnl_emoji
from admin.services import AdminService

logger = logging.getLogger(__name__)


@admin_only
async def show_copy_trading_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display paginated copy trading subscriptions."""
    query = update.callback_query
    if query:
        await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    # Get page from callback data
    page = 0
    if query and query.data.startswith("admin_copy_page_"):
        page = int(query.data.split("_")[-1])

    offset = page * ITEMS_PER_PAGE
    subscriptions = await admin_service.get_copy_subscriptions(
        limit=ITEMS_PER_PAGE, offset=offset
    )
    total = await admin_service.count_copy_subscriptions()
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    text = f"👥 *Copy Trading Management*\n\nTotal: {total} subscriptions | Page {page + 1}/{total_pages}"

    keyboard = []

    if subscriptions:
        for sub in subscriptions:
            status = "🟢" if sub.is_active else "🔴"
            trader_short = (sub.trader_name or sub.trader_address[:8])[:15]
            pnl = sub.total_pnl
            pnl_indicator = "📈" if pnl > 0 else "📉" if pnl < 0 else "➖"
            keyboard.append([
                InlineKeyboardButton(
                    f"{status} #{sub.id} {trader_short} {pnl_indicator}",
                    callback_data=f"admin_copy_sub_{sub.id}",
                )
            ])
    else:
        text += "\n\nNo copy trading subscriptions found."

    # Pagination
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"admin_copy_page_{page - 1}")
            )
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"admin_copy_page_{page + 1}")
            )
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    return AdminState.COPY_TRADING_LIST


@admin_only
async def show_trader_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show detailed copy trader subscription information."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    sub_id = int(query.data.split("_")[-1])

    # Get subscription from list
    subscriptions = await admin_service.get_copy_subscriptions(limit=100)
    subscription = next((s for s in subscriptions if s.id == sub_id), None)

    if not subscription:
        await query.edit_message_text(
            "Subscription not found.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_copy")]
            ]),
        )
        return AdminState.COPY_TRADING_LIST

    text = format_copy_trader_summary(subscription)

    keyboard = []

    if subscription.is_active:
        keyboard.append([
            InlineKeyboardButton(
                "⚠️ Deactivate", callback_data=f"admin_copy_deactivate_{subscription.id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("👤 View User", callback_data=f"admin_user_{subscription.user_id}"),
    ])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_copy")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.TRADER_DETAIL


@admin_only
async def deactivate_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Deactivate a copy trading subscription."""
    query = update.callback_query
    await query.answer("Deactivating...")

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    sub_id = int(query.data.split("_")[-1])
    await admin_service.deactivate_subscription(sub_id)

    logger.info(f"Admin deactivated copy trading subscription {sub_id}")

    # Return to list
    return await show_copy_trading_list(update, context)

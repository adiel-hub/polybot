"""Admin wallet and financial management handler."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.config import ITEMS_PER_PAGE
from admin.utils.decorators import admin_only
from admin.utils.formatters import format_wallet_summary, format_number, format_datetime
from admin.services import AdminService, StatsService

logger = logging.getLogger(__name__)


@admin_only
async def show_wallet_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display wallet/financial management menu."""
    query = update.callback_query
    if query:
        await query.answer()

    db = context.bot_data["db"]
    stats_service = StatsService(db)
    admin_service = AdminService(db)

    stats = await stats_service.get_dashboard_stats()
    financial = stats["financial"]

    text = (
        "💰 *Financial Management*\n\n"
        f"💵 Total Balance: {format_number(financial['total_balance'])}\n"
        f"📥 Total Deposits: {format_number(financial['total_deposits'])}\n"
        f"📤 Total Withdrawals: {format_number(financial['total_withdrawals'])}\n"
    )

    keyboard = [
        [InlineKeyboardButton("💰 View Wallets", callback_data="admin_wallets_list")],
        [InlineKeyboardButton("📥 Deposits", callback_data="admin_deposits")],
        [InlineKeyboardButton("📤 Withdrawals", callback_data="admin_withdrawals")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_menu")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    return AdminState.WALLET_LIST


@admin_only
async def show_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display paginated wallet list."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    # Get page from callback data
    page = 0
    if query.data.startswith("admin_wallets_list_page_"):
        page = int(query.data.split("_")[-1])

    offset = page * ITEMS_PER_PAGE
    wallets = await admin_service.get_wallets(limit=ITEMS_PER_PAGE, offset=offset)
    total = await admin_service.count_wallets()
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    text = f"💰 *Wallets*\n\nTotal: {total} | Page {page + 1}/{total_pages}"

    keyboard = []

    if wallets:
        for wallet in wallets:
            addr_short = f"{wallet.address[:6]}...{wallet.address[-4:]}"
            keyboard.append([
                InlineKeyboardButton(
                    f"💰 {addr_short} - ${wallet.usdc_balance:.2f}",
                    callback_data=f"admin_wallet_{wallet.id}",
                )
            ])
    else:
        text += "\n\nNo wallets found."

    # Pagination
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"admin_wallets_list_page_{page - 1}")
            )
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"admin_wallets_list_page_{page + 1}")
            )
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_wallets")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.WALLET_LIST


@admin_only
async def show_wallet_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display wallet details."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    # Extract wallet ID from callback data
    wallet_id = int(query.data.split("_")[-1])
    wallet = await admin_service.get_wallet_by_id(wallet_id)

    if not wallet:
        await query.edit_message_text(
            "❌ Wallet not found.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_wallets_list")]
            ]),
        )
        return AdminState.WALLET_LIST

    # Get user info
    user = await admin_service.get_user_by_id(wallet.user_id)

    text = format_wallet_summary(wallet, user)

    keyboard = [
        [InlineKeyboardButton(f"👤 View User #{wallet.user_id}", callback_data=f"admin_user_{wallet.user_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_wallets_list")],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.WALLET_DETAIL


@admin_only
async def show_deposit_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display paginated deposit list."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    # Get page from callback data
    page = 0
    if query.data.startswith("admin_deposits_page_"):
        page = int(query.data.split("_")[-1])

    offset = page * ITEMS_PER_PAGE
    deposits = await admin_service.get_deposits(limit=ITEMS_PER_PAGE, offset=offset)
    total = await admin_service.count_deposits()
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    text = f"📥 *Deposits*\n\nTotal: {total} | Page {page + 1}/{total_pages}\n"

    if deposits:
        for dep in deposits:
            status_emoji = {"PENDING": "⏳", "CONFIRMED": "✅", "FAILED": "❌"}.get(
                dep.get("status", ""), "❓"
            )
            text += (
                f"\n{status_emoji} ${dep.get('amount', 0):.2f} - "
                f"User #{dep.get('user_id', 'N/A')}"
            )
    else:
        text += "\nNo deposits found."

    keyboard = []

    # Pagination
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"admin_deposits_page_{page - 1}")
            )
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"admin_deposits_page_{page + 1}")
            )
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_wallets")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.DEPOSIT_LIST


@admin_only
async def show_withdrawal_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display paginated withdrawal list."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    # Get page from callback data
    page = 0
    if query.data.startswith("admin_withdrawals_page_"):
        page = int(query.data.split("_")[-1])

    offset = page * ITEMS_PER_PAGE
    withdrawals = await admin_service.get_withdrawals(limit=ITEMS_PER_PAGE, offset=offset)
    total = await admin_service.count_withdrawals()
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    text = f"📤 *Withdrawals*\n\nTotal: {total} | Page {page + 1}/{total_pages}\n"

    if withdrawals:
        for wd in withdrawals:
            status_emoji = {"PENDING": "⏳", "CONFIRMED": "✅", "FAILED": "❌"}.get(
                wd.get("status", ""), "❓"
            )
            text += (
                f"\n{status_emoji} ${wd.get('amount', 0):.2f} - "
                f"User #{wd.get('user_id', 'N/A')}"
            )
    else:
        text += "\nNo withdrawals found."

    keyboard = []

    # Pagination
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"admin_withdrawals_page_{page - 1}")
            )
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"admin_withdrawals_page_{page + 1}")
            )
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_wallets")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.WITHDRAWAL_LIST

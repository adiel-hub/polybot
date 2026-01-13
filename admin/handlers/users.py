"""Admin user management handler."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.config import ITEMS_PER_PAGE
from admin.utils.decorators import admin_only
from admin.utils.formatters import format_user_summary, format_datetime
from admin.services import AdminService
from admin.keyboards.pagination import build_pagination_keyboard

logger = logging.getLogger(__name__)


@admin_only
async def show_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display paginated user list."""
    query = update.callback_query
    if query:
        await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    # Get page from callback data or default to 0
    page = 0
    if query and query.data.startswith("admin_users_page_"):
        page = int(query.data.split("_")[-1])

    offset = page * ITEMS_PER_PAGE
    users = await admin_service.get_users(limit=ITEMS_PER_PAGE, offset=offset)
    total = await admin_service.count_users()
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if not users:
        text = "👥 *User Management*\n\nNo users found."
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_menu")]]
    else:
        text = f"👥 *User Management*\n\nTotal: {total} users | Page {page + 1}/{total_pages}\n\n"

        keyboard = []
        for user in users:
            status = "✅" if user.is_active else "⛔"
            username = f"@{user.telegram_username}" if user.telegram_username else f"ID:{user.telegram_id}"
            keyboard.append([
                InlineKeyboardButton(
                    f"{status} #{user.id} - {username}",
                    callback_data=f"admin_user_{user.id}",
                )
            ])

        # Pagination
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"admin_users_page_{page - 1}")
            )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"admin_users_page_{page + 1}")
            )
        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([
            InlineKeyboardButton("🔍 Search", callback_data="admin_user_search"),
            InlineKeyboardButton("🔙 Back", callback_data="admin_menu"),
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    return AdminState.USER_LIST


@admin_only
async def show_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show detailed user information."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    # Get user ID from callback data
    user_id = int(query.data.split("_")[-1])
    details = await admin_service.get_user_full_details(user_id)

    if not details or not details.get("user"):
        await query.edit_message_text(
            "User not found.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_users")]
            ]),
        )
        return AdminState.USER_LIST

    user = details["user"]
    wallet = details.get("wallet")
    positions = details.get("positions", [])
    total_orders = details.get("total_orders", 0)

    # Format text
    text = format_user_summary(user, wallet)
    text += f"\n\n📊 *Statistics*\n"
    text += f"├ Total Orders: {total_orders}\n"
    text += f"└ Active Positions: {len(positions)}"

    # Build keyboard
    keyboard = []

    if user.is_active:
        keyboard.append([
            InlineKeyboardButton("⛔ Suspend User", callback_data=f"admin_suspend_{user.id}")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("✅ Activate User", callback_data=f"admin_activate_{user.id}")
        ])

    keyboard.append([
        InlineKeyboardButton("📋 Orders", callback_data=f"admin_user_orders_{user.id}"),
        InlineKeyboardButton("🎯 Positions", callback_data=f"admin_user_positions_{user.id}"),
    ])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_users")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.USER_DETAIL


@admin_only
async def prompt_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for user search input."""
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_users")]]

    await query.edit_message_text(
        "🔍 *Search Users*\n\n"
        "Enter a Telegram ID, username, or user ID to search:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.USER_SEARCH


@admin_only
async def handle_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user search input."""
    search_query = update.message.text.strip()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    users = await admin_service.search_users(search_query)

    if not users:
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_users")]]
        await update.message.reply_text(
            f"No users found matching '{search_query}'.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return AdminState.USER_LIST

    text = f"🔍 *Search Results*\n\nFound {len(users)} user(s):\n"

    keyboard = []
    for user in users[:10]:  # Limit to 10 results
        status = "✅" if user.is_active else "⛔"
        username = f"@{user.telegram_username}" if user.telegram_username else f"ID:{user.telegram_id}"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} #{user.id} - {username}",
                callback_data=f"admin_user_{user.id}",
            )
        ])

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_users")])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.USER_LIST


@admin_only
async def suspend_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Suspend a user."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    user_id = int(query.data.split("_")[-1])
    await admin_service.suspend_user(user_id)

    logger.info(f"Admin suspended user {user_id}")

    # Refresh user detail
    context.user_data["admin_message"] = f"User #{user_id} has been suspended."

    # Simulate callback to show updated user detail
    query.data = f"admin_user_{user_id}"
    return await show_user_detail(update, context)


@admin_only
async def activate_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Activate a user."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    admin_service = AdminService(db)

    user_id = int(query.data.split("_")[-1])
    await admin_service.activate_user(user_id)

    logger.info(f"Admin activated user {user_id}")

    # Refresh user detail
    query.data = f"admin_user_{user_id}"
    return await show_user_detail(update, context)

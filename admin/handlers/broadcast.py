"""Admin broadcast handler for sending messages to users."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.utils.decorators import admin_only
from admin.services import BroadcastService

logger = logging.getLogger(__name__)

# Broadcast filter options
BROADCAST_FILTERS = [
    ("All Users", "all"),
    ("Active Only", "active"),
    ("With Balance", "with_balance"),
]


@admin_only
async def show_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display broadcast menu."""
    query = update.callback_query
    if query:
        await query.answer()

    db = context.bot_data["db"]
    bot = context.bot
    broadcast_service = BroadcastService(db, bot)

    # Get user counts for each filter
    all_count = await broadcast_service.count_target_users("all")
    active_count = await broadcast_service.count_target_users("active")
    balance_count = await broadcast_service.count_target_users("with_balance")

    text = (
        "📢 *Broadcast Message*\n\n"
        "Send a message to multiple users.\n\n"
        f"👥 All Users: {all_count}\n"
        f"✅ Active Users: {active_count}\n"
        f"💰 With Balance: {balance_count}\n\n"
        "Select target audience:"
    )

    keyboard = [
        [InlineKeyboardButton(f"👥 All Users ({all_count})", callback_data="admin_broadcast_all")],
        [
            InlineKeyboardButton(
                f"✅ Active Only ({active_count})", callback_data="admin_broadcast_active"
            )
        ],
        [
            InlineKeyboardButton(
                f"💰 With Balance ({balance_count})", callback_data="admin_broadcast_with_balance"
            )
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_menu")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    return AdminState.BROADCAST_MENU


@admin_only
async def prompt_broadcast_compose(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to compose broadcast message."""
    query = update.callback_query
    await query.answer()

    # Extract filter from callback
    filter_type = query.data.replace("admin_broadcast_", "")
    context.user_data["broadcast_filter"] = filter_type

    filter_labels = {"all": "All Users", "active": "Active Users", "with_balance": "Users with Balance"}
    filter_label = filter_labels.get(filter_type, filter_type)

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast")]]

    await query.edit_message_text(
        f"📢 *Compose Broadcast*\n\n"
        f"Target: {filter_label}\n\n"
        "✏️ Enter your message below.\n\n"
        "💡 You can use Markdown formatting:\n"
        "• *bold* → **bold**\n"
        "• _italic_ → _italic_\n"
        "• `code` → `code`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.BROADCAST_COMPOSE


@admin_only
async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle broadcast message input."""
    message_text = update.message.text.strip()

    if not message_text:
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast")]]
        await update.message.reply_text(
            "Message cannot be empty. Please enter a message:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return AdminState.BROADCAST_COMPOSE

    context.user_data["broadcast_message"] = message_text

    return await confirm_broadcast(update, context)


@admin_only
async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show broadcast confirmation with preview."""
    filter_type = context.user_data.get("broadcast_filter", "all")
    message_text = context.user_data.get("broadcast_message", "")

    db = context.bot_data["db"]
    bot = context.bot
    broadcast_service = BroadcastService(db, bot)
    target_count = await broadcast_service.count_target_users(filter_type)

    filter_labels = {"all": "All Users", "active": "Active Users", "with_balance": "Users with Balance"}
    filter_label = filter_labels.get(filter_type, filter_type)

    text = (
        "📢 *Broadcast Preview*\n\n"
        f"🎯 Target: {filter_label} ({target_count} users)\n\n"
        "📝 *Message:*\n"
        "───────────────\n"
        f"{message_text}\n"
        "───────────────\n\n"
        "⚠️ This action cannot be undone.\n"
        "Are you sure you want to send this message?"
    )

    keyboard = [
        [
            InlineKeyboardButton("📤 Send", callback_data="admin_broadcast_send"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"admin_broadcast_{filter_type}"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast")],
    ]

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    return AdminState.BROADCAST_CONFIRM


@admin_only
async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute the broadcast."""
    query = update.callback_query
    await query.answer("Sending broadcast...")

    filter_type = context.user_data.get("broadcast_filter", "all")
    message_text = context.user_data.get("broadcast_message", "")

    if not message_text:
        await query.edit_message_text(
            "Error: No message to send.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_broadcast")]
            ]),
        )
        return AdminState.BROADCAST_MENU

    db = context.bot_data["db"]
    bot = context.bot
    broadcast_service = BroadcastService(db, bot)

    # Show progress message
    await query.edit_message_text(
        "📤 *Sending Broadcast...*\n\n⏳ Please wait...",
        parse_mode="Markdown",
    )

    # Send broadcast
    result = await broadcast_service.broadcast_message(
        message=message_text,
        filter_type=filter_type,
    )

    # Show results
    text = (
        "📢 *Broadcast Complete*\n\n"
        f"✅ Sent: {result['sent']}\n"
        f"❌ Failed: {result['failed']}\n"
        f"📊 Total: {result['total']}\n"
    )

    if result["failed"] > 0:
        text += f"\n⚠️ {result['failed']} messages failed to deliver."

    # Clear broadcast data
    context.user_data.pop("broadcast_filter", None)
    context.user_data.pop("broadcast_message", None)

    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_menu")]]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    logger.info(
        f"Admin broadcast completed: {result['sent']}/{result['total']} sent, "
        f"{result['failed']} failed"
    )

    return AdminState.ADMIN_MENU

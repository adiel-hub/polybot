"""Admin broadcast handler for sending messages to users."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.utils.decorators import admin_only
from admin.services import BroadcastService

logger = logging.getLogger(__name__)


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

    # Reset broadcast data
    context.user_data.pop("broadcast_message", None)
    context.user_data.pop("broadcast_image", None)
    context.user_data.pop("broadcast_buttons", None)

    filter_labels = {"all": "All Users", "active": "Active Users", "with_balance": "Users with Balance"}
    filter_label = filter_labels.get(filter_type, filter_type)

    keyboard = [
        [InlineKeyboardButton("📝 Text Only", callback_data="admin_broadcast_type_text")],
        [InlineKeyboardButton("🖼️ Image + Text", callback_data="admin_broadcast_type_image")],
        [InlineKeyboardButton("🔘 Add Buttons", callback_data="admin_broadcast_type_buttons")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast")],
    ]

    await query.edit_message_text(
        f"📢 *Compose Broadcast*\n\n"
        f"Target: {filter_label}\n\n"
        "Choose broadcast type:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.BROADCAST_COMPOSE


@admin_only
async def handle_broadcast_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle broadcast type selection."""
    query = update.callback_query
    await query.answer()

    broadcast_type = query.data.replace("admin_broadcast_type_", "")
    context.user_data["broadcast_type"] = broadcast_type

    filter_type = context.user_data.get("broadcast_filter", "all")
    filter_labels = {"all": "All Users", "active": "Active Users", "with_balance": "Users with Balance"}
    filter_label = filter_labels.get(filter_type, filter_type)

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast")]]

    if broadcast_type == "text":
        text = (
            f"📢 *Compose Broadcast*\n\n"
            f"Target: {filter_label}\n"
            f"Type: Text Only\n\n"
            "✏️ Enter your message below.\n\n"
            "💡 **Formatting supported:**\n"
            "• `*bold*` → *bold*\n"
            "• `_italic_` → _italic_\n"
            "• `` `code` `` → `code`\n"
            "• `[link](url)` → clickable link\n\n"
            "✨ **Example:**\n"
            "`*Welcome!* Check out our [website](https://example.com)`"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return AdminState.BROADCAST_COMPOSE_TEXT

    elif broadcast_type == "image":
        text = (
            f"📢 *Compose Broadcast*\n\n"
            f"Target: {filter_label}\n"
            f"Type: Image + Text\n\n"
            "📸 Send an image with optional caption.\n\n"
            "You can send:\n"
            "• Photo directly\n"
            "• Photo with caption text\n\n"
            "Markdown formatting is supported in caption."
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return AdminState.BROADCAST_COMPOSE_IMAGE

    elif broadcast_type == "buttons":
        text = (
            f"📢 *Compose Broadcast with Buttons*\n\n"
            f"Target: {filter_label}\n\n"
            "✏️ First, enter your message text:\n\n"
            "Markdown formatting is supported."
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return AdminState.BROADCAST_COMPOSE_TEXT

    return AdminState.BROADCAST_COMPOSE


@admin_only
async def handle_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle broadcast text message input."""
    message_text = update.message.text.strip()

    if not message_text:
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast")]]
        await update.message.reply_text(
            "❌ Message cannot be empty. Please enter a message:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return AdminState.BROADCAST_COMPOSE_TEXT

    context.user_data["broadcast_message"] = message_text

    # If buttons type, prompt for buttons
    if context.user_data.get("broadcast_type") == "buttons":
        return await prompt_add_buttons(update, context)

    # Otherwise go to confirmation
    return await confirm_broadcast(update, context)


@admin_only
async def handle_broadcast_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle broadcast image input."""
    if not update.message.photo:
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast")]]
        await update.message.reply_text(
            "❌ Please send a photo image.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return AdminState.BROADCAST_COMPOSE_IMAGE

    # Get the largest photo
    photo = update.message.photo[-1]
    context.user_data["broadcast_image"] = photo.file_id

    # Get caption if provided
    if update.message.caption:
        context.user_data["broadcast_message"] = update.message.caption.strip()

    return await confirm_broadcast(update, context)


@admin_only
async def prompt_add_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt admin to add buttons."""
    keyboard = [
        [InlineKeyboardButton("➕ Add Button", callback_data="admin_broadcast_add_button")],
        [InlineKeyboardButton("✅ Done", callback_data="admin_broadcast_confirm_preview")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast")],
    ]

    buttons = context.user_data.get("broadcast_buttons", [])
    buttons_text = "\n".join([f"{i+1}. {btn['text']} → {btn['url']}" for i, btn in enumerate(buttons)])

    text = (
        "🔘 *Add Buttons to Broadcast*\n\n"
        f"Current buttons ({len(buttons)}):\n"
        f"{buttons_text if buttons else '_No buttons added yet_'}\n\n"
        "Choose an option:"
    )

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

    return AdminState.BROADCAST_ADD_BUTTONS


@admin_only
async def prompt_button_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for button details."""
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast_buttons_back")]]

    await query.edit_message_text(
        "🔘 *Add Button*\n\n"
        "Enter button details in format:\n"
        "`Button Text | https://example.com`\n\n"
        "Example:\n"
        "`Visit Website | https://polymarket.com`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return AdminState.BROADCAST_BUTTON_INPUT


@admin_only
async def handle_button_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle button input."""
    text = update.message.text.strip()

    if "|" not in text:
        await update.message.reply_text(
            "❌ Invalid format. Please use:\n"
            "`Button Text | URL`",
            parse_mode="Markdown",
        )
        return AdminState.BROADCAST_BUTTON_INPUT

    parts = text.split("|", 1)
    button_text = parts[0].strip()
    button_url = parts[1].strip()

    if not button_text or not button_url:
        await update.message.reply_text(
            "❌ Both button text and URL are required.",
        )
        return AdminState.BROADCAST_BUTTON_INPUT

    # Add button
    if "broadcast_buttons" not in context.user_data:
        context.user_data["broadcast_buttons"] = []

    context.user_data["broadcast_buttons"].append({
        "text": button_text,
        "url": button_url,
    })

    await update.message.reply_text("✅ Button added!")

    return await prompt_add_buttons(update, context)


@admin_only
async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show broadcast confirmation with preview."""
    filter_type = context.user_data.get("broadcast_filter", "all")
    message_text = context.user_data.get("broadcast_message", "")
    image_file_id = context.user_data.get("broadcast_image")
    buttons = context.user_data.get("broadcast_buttons", [])
    broadcast_type = context.user_data.get("broadcast_type", "text")

    db = context.bot_data["db"]
    bot = context.bot
    broadcast_service = BroadcastService(db, bot)
    target_count = await broadcast_service.count_target_users(filter_type)

    filter_labels = {"all": "All Users", "active": "Active Users", "with_balance": "Users with Balance"}
    filter_label = filter_labels.get(filter_type, filter_type)

    # Build preview keyboard
    preview_keyboard = []
    for btn in buttons:
        preview_keyboard.append([InlineKeyboardButton(btn["text"], url=btn["url"])])

    # Send preview
    preview_text = f"📢 *Preview of your broadcast:*\n\n{message_text}" if message_text else "📸 Image with optional caption"

    if image_file_id:
        await update.effective_chat.send_photo(
            photo=image_file_id,
            caption=preview_text,
            reply_markup=InlineKeyboardMarkup(preview_keyboard) if preview_keyboard else None,
            parse_mode="Markdown",
        )
    else:
        await update.effective_chat.send_message(
            text=preview_text,
            reply_markup=InlineKeyboardMarkup(preview_keyboard) if preview_keyboard else None,
            parse_mode="Markdown",
        )

    # Confirmation message
    text = (
        "📊 *Broadcast Summary*\n\n"
        f"🎯 Target: {filter_label} ({target_count} users)\n"
        f"📝 Type: {broadcast_type.title()}\n"
        f"🔘 Buttons: {len(buttons)}\n\n"
        "⚠️ This action cannot be undone.\n"
        "Are you sure you want to send?"
    )

    keyboard = [
        [
            InlineKeyboardButton("📤 Send Now", callback_data="admin_broadcast_send"),
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
        await update.callback_query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    return AdminState.BROADCAST_CONFIRM


@admin_only
async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute the broadcast with real-time progress."""
    query = update.callback_query
    await query.answer("Starting broadcast...")

    filter_type = context.user_data.get("broadcast_filter", "all")
    message_text = context.user_data.get("broadcast_message", "")
    image_file_id = context.user_data.get("broadcast_image")
    buttons = context.user_data.get("broadcast_buttons", [])

    db = context.bot_data["db"]
    bot = context.bot
    broadcast_service = BroadcastService(db, bot)

    # Get total count
    target_count = await broadcast_service.count_target_users(filter_type)

    # Show initial progress
    progress_message = await query.edit_message_text(
        f"📤 *Sending Broadcast...*\n\n"
        f"📊 Progress: 0/{target_count} (0%)\n"
        f"✅ Sent: 0\n"
        f"❌ Failed: 0\n\n"
        f"⏳ Please wait...",
        parse_mode="Markdown",
    )

    # Progress callback to update message
    last_update = 0
    async def progress_callback(sent, failed, total):
        nonlocal last_update
        current = sent + failed

        # Update every 5% or every 10 messages
        if current - last_update < 10 and current < total:
            return

        last_update = current
        percentage = int((current / total) * 100) if total > 0 else 0

        # Progress bar
        bar_length = 20
        filled = int((current / total) * bar_length) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        try:
            await progress_message.edit_text(
                f"📤 *Sending Broadcast...*\n\n"
                f"{bar} {percentage}%\n\n"
                f"📊 Progress: {current}/{total}\n"
                f"✅ Sent: {sent}\n"
                f"❌ Failed: {failed}\n\n"
                f"⏳ Please wait...",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"Failed to update progress: {e}")

    # Build button keyboard if provided
    reply_markup = None
    if buttons:
        keyboard = [[InlineKeyboardButton(btn["text"], url=btn["url"])] for btn in buttons]
        reply_markup = InlineKeyboardMarkup(keyboard)

    # Send broadcast
    result = await broadcast_service.broadcast_message(
        message=message_text,
        filter_type=filter_type,
        progress_callback=progress_callback,
        image_file_id=image_file_id,
        reply_markup=reply_markup,
    )

    # Show final results
    percentage_sent = int((result['sent'] / result['total']) * 100) if result['total'] > 0 else 0

    text = (
        "✅ *Broadcast Complete!*\n\n"
        f"📊 Results:\n"
        f"✅ Successfully sent: {result['sent']} ({percentage_sent}%)\n"
        f"❌ Failed: {result['failed']}\n"
        f"📈 Total attempted: {result['total']}\n"
    )

    if result["failed"] > 0:
        text += f"\n⚠️ {result['failed']} messages failed to deliver (users may have blocked the bot)."

    # Clear broadcast data
    context.user_data.pop("broadcast_filter", None)
    context.user_data.pop("broadcast_message", None)
    context.user_data.pop("broadcast_image", None)
    context.user_data.pop("broadcast_buttons", None)
    context.user_data.pop("broadcast_type", None)

    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="admin_menu")]]

    await progress_message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    logger.info(
        f"Admin broadcast completed: {result['sent']}/{result['total']} sent, "
        f"{result['failed']} failed"
    )

    return AdminState.ADMIN_MENU

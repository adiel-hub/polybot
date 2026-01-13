"""Start command and license flow handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.handlers.menu import show_main_menu
from config.constants import LICENSE_TEXT

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start command."""
    user = update.effective_user
    user_service = context.bot_data["user_service"]

    # Check if user already registered
    if await user_service.is_registered(user.id):
        return await show_main_menu(update, context)

    # Show license agreement
    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data="license_accept"),
            InlineKeyboardButton("❌ Decline", callback_data="license_decline"),
        ]
    ]

    await update.message.reply_text(
        LICENSE_TEXT,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.LICENSE_PROMPT


async def license_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle license acceptance - generate wallet."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    # Show loading message
    await query.edit_message_text(
        "🔐 Creating your secure wallet...\n\n⏳ Please wait."
    )

    try:
        # Register user and generate wallet
        wallet_address = await user_service.register_user(
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        # Show success message
        await query.edit_message_text(
            f"✅ *Your PolyBot wallet is ready!*\n\n"
            f"🔑 Your wallet address:\n"
            f"`{wallet_address}`\n\n"
            f"🚀 *Get started:*\n"
            f"💳 Fund your wallet\n"
            f"👥 Copy trade your favorite traders\n"
            f"🎁 Invite your friends and earn referral rewards\n\n"
            f"📋 *You can also:*\n"
            f"📈 Place market and limit orders\n"
            f"📊 Manage your portfolio\n"
            f"🛡️ Protect your positions with Stop Loss orders\n"
            f"🤖 Set up automated strategies that auto apply to new orders\n"
            f"⚙️ Tune your trading settings and toggle automations\n\n"
            f"🔜 More features coming soon!\n"
            f"👥 Join our community to stay up to date.",
            parse_mode="Markdown",
        )

        # Show main menu after a brief delay
        return await show_main_menu(update, context, send_new=True)

    except Exception as e:
        logger.error(f"Registration failed for user {user.id}: {e}")
        await query.edit_message_text(
            "❌ Registration failed. Please try again with /start"
        )
        return ConversationState.LICENSE_PROMPT


async def license_decline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle license decline."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "⚠️ You must accept the terms to use PolyBot.\n\n"
        "📝 Send /start again when you're ready."
    )

    return ConversationState.LICENSE_PROMPT

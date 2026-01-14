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

    # Extract deep link parameters from /start
    referral_code = None
    market_id = None

    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("ref_"):
            referral_code = arg[4:]  # Remove "ref_" prefix
            logger.info(f"User {user.id} started with referral code: {referral_code}")
        elif arg.startswith("m_"):
            market_id = arg[2:]  # Remove "m_" prefix
            logger.info(f"User {user.id} started with market deep link: {market_id}")

    # Store for use during registration or after login
    context.user_data["referral_code"] = referral_code
    if market_id:
        context.user_data["deep_link_market"] = market_id

    # Check if user already registered
    if await user_service.is_registered(user.id):
        # If there's a market deep link, show that market's trade page
        if market_id:
            logger.info(f"User {user.id} is registered, processing market deep link: {market_id}")
            # Store minimal market info to trigger detail view
            context.user_data["pending_market_id"] = market_id
            return await show_main_menu(update, context)
        logger.info(f"User {user.id} is registered, showing main menu")
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
        new_user, wallet = await user_service.register_user(
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        # Generate referral code for the new user
        await user_service.generate_referral_code_for_user(new_user.id)

        # Link referral if code provided
        referral_code = context.user_data.get("referral_code")
        if referral_code:
            referral_service = context.bot_data["referral_service"]
            await referral_service.link_referral(new_user.id, referral_code)

        # Check if there was a deep link market
        deep_link_market = context.user_data.get("deep_link_market")
        if deep_link_market:
            # Transfer to pending_market_id for menu handler
            context.user_data["pending_market_id"] = deep_link_market
            logger.info(f"New user registered via market deep link: {deep_link_market}")

        # Show success message
        await query.edit_message_text(
            f"✅ *Your PolyBot wallet is ready!*\n\n"
            f"🔑 Your wallet address:\n"
            f"`{wallet.address}`\n\n"
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

        # Show main menu (or market detail if deep link) after a brief delay
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

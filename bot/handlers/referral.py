"""Referral program handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState

logger = logging.getLogger(__name__)


async def show_referral_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Display referral program dashboard."""
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    referral_service = context.bot_data["referral_service"]

    # Get referral stats
    stats = await referral_service.get_referral_stats(user.id)

    # Get referral link
    bot_username = context.bot.username
    referral_link = await referral_service.get_referral_link(user.id, bot_username)

    # Build referral menu message
    message = (
        f"*Referral Program*\n"
        f"Earn commissions when your referrals trade.\n\n"
        f"📊 *Commission Tiers*\n"
        f"├ Tier 1 (people you invite): 25%\n"
        f"├ Tier 2 (people invited by your Tier 1): 5%\n"
        f"└ Tier 3 (people invited by your Tier 2): 3%\n\n"
        f"💡 *Get referrals*\n"
        f"Share your link anywhere, or add PolyBot to your groups.\n"
        f"PolyBot parses market links and /polybot search commands.\n"
        f"When someone taps \"Trade on PolyBot\", they're automatically credited\n"
        f"as your referral.\n\n"
        f"🔗 *Your reflink* (tap to copy)\n"
        f"👉 `{referral_link}`\n\n"
        f"📈 *Your stats*\n"
        f"├ Referrals: {stats['total_referrals']} "
        f"(T1: {stats['referral_counts']['t1']} • "
        f"T2: {stats['referral_counts']['t2']} • "
        f"T3: {stats['referral_counts']['t3']})\n"
        f"├ Lifetime Earnings: ${stats['lifetime_earned']:.2f}\n"
        f"├ Total Claimed: ${stats['total_claimed']:.2f}\n"
        f"└ Claimable: ${stats['claimable']:.2f} (min ${referral_service.MIN_CLAIM_AMOUNT:.2f})\n\n"
        f"Quick start: share your link with 3 friends, then add PolyBot to your\n"
        f"most active group to start earning."
    )

    # Build keyboard
    keyboard = []

    # Claim button (enabled only if balance >= min amount)
    if stats['claimable'] >= referral_service.MIN_CLAIM_AMOUNT:
        keyboard.append([
            InlineKeyboardButton(
                f"💵 Claim ${stats['claimable']:.2f}",
                callback_data="ref_claim"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                f"💵 Claim ${stats['claimable']:.2f}",
                callback_data="noop"
            )
        ])

    # Other action buttons
    keyboard.append([
        InlineKeyboardButton("📱 Create QR", callback_data="ref_qr"),
    ])
    keyboard.append([
        InlineKeyboardButton("🗂️ Add to Group ↗", callback_data="ref_group"),
    ])

    # Back button
    keyboard.append([
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    if query:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    return ConversationState.REFERRAL_MENU


async def handle_claim_earnings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle claim earnings button."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    referral_service = context.bot_data["referral_service"]

    # Attempt to claim
    success, message = await referral_service.claim_earnings(user.id)

    if success:
        # Show success message
        await query.edit_message_text(
            f"✅ *Earnings Claimed*\n\n"
            f"{message}\n\n"
            f"The amount has been added to your wallet balance.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 Referral Menu", callback_data="menu_rewards")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]),
        )
    else:
        # Show error message
        await query.edit_message_text(
            f"❌ *Claim Failed*\n\n"
            f"{message}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="menu_rewards")],
            ]),
        )

    return ConversationState.REFERRAL_MENU


async def handle_create_qr(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle QR code generation for referral link."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    referral_service = context.bot_data["referral_service"]

    # Get referral link
    bot_username = context.bot.username
    referral_link = await referral_service.get_referral_link(user.id, bot_username)

    # For now, show a simple message with the link
    # In the future, this could generate an actual QR code image
    await query.edit_message_text(
        f"📱 *QR Code*\n\n"
        f"Share this link to invite friends:\n\n"
        f"`{referral_link}`\n\n"
        f"🔜 QR code generation coming soon!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="menu_rewards")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]),
    )

    return ConversationState.REFERRAL_QR


async def handle_add_to_group(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle add to group instructions."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        f"👥 *Add to Group*\n\n"
        f"Add PolyBot to your Telegram groups to earn rewards!\n\n"
        f"*How it works:*\n"
        f"1. Add @{context.bot.username} to your group\n"
        f"2. When members search markets or click links\n"
        f"3. Anyone who taps \"Trade on PolyBot\" becomes your referral\n\n"
        f"🔜 Group features coming soon!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="menu_rewards")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]),
    )

    return ConversationState.REFERRAL_MENU

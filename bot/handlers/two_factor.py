"""Two-Factor Authentication handlers."""

import logging
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState

logger = logging.getLogger(__name__)


async def show_2fa_intro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Show 2FA introduction matching screenshot design.

    Display:
    - Title: "Enable Two-Factor Authentication"
    - Explanation of what 2FA protects
    - List of supported apps
    - Continue and Cancel buttons
    """
    query = update.callback_query
    if query:
        await query.answer()

    message_text = (
        "🔐 *Enable Two-Factor Authentication*\n\n"
        "2FA adds an extra layer of security to your account. When enabled, "
        "you'll need to enter a 6-digit code from your authenticator app for:\n\n"
        "• Withdrawals\n"
        "• Private key export\n\n"
        "✅ *Supported Apps:*\n"
        "• Google Authenticator\n"
        "• Authy\n"
        "• 1Password\n"
        "• Microsoft Authenticator\n\n"
        "Tap Continue to generate your secret key."
    )

    keyboard = [
        [
            InlineKeyboardButton("▶️ Continue", callback_data="2fa_continue"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu_settings"),
        ]
    ]

    if query:
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    return ConversationState.TWO_FA_SETUP


async def handle_2fa_continue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle Continue button - generate secret and show QR code.

    Flow:
    1. Generate TOTP secret via UserService
    2. Create QR code
    3. Send QR code as photo
    4. Show "Enter 6-digit code" prompt
    5. Move to TWO_FA_VERIFY state
    """
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_service = context.bot_data["user_service"]

    try:
        # Show loading message
        await query.edit_message_text("⏳ Generating your 2FA secret...")

        # Generate TOTP secret and QR code
        secret, qr_code = await user_service.setup_2fa(user.id)

        # Store secret temporarily in user_data for verification
        context.user_data["2fa_setup_secret"] = secret
        context.user_data["2fa_verification_attempts"] = 0

        # Send QR code as photo
        qr_code.seek(0)
        caption = (
            "📱 *Scan this QR Code*\n\n"
            "1. Open your authenticator app\n"
            "2. Scan this QR code\n"
            "3. Enter the 6-digit code below\n\n"
            f"🔑 *Or manually enter:* `{secret}`"
        )

        await query.message.reply_photo(
            photo=qr_code,
            caption=caption,
            parse_mode="Markdown",
        )

        # Show verification prompt
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="menu_settings")]]
        await query.message.reply_text(
            "✏️ *Enter Verification Code*\n\n"
            "Enter the 6-digit code from your authenticator app:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return ConversationState.TWO_FA_VERIFY

    except Exception as e:
        logger.error(f"2FA setup failed for user {user.id}: {e}")
        await query.edit_message_text(
            "❌ Failed to set up 2FA. Please try again later.\n\n"
            "Use /start to return to the main menu.",
            parse_mode="Markdown",
        )
        return ConversationState.MAIN_MENU


async def handle_2fa_verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle 6-digit code verification.

    This handles TWO scenarios:
    1. Initial 2FA setup verification
    2. Verification for protected actions (withdraw, export_key)

    Flow:
    1. Get code from message
    2. Verify via UserService.verify_2fa_token()
    3. If valid:
       - For setup: Enable 2FA in settings and show success
       - For protected action: Mark as verified and route to original action
    4. If invalid:
       - Show error and allow retry (3 attempts max)
    """
    user = update.effective_user
    user_service = context.bot_data["user_service"]

    # Get the code from the message
    code = update.message.text.strip()

    # Validate format (6 digits)
    if not code.isdigit() or len(code) != 6:
        await update.message.reply_text(
            "❌ *Invalid Format*\n\n"
            "Please enter a 6-digit code (numbers only).",
            parse_mode="Markdown",
        )
        return ConversationState.TWO_FA_VERIFY

    # Check verification attempts
    attempts = context.user_data.get("2fa_verification_attempts", 0)
    if attempts >= 3:
        context.user_data.pop("2fa_setup_secret", None)
        context.user_data.pop("2fa_verification_attempts", None)
        context.user_data.pop("pending_2fa_action", None)

        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]]
        await update.message.reply_text(
            "❌ *Too Many Failed Attempts*\n\n"
            "Please try again later.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return ConversationState.MAIN_MENU

    # Verify the token
    is_valid = await user_service.verify_2fa_token(user.id, code)

    if is_valid:
        # Check if this is for a protected action or initial setup
        pending_action = context.user_data.get("pending_2fa_action")

        if pending_action:
            # This is verification for a protected action (withdraw, export_key)
            context.user_data["2fa_verified"] = True
            context.user_data.pop("2fa_verification_attempts", None)

            # Execute the pending action automatically
            if pending_action == "withdraw":
                # Import and call confirm_withdraw handler
                from bot.handlers.wallet import confirm_withdraw

                # Create a fake callback query since we're coming from a message
                # We'll need to re-show the confirmation with a button
                keyboard = [[
                    InlineKeyboardButton("✅ Confirm Withdrawal", callback_data="withdraw_confirm"),
                    InlineKeyboardButton("❌ Cancel", callback_data="menu_main"),
                ]]

                amount = context.user_data.get("withdraw_amount", 0)
                to_address = context.user_data.get("withdraw_address", "")

                await update.message.reply_text(
                    "✅ *2FA Verified*\n\n"
                    f"💵 Amount: `${amount:.2f}` USDC\n"
                    f"📤 To: `{to_address[:10]}...{to_address[-6:]}`\n\n"
                    "Click Confirm to complete withdrawal:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
                return ConversationState.CONFIRM_WITHDRAW

            elif pending_action == "export_key":
                # Import and call export handler
                from bot.handlers.settings import handle_settings_callback

                # Re-show the confirmation button
                keyboard = [[
                    InlineKeyboardButton("⚠️ Yes, Show Private Key", callback_data="settings_export_confirm"),
                    InlineKeyboardButton("❌ Cancel", callback_data="menu_settings"),
                ]]

                await update.message.reply_text(
                    "✅ *2FA Verified*\n\n"
                    "Click below to view your private key:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
                return ConversationState.SETTINGS_EXPORT_KEY

            else:
                return ConversationState.MAIN_MENU

        else:
            # This is initial 2FA setup verification
            # Enable 2FA in settings
            await user_service.update_user_setting(user.id, "two_factor_enabled", True)

            # Clear temporary data
            context.user_data.pop("2fa_setup_secret", None)
            context.user_data.pop("2fa_verification_attempts", None)

            # Show success message
            keyboard = [[InlineKeyboardButton("🔙 Back to Settings", callback_data="menu_settings")]]
            await update.message.reply_text(
                "✅ *2FA Enabled Successfully!*\n\n"
                "Your account is now protected with Two-Factor Authentication.\n\n"
                "You'll need your authenticator app for:\n"
                "• Withdrawals\n"
                "• Private key export",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
            return ConversationState.MAIN_MENU

    else:
        # Invalid code - increment attempts
        attempts += 1
        context.user_data["2fa_verification_attempts"] = attempts
        remaining = 3 - attempts

        await update.message.reply_text(
            "❌ *Invalid Code*\n\n"
            "Please try again. Make sure you're entering the current code from your app.\n\n"
            f"Attempts remaining: {remaining}/3",
            parse_mode="Markdown",
        )
        return ConversationState.TWO_FA_VERIFY


async def require_2fa_verification(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action: str,
) -> bool:
    """
    Check if 2FA verification is required and prompt if needed.

    Args:
        update: Telegram update
        context: Bot context
        action: Action being performed (e.g., "withdraw", "export_key")

    Returns:
        True if user can proceed (no 2FA or already verified)
        False if 2FA verification is required
    """
    user = update.effective_user
    user_service = context.bot_data["user_service"]

    # Check if user has 2FA enabled
    if not await user_service.is_2fa_enabled(user.id):
        return True

    # Check if already verified in this session
    if context.user_data.get("2fa_verified"):
        return True

    # Need to verify - show prompt
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "🔐 *2FA Verification Required*\n\n"
            f"Enter your 6-digit 2FA code to confirm {action}:",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "🔐 *2FA Verification Required*\n\n"
            f"Enter your 6-digit 2FA code to confirm {action}:",
            parse_mode="Markdown",
        )

    # Store pending action
    context.user_data["pending_2fa_action"] = action
    context.user_data["2fa_verification_attempts"] = 0

    return False


async def verify_2fa_for_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Verify 2FA code for a pending action.

    Returns:
        True if verification successful
        False if verification failed
    """
    user = update.effective_user
    user_service = context.bot_data["user_service"]

    # Get the code from the message
    code = update.message.text.strip()

    # Validate format
    if not code.isdigit() or len(code) != 6:
        await update.message.reply_text(
            "❌ *Invalid Format*\n\n"
            "Please enter a 6-digit code (numbers only).",
            parse_mode="Markdown",
        )
        return False

    # Check verification attempts
    attempts = context.user_data.get("2fa_verification_attempts", 0)
    if attempts >= 3:
        context.user_data.pop("pending_2fa_action", None)
        context.user_data.pop("2fa_verification_attempts", None)

        await update.message.reply_text(
            "❌ *Too Many Failed Attempts*\n\n"
            "Action cancelled for security. Please try again.",
            parse_mode="Markdown",
        )
        return False

    # Verify the token
    is_valid = await user_service.verify_2fa_token(user.id, code)

    if is_valid:
        # Mark as verified for this session
        context.user_data["2fa_verified"] = True
        context.user_data.pop("2fa_verification_attempts", None)
        return True
    else:
        # Invalid code - increment attempts
        attempts += 1
        context.user_data["2fa_verification_attempts"] = attempts
        remaining = 3 - attempts

        await update.message.reply_text(
            "❌ *Invalid Code*\n\n"
            "Please try again.\n\n"
            f"Attempts remaining: {remaining}/3",
            parse_mode="Markdown",
        )
        return False

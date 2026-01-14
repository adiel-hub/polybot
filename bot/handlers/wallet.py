"""Wallet handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.keyboards.main_menu import get_wallet_keyboard
from bot.keyboards.common import get_back_keyboard

logger = logging.getLogger(__name__)


async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show wallet information and deposit address."""
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    wallet = await user_service.get_wallet(user.id)

    if not wallet:
        text = "❌ Wallet not found. Please /start to create one."
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationState.MAIN_MENU

    text = (
        f"💳 *Polygon Deposit*\n\n"
        f"🔑 Your Wallet Address:\n"
        f"`{wallet.address}`\n\n"
        f"⚠️ *Please ensure you are:*\n"
        f"├ 🔗 On Polygon network\n"
        f"├ 💵 Sending USDC or USDC.e\n"
        f"└ ✅ Double-checking the address\n\n"
        f"📍 Minimum: $1.00\n\n"
        f"⛽ We sponsor gas fees, so you DO NOT need POL in your wallet.\n\n"
        f"🔔 _We'll notify you when your funds arrive._"
    )

    keyboard = get_wallet_keyboard()

    if query:
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    return ConversationState.WALLET_MENU


async def handle_wallet_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle wallet menu callbacks."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    user = update.effective_user
    user_service = context.bot_data["user_service"]

    if callback_data == "wallet_qr":
        # Generate QR code for wallet address
        wallet = await user_service.get_wallet(user.id)
        if wallet:
            try:
                import qrcode
                from io import BytesIO

                # Generate QR code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(wallet.address)
                qr.make(fit=True)

                # Create image
                img = qr.make_image(fill_color="black", back_color="white")

                # Convert to bytes
                bio = BytesIO()
                img.save(bio, 'PNG')
                bio.seek(0)

                # Send QR code image
                await query.message.reply_photo(
                    photo=bio,
                    caption=(
                        f"📱 *Deposit QR Code*\n\n"
                        f"🔑 Address:\n`{wallet.address}`\n\n"
                        f"⚠️ Send USDC on Polygon network only"
                    ),
                    parse_mode="Markdown",
                )

                await query.answer("QR code generated!")

            except Exception as e:
                logger.error(f"QR code generation failed: {e}")
                await query.edit_message_text(
                    f"📱 *Deposit Address*\n\n"
                    f"🔑 Your Wallet Address:\n`{wallet.address}`\n\n"
                    f"⚠️ QR code generation failed. Please copy the address manually.",
                    reply_markup=get_back_keyboard("menu_wallet"),
                    parse_mode="Markdown",
                )

        return ConversationState.WALLET_MENU

    elif callback_data == "wallet_withdraw":
        wallet = await user_service.get_wallet(user.id)
        if not wallet or wallet.usdc_balance < 1.0:
            await query.edit_message_text(
                "💸 *Withdraw*\n\n"
                "⚠️ Insufficient balance. Minimum withdrawal is $1.00.",
                reply_markup=get_back_keyboard("menu_wallet"),
                parse_mode="Markdown",
            )
            return ConversationState.WALLET_MENU

        context.user_data["withdraw_balance"] = wallet.usdc_balance

        await query.edit_message_text(
            f"💸 *Withdraw USDC*\n\n"
            f"💰 Available balance: `${wallet.usdc_balance:.2f}`\n"
            f"📍 Minimum withdrawal: $1.00\n\n"
            f"✏️ Enter the amount to withdraw:",
            reply_markup=get_back_keyboard("menu_wallet"),
            parse_mode="Markdown",
        )

        return ConversationState.WITHDRAW_AMOUNT

    return ConversationState.WALLET_MENU


async def handle_withdraw_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle withdrawal amount input."""
    try:
        amount = float(update.message.text.strip())
        balance = context.user_data.get("withdraw_balance", 0)

        if amount < 1.0:
            await update.message.reply_text(
                "⚠️ Minimum withdrawal is $1.00. Please enter a larger amount."
            )
            return ConversationState.WITHDRAW_AMOUNT

        if amount > balance:
            await update.message.reply_text(
                f"⚠️ Insufficient balance. You have `${balance:.2f}` available."
            )
            return ConversationState.WITHDRAW_AMOUNT

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a number."
        )
        return ConversationState.WITHDRAW_AMOUNT

    context.user_data["withdraw_amount"] = amount

    await update.message.reply_text(
        f"💸 *Withdraw ${amount:.2f}*\n\n"
        f"🔑 Enter the destination wallet address:\n"
        f"_(Must be a valid Polygon address)_",
        reply_markup=get_back_keyboard("menu_wallet"),
        parse_mode="Markdown",
    )

    return ConversationState.WITHDRAW_ADDRESS


async def handle_withdraw_address(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle withdrawal address input."""
    from core.wallet import WalletGenerator

    address = update.message.text.strip()

    if not WalletGenerator.is_valid_address(address):
        await update.message.reply_text(
            "❌ Invalid address. Please enter a valid Polygon wallet address."
        )
        return ConversationState.WITHDRAW_ADDRESS

    context.user_data["withdraw_address"] = address
    amount = context.user_data.get("withdraw_amount", 0)

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data="withdraw_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu_wallet"),
        ]
    ]

    await update.message.reply_text(
        f"📋 *Confirm Withdrawal*\n\n"
        f"💵 Amount: `${amount:.2f}` USDC\n"
        f"📤 To: `{address[:10]}...{address[-6:]}`\n\n"
        f"🔗 Network: Polygon\n\n"
        f"✅ Confirm this withdrawal?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.CONFIRM_WITHDRAW


async def confirm_withdraw(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Execute withdrawal."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    amount = context.user_data.get("withdraw_amount", 0)
    to_address = context.user_data.get("withdraw_address", "")

    # Check if 2FA verification is required
    if await user_service.is_2fa_enabled(user.id):
        if not context.user_data.get("2fa_verified"):
            # Require 2FA verification
            await query.edit_message_text(
                "🔐 *2FA Verification Required*\n\n"
                "Enter your 6-digit 2FA code to confirm withdrawal:",
                parse_mode="Markdown",
            )
            context.user_data["pending_2fa_action"] = "withdraw"
            context.user_data["2fa_verification_attempts"] = 0
            return ConversationState.TWO_FA_VERIFY

    await query.edit_message_text("⏳ Processing withdrawal...")

    try:
        # Get user's wallet and private key
        db_user = await user_service.get_user(user.id)
        if not db_user:
            raise Exception("User not found")

        private_key = await user_service.get_private_key(db_user.id)
        if not private_key:
            raise Exception("Wallet not found")

        # Get wallet address
        wallet = await user_service.get_wallet(user.id)
        if not wallet:
            raise Exception("Wallet not found")

        # Execute sponsored withdrawal (gas sponsor pays fees)
        from core.blockchain import WithdrawalManager

        withdrawal_mgr = WithdrawalManager()

        # First attempt withdrawal
        result = await withdrawal_mgr.withdraw_sponsored(
            user_address=wallet.address,
            to_address=to_address,
            amount=amount,
        )

        # If approval needed, approve first then retry
        if not result.success and "approval" in result.error.lower():
            logger.info("Gas sponsor not approved, approving now...")
            await query.edit_message_text("⏳ Setting up withdrawal permissions...")

            # First, check if user has POL for approval transaction
            user_pol = withdrawal_mgr.w3.eth.get_balance(wallet.address) / 1e18
            if user_pol < 0.01:
                logger.info(f"User needs POL for approval, sponsoring gas")
                gas_result = await withdrawal_mgr.sponsor_gas(wallet.address, 0.02)
                if gas_result.success and gas_result.tx_hash != "already_approved":
                    # Wait for gas to arrive
                    import asyncio
                    for i in range(30):
                        await asyncio.sleep(2)
                        try:
                            receipt = withdrawal_mgr.w3.eth.get_transaction_receipt(gas_result.tx_hash)
                            if receipt and receipt.status == 1:
                                logger.info(f"Gas transfer confirmed")
                                break
                        except Exception:
                            pass

            # Approve gas sponsor
            approval_result = await withdrawal_mgr.approve_gas_sponsor(private_key)

            if not approval_result.success:
                await query.edit_message_text(
                    f"❌ *Withdrawal Setup Failed*\n\n"
                    f"⚠️ Could not approve gas sponsor: {approval_result.error}\n\n"
                    f"🔄 Please try again later.",
                    parse_mode="Markdown",
                )
                return ConversationState.MAIN_MENU

            # Wait for approval to be mined if it's a new approval
            if approval_result.tx_hash != "already_approved":
                logger.info(f"Waiting for approval tx: {approval_result.tx_hash}")
                import asyncio
                for i in range(30):
                    await asyncio.sleep(2)
                    try:
                        receipt = withdrawal_mgr.w3.eth.get_transaction_receipt(approval_result.tx_hash)
                        if receipt and receipt.status == 1:
                            logger.info(f"Approval confirmed in block {receipt.blockNumber}")
                            break
                    except Exception:
                        pass

            # Retry withdrawal
            await query.edit_message_text("⏳ Processing withdrawal...")
            result = await withdrawal_mgr.withdraw_sponsored(
                user_address=wallet.address,
                to_address=to_address,
                amount=amount,
            )

        if result.success:
            # Update balance in database
            wallet = await user_service.get_wallet(user.id)
            if wallet:
                from database.repositories import WalletRepository
                wallet_repo = WalletRepository(context.bot_data["db"])
                await wallet_repo.subtract_balance(wallet.id, amount)

            await query.edit_message_text(
                f"✅ *Withdrawal Submitted!*\n\n"
                f"💵 Amount: `${amount:.2f}` USDC\n"
                f"📤 To: `{to_address[:10]}...{to_address[-6:]}`\n"
                f"🔗 TX: `{result.tx_hash[:16]}...`\n\n"
                f"⏳ Your withdrawal is being processed.",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                f"❌ *Withdrawal Failed*\n\n"
                f"⚠️ Error: {result.error}\n\n"
                f"🔄 Please try again later.",
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Withdrawal failed: {e}")
        logger.info("💡 Withdrawal error handler version: 2.0 (with curly brace escaping)")
        # Provide user-friendly error message
        error_str = str(e)
        if "insufficient funds for gas" in error_str.lower():
            user_message = (
                "❌ Withdrawal failed: Insufficient gas funds\n\n"
                "The system's gas sponsor wallet needs to be refilled with POL.\n"
                "Please contact support or try again later."
            )
        else:
            # Escape error message to prevent Markdown parsing issues
            error_msg = (error_str
                .replace('*', '\\*')
                .replace('_', '\\_')
                .replace('[', '\\[')
                .replace(']', '\\]')
                .replace('`', '\\`')
                .replace('{', '\\{')
                .replace('}', '\\}'))
            user_message = f"❌ Withdrawal failed:\n{error_msg}\n\n🔄 Please try again."

        # Don't use parse_mode to avoid any parsing issues
        try:
            await query.edit_message_text(user_message, parse_mode=None)
        except Exception as edit_error:
            logger.error(f"Failed to edit message: {edit_error}")
            # Fallback: send new message instead
            await query.message.reply_text(user_message, parse_mode=None)

    # Clear withdrawal data and 2FA verification
    for key in ["withdraw_amount", "withdraw_address", "withdraw_balance", "2fa_verified", "pending_2fa_action"]:
        context.user_data.pop(key, None)

    from bot.handlers.menu import show_main_menu
    return await show_main_menu(update, context, send_new=True)

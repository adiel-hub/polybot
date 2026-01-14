"""Main menu handlers."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.keyboards.main_menu import get_main_menu_keyboard

logger = logging.getLogger(__name__)


async def show_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    send_new: bool = False,
) -> int:
    """Display main menu with user stats."""
    user = update.effective_user
    user_service = context.bot_data["user_service"]

    # Get user stats
    stats = await user_service.get_user_stats(user.id)

    menu_text = (
        f"🤖 *Welcome to PolyBot*\n\n"
        f"⚡ The fastest and most secure bot for trading on Polymarket\n\n"
        f"📊 Positions Value: `${stats['portfolio_value']:.2f}`\n"
        f"💵 Tradable Balance: `${stats['usdc_balance']:.2f}`\n"
        f"📋 Open Limit Orders: `${stats['open_orders']:.2f}`\n"
        f"💰 Net Worth: `${stats['net_worth']:.2f}`\n\n"
    )

    if stats['usdc_balance'] == 0 and stats['portfolio_value'] == 0:
        menu_text += "💳 Go to Wallet to make a deposit"

    keyboard = get_main_menu_keyboard()

    # Determine how to send the message
    if send_new:
        # Send as new message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=menu_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    elif update.callback_query:
        from telegram.error import BadRequest
        try:
            await update.callback_query.edit_message_text(
                menu_text,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
        except BadRequest as e:
            # Handle cases where message can't be edited (e.g., after sending photo)
            if "message is not modified" in str(e).lower():
                pass
            elif "no text in the message to edit" in str(e).lower():
                # Message is a photo/media, delete it and send new text message
                try:
                    await update.callback_query.message.delete()
                except:
                    pass
                await context.bot.send_message(
                    chat_id=update.callback_query.message.chat_id,
                    text=menu_text,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
            else:
                raise
    else:
        await update.message.reply_text(
            menu_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    return ConversationState.MAIN_MENU


async def handle_menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle main menu button callbacks."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "menu_main":
        return await show_main_menu(update, context)

    elif callback_data == "menu_refresh":
        return await show_main_menu(update, context)

    elif callback_data == "menu_portfolio":
        from bot.handlers.portfolio import show_portfolio
        return await show_portfolio(update, context)

    elif callback_data == "menu_orders":
        from bot.handlers.orders import show_orders
        return await show_orders(update, context)

    elif callback_data == "menu_wallet":
        from bot.handlers.wallet import show_wallet
        return await show_wallet(update, context)

    elif callback_data == "menu_browse":
        from bot.handlers.markets import show_browse_menu
        return await show_browse_menu(update, context)

    elif callback_data == "menu_copy":
        from bot.handlers.copy_trading import show_copy_trading
        return await show_copy_trading(update, context)

    elif callback_data == "menu_stoploss":
        from bot.handlers.stop_loss import show_stop_loss_menu
        return await show_stop_loss_menu(update, context)

    elif callback_data == "menu_settings":
        from bot.handlers.settings import show_settings_menu
        return await show_settings_menu(update, context)

    elif callback_data == "menu_support":
        await query.edit_message_text(
            "💬 *Support*\n\n"
            "Need help? Contact us at:\n"
            "📧 support@polybot.trade\n\n"
            "👥 Or join our Telegram community!",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )
        return ConversationState.MAIN_MENU

    elif callback_data == "menu_group":
        await query.edit_message_text(
            "👥 *Add to Group*\n\n"
            "Add PolyBot to your Telegram group to earn rewards!\n\n"
            "🔜 Group features coming soon.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )
        return ConversationState.MAIN_MENU

    elif callback_data == "menu_rewards":
        from bot.handlers.referral import show_referral_menu
        return await show_referral_menu(update, context)

    elif callback_data == "noop":
        # Do nothing for noop buttons
        return ConversationState.MAIN_MENU

    return ConversationState.MAIN_MENU

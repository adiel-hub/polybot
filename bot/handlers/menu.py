"""Main menu handlers."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.keyboards.main_menu import get_main_menu_keyboard
from utils.short_id import generate_short_id

logger = logging.getLogger(__name__)


async def show_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    send_new: bool = False,
) -> int:
    """Display main menu with user stats."""
    user = update.effective_user
    user_service = context.bot_data["user_service"]

    logger.info(f"=== SHOW_MAIN_MENU === User {user.id}")
    logger.info(f"send_new parameter: {send_new}")
    logger.info(f"user_data keys: {list(context.user_data.keys())}")

    # Check for pending event deep link (multi-outcome events)
    pending_event_id = context.user_data.pop("pending_event_id", None)
    if pending_event_id:
        logger.info(f"✅ FOUND pending_event_id! Redirecting to event options: {pending_event_id}")
        from bot.handlers.markets import show_event_options_from_deeplink
        return await show_event_options_from_deeplink(update, context, pending_event_id)

    # Check for pending market deep link
    pending_market_id = context.user_data.pop("pending_market_id", None)
    logger.info(f"pending_market_id from user_data: {pending_market_id}")

    if pending_market_id:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        logger.info(f"✅ FOUND pending_market_id! Processing deep link for market: {pending_market_id}")
        logger.info(f"Condition ID length: {len(pending_market_id)}")

        # Check if it's a short ID (8 chars) and resolve it
        actual_condition_id = pending_market_id
        if len(pending_market_id) == 8:
            # Try to resolve from cache first
            short_id_map = context.bot_data.get("market_short_ids", {})
            resolved_id = short_id_map.get(pending_market_id)

            if resolved_id:
                logger.info(f"✅ Resolved short ID {pending_market_id} from cache: {resolved_id[:20]}...")
                actual_condition_id = resolved_id
            else:
                # Not in cache - need to search for market by generating all possible short IDs
                # This happens when user clicks a deep link before browsing markets
                logger.info(f"⚠️ Short ID {pending_market_id} not in cache, will try API lookup")
                # For now, try it as-is - the API will return None if not found
                actual_condition_id = pending_market_id

        # Load market and show trade page
        market_service = context.bot_data["market_service"]
        logger.info(f"Calling market_service.get_market_detail({actual_condition_id[:20] if len(actual_condition_id) > 20 else actual_condition_id}...)")

        try:
            market = await market_service.get_market_detail(actual_condition_id)
            logger.info(f"API call completed. Market result: {market is not None}")
        except Exception as e:
            logger.error(f"❌ Error fetching market: {e}", exc_info=True)
            market = None

        if market:
            logger.info(f"✅ Market FOUND! Question: {market.question}")
            # Store market in context
            context.user_data["current_market"] = {
                "condition_id": market.condition_id,
                "question": market.question,
                "yes_token_id": market.yes_token_id,
                "no_token_id": market.no_token_id,
                "yes_price": market.yes_price,
                "no_price": market.no_price,
            }

            # Format market details
            yes_cents = market.yes_price * 100
            no_cents = market.no_price * 100

            # Format expiration date
            from datetime import datetime
            expiry_text = ""
            is_expired = False
            if market.end_date:
                try:
                    # Parse ISO format date
                    end_dt = datetime.fromisoformat(market.end_date.replace('Z', '+00:00'))
                    expiry_text = end_dt.strftime("%b %d, %Y at %I:%M %p UTC")
                    # Check if expired
                    is_expired = datetime.now(end_dt.tzinfo) > end_dt
                except:
                    expiry_text = market.end_date

            text = (
                f"📊 *{market.question}*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
            )

            # Add expiration warning if expired
            if is_expired:
                text += f"⚠️ *This market has expired and is closed for trading*\n\n"

            text += (
                f"💰 *Current Prices*\n"
                f"├ ✅ Yes: `{yes_cents:.1f}c`\n"
                f"└ ❌ No: `{no_cents:.1f}c`\n\n"
                f"📈 *Market Stats*\n"
                f"├ 📊 Volume (All): `${market.total_volume:,.2f}`\n"
                f"├ 📊 Volume (24h): `${market.volume_24h:,.2f}`\n"
                f"└ 💧 Liquidity: `${market.liquidity:,.2f}`\n"
            )

            if expiry_text:
                status = "Expired" if is_expired else "Expires"
                text += f"\n⏰ *Timeline*\n└ 📅 {status}: {expiry_text}\n"

            # Add Polymarket link if slug exists
            if market.slug:
                polymarket_url = f"https://polymarket.com/market/{market.slug}"
                text += f"\n[View on Polymarket]({polymarket_url})\n"

            keyboard = [
                [
                    InlineKeyboardButton("📈 Buy Yes", callback_data="trade_buy_yes"),
                    InlineKeyboardButton("📉 Buy No", callback_data="trade_buy_no"),
                ],
                [
                    InlineKeyboardButton("📊 Limit Yes", callback_data="trade_limit_yes"),
                    InlineKeyboardButton("📊 Limit No", callback_data="trade_limit_no"),
                ],
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data=f"market_{pending_market_id[:20]}"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
                ],
            ]

            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

            return ConversationState.MARKET_DETAIL
        else:
            # Market not found
            logger.warning(f"❌ Market NOT FOUND for condition_id: {pending_market_id}")
            await update.message.reply_text(
                f"❌ Market not found.\n\n"
                f"The market may have been removed or the link is invalid.\n\n"
                f"Use /start to access the main menu.",
                parse_mode="Markdown",
            )
            return ConversationState.MAIN_MENU

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

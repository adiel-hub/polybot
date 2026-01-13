"""Trading flow handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.keyboards.common import get_cancel_keyboard
from bot.handlers.menu import show_main_menu

logger = logging.getLogger(__name__)


async def handle_trade_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle trade type selection."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    market = context.user_data.get("current_market")

    if not market:
        await query.edit_message_text(
            "❌ Market data not found. Please select a market again.",
        )
        return ConversationState.BROWSE_RESULTS

    # Parse trade type: trade_buy_yes, trade_limit_no, etc.
    parts = callback_data.replace("trade_", "").split("_")
    order_type = parts[0]  # "buy" (market) or "limit"
    outcome = parts[1].upper()  # "YES" or "NO"

    context.user_data["order_type"] = "MARKET" if order_type == "buy" else "LIMIT"
    context.user_data["outcome"] = outcome
    context.user_data["token_id"] = market["yes_token_id"] if outcome == "YES" else market["no_token_id"]

    if order_type == "buy":
        # Market order - ask for USD amount
        text = (
            f"📈 *Market Order - {outcome}*\n\n"
            f"💹 Market: {market['question'][:50]}...\n\n"
            f"💵 Enter the USD amount you want to spend:\n"
            f"_(e.g., 10 or 25.50)_"
        )
        await query.edit_message_text(
            text,
            reply_markup=get_cancel_keyboard(f"market_{market['condition_id'][:20]}"),
            parse_mode="Markdown",
        )
        return ConversationState.ENTER_AMOUNT
    else:
        # Limit order - ask for price first
        current_price = market["yes_price"] if outcome == "YES" else market["no_price"]
        text = (
            f"📊 *Limit Order - {outcome}*\n\n"
            f"💹 Market: {market['question'][:50]}...\n"
            f"💰 Current price: `{current_price * 100:.1f}c`\n\n"
            f"✏️ Enter your limit price (1-99 cents):\n"
            f"_(e.g., 45 or 67)_"
        )
        await query.edit_message_text(
            text,
            reply_markup=get_cancel_keyboard(f"market_{market['condition_id'][:20]}"),
            parse_mode="Markdown",
        )
        return ConversationState.ENTER_PRICE


async def handle_price_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle limit price input."""
    try:
        price_cents = float(update.message.text.strip())
        if price_cents < 1 or price_cents > 99:
            raise ValueError("Price out of range")
        price = price_cents / 100  # Convert to decimal
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid price. Please enter a number between 1 and 99 cents."
        )
        return ConversationState.ENTER_PRICE

    context.user_data["limit_price"] = price

    market = context.user_data.get("current_market", {})
    outcome = context.user_data.get("outcome", "YES")

    text = (
        f"📊 *Limit Order - {outcome}*\n\n"
        f"💹 Market: {market.get('question', '')[:50]}...\n"
        f"💰 Limit Price: `{price_cents:.0f}c`\n\n"
        f"📝 Enter the number of shares to buy:\n"
        f"_(e.g., 100 or 50.5)_"
    )

    await update.message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(f"market_{market.get('condition_id', '')[:20]}"),
        parse_mode="Markdown",
    )

    return ConversationState.ENTER_AMOUNT


async def handle_amount_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle amount input for orders."""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if amount > 100000:
            raise ValueError("Amount too large")
    except ValueError as e:
        await update.message.reply_text(
            f"❌ Invalid amount: {e}. Please enter a positive number."
        )
        return ConversationState.ENTER_AMOUNT

    context.user_data["amount"] = amount

    # Show confirmation
    market = context.user_data.get("current_market", {})
    order_type = context.user_data.get("order_type", "MARKET")
    outcome = context.user_data.get("outcome", "YES")
    limit_price = context.user_data.get("limit_price")

    if order_type == "MARKET":
        # Estimate shares for market order
        current_price = market.get("yes_price", 0.5) if outcome == "YES" else market.get("no_price", 0.5)
        estimated_shares = amount / current_price if current_price > 0 else 0

        text = (
            f"📋 *Confirm Order*\n\n"
            f"💹 Market: {market.get('question', '')[:50]}...\n"
            f"📈 Type: Market Order\n"
            f"🎯 Outcome: {outcome}\n"
            f"💵 Amount: `${amount:.2f}`\n"
            f"📊 Est. Shares: `{estimated_shares:.2f}`\n"
            f"💰 Est. Price: `{current_price * 100:.1f}c`\n\n"
            f"✅ Confirm this order?"
        )
    else:
        text = (
            f"📋 *Confirm Order*\n\n"
            f"💹 Market: {market.get('question', '')[:50]}...\n"
            f"📊 Type: Limit Order\n"
            f"🎯 Outcome: {outcome}\n"
            f"📈 Shares: `{amount:.2f}`\n"
            f"💰 Limit Price: `{limit_price * 100:.0f}c`\n"
            f"💵 Total Cost: `${amount * limit_price:.2f}`\n\n"
            f"✅ Confirm this order?"
        )

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data="order_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"market_{market.get('condition_id', '')[:20]}"),
        ]
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.CONFIRM_ORDER


async def confirm_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Execute the confirmed order."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    trading_service = context.bot_data["trading_service"]
    user_service = context.bot_data["user_service"]

    # Get user
    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found. Please /start again.")
        return ConversationState.MAIN_MENU

    # Get order details from context
    market = context.user_data.get("current_market", {})
    order_type = context.user_data.get("order_type", "MARKET")
    outcome = context.user_data.get("outcome", "YES")
    amount = context.user_data.get("amount", 0)
    limit_price = context.user_data.get("limit_price")
    token_id = context.user_data.get("token_id")

    await query.edit_message_text("⏳ Submitting order...")

    try:
        result = await trading_service.place_order(
            user_id=db_user.id,
            market_condition_id=market.get("condition_id", ""),
            token_id=token_id,
            outcome=outcome,
            order_type=order_type,
            amount=amount,
            price=limit_price,
            market_question=market.get("question"),
        )

        if result.get("success"):
            await query.edit_message_text(
                f"✅ *Order Submitted!*\n\n"
                f"🔗 Order ID: `{result.get('order_id', 'N/A')}`\n"
                f"📊 Status: {result.get('status', 'PENDING')}\n\n"
                f"🎉 Your order has been placed successfully.",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                f"❌ *Order Failed*\n\n"
                f"⚠️ Error: {result.get('error', 'Unknown error')}\n\n"
                f"🔄 Please try again.",
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Order execution failed: {e}")
        await query.edit_message_text(
            f"❌ Order failed: {str(e)}\n\n🔄 Please try again."
        )

    # Clear order data from context
    for key in ["order_type", "outcome", "amount", "limit_price", "token_id", "current_market"]:
        context.user_data.pop(key, None)

    return await show_main_menu(update, context, send_new=True)


async def handle_sell_position(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle sell position callback from portfolio."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    position_id = int(callback_data.replace("sell_position_", ""))

    user = update.effective_user
    user_service = context.bot_data["user_service"]
    trading_service = context.bot_data["trading_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Get position from database
    from database.repositories import PositionRepository
    position_repo = PositionRepository(context.bot_data["db"])

    position = await position_repo.get_by_id(position_id)

    if not position or position.user_id != db_user.id:
        await query.edit_message_text("❌ Position not found.")
        return ConversationState.PORTFOLIO_VIEW

    # Store position data for selling
    context.user_data["sell_position"] = {
        "id": position.id,
        "token_id": position.token_id,
        "size": position.size,
        "outcome": position.outcome,
        "market_question": position.market_question,
        "market_condition_id": position.market_condition_id,
        "average_entry_price": position.average_entry_price,
        "current_price": position.current_price or position.average_entry_price,
    }

    current_value = position.size * (position.current_price or position.average_entry_price)
    pnl = position.unrealized_pnl or 0
    pnl_sign = "+" if pnl >= 0 else ""
    pnl_emoji = "📈" if pnl >= 0 else "📉"

    text = (
        f"📉 *Sell Position*\n\n"
        f"💹 Market: {position.market_question[:50] if position.market_question else 'Unknown'}...\n"
        f"🎯 Outcome: {position.outcome}\n"
        f"📊 Shares: `{position.size:.2f}`\n"
        f"💰 Entry Price: `{position.average_entry_price * 100:.1f}c`\n"
        f"💵 Current Value: `${current_value:.2f}`\n"
        f"{pnl_emoji} P&L: `{pnl_sign}${pnl:.2f}`\n\n"
        f"✏️ Enter the number of shares to sell:\n"
        f"_(Enter `all` or `max` to sell entire position)_"
    )

    keyboard = [
        [
            InlineKeyboardButton("📊 Sell 25%", callback_data="sell_pct_25"),
            InlineKeyboardButton("📊 Sell 50%", callback_data="sell_pct_50"),
        ],
        [
            InlineKeyboardButton("📊 Sell 75%", callback_data="sell_pct_75"),
            InlineKeyboardButton("📊 Sell 100%", callback_data="sell_pct_100"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="menu_portfolio"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
        ],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.SELL_AMOUNT


async def handle_sell_percentage(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle sell percentage button callbacks."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    percentage = int(callback_data.replace("sell_pct_", ""))

    sell_position = context.user_data.get("sell_position")
    if not sell_position:
        await query.edit_message_text("❌ Position data not found.")
        return ConversationState.PORTFOLIO_VIEW

    shares_to_sell = sell_position["size"] * (percentage / 100)
    context.user_data["sell_shares"] = shares_to_sell

    return await show_sell_confirmation(update, context)


async def handle_sell_amount_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle manual sell amount input."""
    sell_position = context.user_data.get("sell_position")
    if not sell_position:
        await update.message.reply_text("❌ Position data not found.")
        return ConversationState.PORTFOLIO_VIEW

    text = update.message.text.strip().lower()

    # Handle 'all' or 'max' keywords
    if text in ["all", "max"]:
        shares_to_sell = sell_position["size"]
    else:
        try:
            shares_to_sell = float(text)
            if shares_to_sell <= 0:
                raise ValueError("Amount must be positive")
            if shares_to_sell > sell_position["size"]:
                await update.message.reply_text(
                    f"❌ You only have `{sell_position['size']:.2f}` shares. "
                    f"Please enter a smaller amount.",
                    parse_mode="Markdown",
                )
                return ConversationState.SELL_AMOUNT
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid amount. Please enter a number or 'all'."
            )
            return ConversationState.SELL_AMOUNT

    context.user_data["sell_shares"] = shares_to_sell

    return await show_sell_confirmation(update, context, is_message=True)


async def show_sell_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    is_message: bool = False,
) -> int:
    """Show sell order confirmation."""
    sell_position = context.user_data.get("sell_position")
    shares_to_sell = context.user_data.get("sell_shares", 0)

    current_price = sell_position["current_price"]
    estimated_value = shares_to_sell * current_price

    text = (
        f"📋 *Confirm Sell Order*\n\n"
        f"💹 Market: {sell_position['market_question'][:50] if sell_position.get('market_question') else 'Unknown'}...\n"
        f"🎯 Outcome: {sell_position['outcome']}\n"
        f"📊 Shares to Sell: `{shares_to_sell:.2f}`\n"
        f"💰 Est. Price: `{current_price * 100:.1f}c`\n"
        f"💵 Est. Value: `${estimated_value:.2f}`\n\n"
        f"✅ Confirm this sell order?"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm Sell", callback_data="sell_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu_portfolio"),
        ]
    ]

    if is_message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    return ConversationState.CONFIRM_SELL


async def confirm_sell(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Execute the confirmed sell order."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    trading_service = context.bot_data["trading_service"]
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    sell_position = context.user_data.get("sell_position")
    shares_to_sell = context.user_data.get("sell_shares", 0)

    if not sell_position:
        await query.edit_message_text("❌ Position data not found.")
        return ConversationState.PORTFOLIO_VIEW

    await query.edit_message_text("⏳ Submitting sell order...")

    try:
        result = await trading_service.sell_position(
            user_id=db_user.id,
            position_id=sell_position["id"],
            token_id=sell_position["token_id"],
            size=shares_to_sell,
            market_condition_id=sell_position["market_condition_id"],
        )

        if result.get("success"):
            await query.edit_message_text(
                f"✅ *Sell Order Submitted!*\n\n"
                f"🔗 Order ID: `{result.get('order_id', 'N/A')}`\n"
                f"📊 Shares Sold: `{shares_to_sell:.2f}`\n"
                f"💵 Est. Value: `${shares_to_sell * sell_position['current_price']:.2f}`\n\n"
                f"🎉 Your sell order has been placed successfully.",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                f"❌ *Sell Order Failed*\n\n"
                f"⚠️ Error: {result.get('error', 'Unknown error')}\n\n"
                f"🔄 Please try again.",
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Sell order failed: {e}")
        await query.edit_message_text(
            f"❌ Sell order failed: {str(e)}\n\n🔄 Please try again."
        )

    # Clear sell data from context
    context.user_data.pop("sell_position", None)
    context.user_data.pop("sell_shares", None)

    return await show_main_menu(update, context, send_new=True)

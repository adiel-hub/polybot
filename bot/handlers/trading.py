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

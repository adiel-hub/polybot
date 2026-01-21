"""Trading flow handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.keyboards.common import get_cancel_keyboard
from bot.handlers.menu import show_main_menu
from config.constants import MIN_ORDER_AMOUNT
from core.images import generate_trade_card

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

    order_type = context.user_data.get("order_type", "MARKET")
    limit_price = context.user_data.get("limit_price")

    # Calculate actual order value for minimum check
    if order_type == "MARKET":
        order_value = amount
    else:
        # Limit order: amount is shares, total cost = shares * price
        order_value = amount * limit_price if limit_price else amount

    # Validate minimum order amount (Polymarket requires $1 minimum)
    if order_value < MIN_ORDER_AMOUNT:
        await update.message.reply_text(
            f"❌ Minimum order value is `${MIN_ORDER_AMOUNT:.0f}`.\n"
            f"Your order: `${order_value:.2f}`\n\n"
            f"Please enter a larger amount.",
            parse_mode="Markdown",
        )
        return ConversationState.ENTER_AMOUNT

    context.user_data["amount"] = amount

    # Get user settings to check trading mode
    user_service = context.bot_data["user_service"]
    db_user = await user_service.get_user(update.effective_user.id)
    if not db_user:
        await update.message.reply_text("❌ User not found. Please /start again.")
        return ConversationState.MAIN_MENU

    settings = await user_service.get_user_settings(db_user.id)
    trading_mode = settings.get("trading_mode", "standard")
    threshold = settings.get("fast_mode_threshold", 100.0)

    # Validate trading mode and default to standard (safest) if invalid
    valid_modes = ["standard", "fast", "ludicrous"]
    if trading_mode not in valid_modes:
        trading_mode = "standard"

    # Determine if confirmation is needed based on trading mode
    needs_confirmation = (
        trading_mode == "standard" or
        (trading_mode == "fast" and amount > threshold)
    )

    # If no confirmation needed, execute immediately
    if not needs_confirmation:
        # Determine mode message
        if trading_mode == "ludicrous":
            mode_message = "🚀 *Ludicrous Mode* - Order fired immediately!"
        else:  # fast mode, below threshold
            mode_message = f"⚡ *Fast Mode* - Order under `${threshold:.0f}`, executing instantly!"

        # Execute order immediately
        return await _execute_order_internal(update, context, db_user, mode_message)

    # Show confirmation (standard mode or fast mode above threshold)
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


async def _execute_order_internal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_user,
    mode_message: str = None,
) -> int:
    """Internal helper to execute order placement.

    Args:
        update: Telegram update object
        context: Bot context
        db_user: Database user object
        mode_message: Optional message to prepend (e.g., "🚀 Ludicrous Mode - Order fired immediately!")

    Returns:
        ConversationState for next state
    """
    trading_service = context.bot_data["trading_service"]

    # Get order details from context
    market = context.user_data.get("current_market", {})
    order_type = context.user_data.get("order_type", "MARKET")
    outcome = context.user_data.get("outcome", "YES")
    amount = context.user_data.get("amount", 0)
    limit_price = context.user_data.get("limit_price")
    token_id = context.user_data.get("token_id")

    # Determine if we're editing a message or sending new one
    if update.callback_query:
        message_handler = update.callback_query.edit_message_text
    else:
        message_handler = update.message.reply_text

    await message_handler("⏳ Submitting order...")

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
            # Build enhanced order confirmation message
            message_lines = []

            # Add mode message if provided
            if mode_message:
                message_lines.append(mode_message)
                message_lines.append("")

            message_lines.extend([
                "✅ *Trade Executed Successfully!*",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "📋 *Order Details*",
                "",
            ])

            # Market info
            market_question = market.get("question", "Unknown Market")
            if len(market_question) > 60:
                market_question = market_question[:60] + "..."
            message_lines.append(f"🎯 Market: _{market_question}_")
            message_lines.append(f"📊 Outcome: *{outcome}*")
            message_lines.append("")

            # Order details
            message_lines.append(f"💵 Amount: `${amount:.2f}` USDC")
            message_lines.append(f"📈 Type: {order_type.upper()}")

            if limit_price:
                message_lines.append(f"💰 Price: `${limit_price:.4f}`")

            message_lines.append("")
            message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Transaction info
            message_lines.append("🔗 *Transaction Info*")
            message_lines.append("")
            message_lines.append(f"📝 Order ID: `{result.get('order_id', 'N/A')[:16]}...`")
            message_lines.append(f"✨ Status: *{result.get('status', 'PENDING')}*")

            # If filled, show position details
            if result.get('status') == 'FILLED':
                message_lines.append("")
                message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                message_lines.append("📊 *Position Created*")
                message_lines.append("")

                # Try to get position details
                try:
                    from database.repositories.position_repo import PositionRepository
                    position_repo = PositionRepository(context.bot_data["db"])
                    positions = await position_repo.get_user_positions(db_user.id)

                    # Find the position for this market and outcome
                    matching_position = None
                    for pos in positions:
                        if pos.token_id == token_id and pos.outcome == outcome:
                            matching_position = pos
                            break

                    if matching_position:
                        shares = matching_position.size
                        entry_price = matching_position.average_entry_price
                        position_value = shares * entry_price

                        message_lines.append(f"📦 Shares: `{shares:.4f}`")
                        message_lines.append(f"💰 Entry Price: `${entry_price:.4f}`")
                        message_lines.append(f"💎 Position Value: `${position_value:.2f}`")

                        # Calculate potential profit (to $1.00 payout)
                        if entry_price > 0:
                            potential_profit = (1.0 - entry_price) * shares
                            roi = (potential_profit / amount) * 100 if amount > 0 else 0
                            message_lines.append(f"🎯 Max Profit: `${potential_profit:.2f}` ({roi:.1f}%)")
                    else:
                        message_lines.append(f"📦 Shares: `{amount / limit_price if limit_price else 'calculating...'}`")
                except Exception as e:
                    logger.error(f"Failed to fetch position details: {e}")
                    pass

                message_lines.append("")
                message_lines.append("🎉 _Your position is now active!_")
            else:
                message_lines.append("")
                message_lines.append("⏳ _Order pending execution..._")

            message_lines.append("")
            message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Get updated balance
            try:
                user_service = context.bot_data["user_service"]
                wallet = await user_service.get_wallet_by_user_id(db_user.id)
                from core.blockchain.balance import get_balance_service
                balance_service = get_balance_service()
                new_balance = balance_service.get_balance(wallet.address)
                message_lines.append(f"💰 Remaining Balance: `${new_balance:.2f}` USDC")
            except Exception as e:
                logger.error(f"Failed to get balance: {e}")

            # Ensure message doesn't exceed Telegram's limit (4096 chars)
            full_message = "\n".join(message_lines)
            if len(full_message) > 4000:  # Leave some buffer
                # Truncate message at a reasonable point
                full_message = full_message[:4000] + "\n\n... (message truncated)"

            await message_handler(
                full_message,
                parse_mode="Markdown",
            )
        else:
            error_msg = result.get('error', 'Unknown error')
            # Truncate error if too long
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            error_lines = []

            # Add mode message if provided
            if mode_message:
                error_lines.append(mode_message)
                error_lines.append("")

            error_lines.extend([
                f"❌ *Order Failed*\n",
                f"⚠️ Error: {error_msg}\n",
                f"🔄 Please try again."
            ])

            text = "\n".join(error_lines)

            # Add deposit button if insufficient balance
            if "Insufficient balance" in error_msg:
                keyboard = [
                    [InlineKeyboardButton("💳 Deposit Funds", callback_data="wallet_deposit")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                reply_markup = None

            await message_handler(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Order execution failed: {e}")

        # Store order details for retry
        context.user_data["retry_order"] = {
            "market": market,
            "order_type": order_type,
            "outcome": outcome,
            "amount": amount,
            "limit_price": limit_price,
            "token_id": token_id,
        }

        keyboard = [
            [InlineKeyboardButton("🔄 Retry Order", callback_data="order_retry")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]

        # Truncate error message if too long (Telegram limit is 4096 characters)
        error_str = str(e)
        if len(error_str) > 200:
            error_str = error_str[:200] + "..."

        await message_handler(
            f"❌ Order failed: {error_str}\n\n"
            f"This may be a temporary network issue.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return ConversationState.MAIN_MENU

    # Clear order data from context
    for key in ["order_type", "outcome", "amount", "limit_price", "token_id", "current_market"]:
        context.user_data.pop(key, None)

    return await show_main_menu(update, context, send_new=True)


async def confirm_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Execute the confirmed order (callback from confirmation button)."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    # Get user
    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found. Please /start again.")
        return ConversationState.MAIN_MENU

    # Execute order using internal helper
    return await _execute_order_internal(update, context, db_user)


async def handle_order_retry(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Retry a failed order with the same parameters."""
    query = update.callback_query
    await query.answer("Retrying order...")

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    # Get retry order data
    retry_order = context.user_data.get("retry_order")
    if not retry_order:
        await query.edit_message_text(
            "❌ Order data not found. Please start a new order."
        )
        return ConversationState.MAIN_MENU

    # Get user
    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found. Please /start again.")
        return ConversationState.MAIN_MENU

    # Restore order data to context
    context.user_data["current_market"] = retry_order["market"]
    context.user_data["order_type"] = retry_order["order_type"]
    context.user_data["outcome"] = retry_order["outcome"]
    context.user_data["amount"] = retry_order["amount"]
    context.user_data["limit_price"] = retry_order["limit_price"]
    context.user_data["token_id"] = retry_order["token_id"]

    # Clear retry data
    context.user_data.pop("retry_order", None)

    # Execute order
    return await _execute_order_internal(update, context, db_user, "🔄 *Retrying Order...*")


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
            # Build enhanced sell confirmation message
            message_lines = [
                "✅ *Position Closed Successfully!*",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "📋 *Sale Details*",
                "",
            ]

            # Market info
            market_question = sell_position.get('market_question', 'Unknown Market')
            if len(market_question) > 60:
                market_question = market_question[:60] + "..."
            message_lines.append(f"🎯 Market: _{market_question}_")
            message_lines.append(f"📊 Outcome: *{sell_position['outcome']}*")
            message_lines.append("")

            # Sale details
            sale_price = sell_position['current_price']
            sale_value = shares_to_sell * sale_price

            message_lines.append(f"📦 Shares Sold: `{shares_to_sell:.4f}`")
            message_lines.append(f"💰 Sale Price: `${sale_price:.4f}`")
            message_lines.append(f"💵 Total Value: `${sale_value:.2f}` USDC")

            message_lines.append("")
            message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # P&L calculation
            try:
                entry_price = sell_position.get('average_entry_price', 0)
                if entry_price > 0:
                    cost_basis = shares_to_sell * entry_price
                    profit_loss = sale_value - cost_basis
                    roi = (profit_loss / cost_basis) * 100 if cost_basis > 0 else 0

                    message_lines.append("💹 *Profit/Loss*")
                    message_lines.append("")
                    message_lines.append(f"📥 Entry Price: `${entry_price:.4f}`")
                    message_lines.append(f"📤 Exit Price: `${sale_price:.4f}`")
                    message_lines.append(f"💰 Cost Basis: `${cost_basis:.2f}`")

                    if profit_loss >= 0:
                        message_lines.append(f"🟢 P&L: `+${profit_loss:.2f}` (+{roi:.1f}%)")
                    else:
                        message_lines.append(f"🔴 P&L: `-${abs(profit_loss):.2f}` ({roi:.1f}%)")

                    message_lines.append("")
                    message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            except Exception as e:
                logger.error(f"Failed to calculate P&L: {e}")

            # Transaction info
            message_lines.append("🔗 *Transaction Info*")
            message_lines.append("")
            message_lines.append(f"📝 Order ID: `{result.get('order_id', 'N/A')[:16]}...`")
            message_lines.append(f"✨ Status: *{result.get('status', 'FILLED')}*")

            message_lines.append("")
            message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Get updated balance
            try:
                user_service = context.bot_data["user_service"]
                wallet = await user_service.get_wallet_by_user_id(db_user.id)
                from core.blockchain.balance import get_balance_service
                balance_service = get_balance_service()
                new_balance = balance_service.get_balance(wallet.address)
                message_lines.append(f"💰 New Balance: `${new_balance:.2f}` USDC")
                message_lines.append("")
                message_lines.append("🎉 _Funds added to your wallet!_")
            except Exception as e:
                logger.error(f"Failed to get balance: {e}")
                message_lines.append("")
                message_lines.append("🎉 _Your position has been closed!_")

            # Calculate trade data
            entry_price = sell_position.get('average_entry_price', 0)
            cost_basis = shares_to_sell * entry_price if entry_price > 0 else 0
            profit_loss = sale_value - cost_basis if cost_basis > 0 else 0
            roi = (profit_loss / cost_basis) * 100 if cost_basis > 0 else 0

            # Store trade data for potential re-sharing
            context.user_data["last_trade"] = {
                "market_question": sell_position.get('market_question', 'Unknown Market'),
                "outcome": sell_position['outcome'],
                "entry_price": entry_price,
                "exit_price": sale_price,
                "size": shares_to_sell,
                "pnl": profit_loss,
                "pnl_percentage": roi,
            }

            # Send text summary first
            await query.edit_message_text(
                "\n".join(message_lines),
                parse_mode="Markdown",
            )

            # Automatically generate and send trade card image
            try:
                referral_service = context.bot_data["referral_service"]

                # Get user's referral code
                stats = await referral_service.get_referral_stats(db_user.id)
                referral_code = stats.get('referral_code', '')

                if not referral_code:
                    await user_service.generate_referral_code_for_user(db_user.id)
                    stats = await referral_service.get_referral_stats(db_user.id)
                    referral_code = stats.get('referral_code', 'POLYBOT')

                # Get referral link
                bot_username = context.bot.username
                referral_link = await referral_service.get_referral_link(db_user.id, bot_username)

                # Generate trade card image
                image_buffer = generate_trade_card(
                    market_question=sell_position.get('market_question', 'Unknown Market'),
                    outcome=sell_position['outcome'],
                    entry_price=entry_price,
                    exit_price=sale_price,
                    size=shares_to_sell,
                    pnl=profit_loss,
                    pnl_percentage=roi,
                    referral_code=referral_code,
                    referral_link=referral_link,
                )

                # Build caption
                pnl_sign = "+" if profit_loss >= 0 else ""
                pnl_emoji = "🟢" if profit_loss >= 0 else "🔴"

                # Escape underscores in referral link for Markdown
                safe_referral_link = referral_link.replace("_", "\\_")
                caption = (
                    f"{pnl_emoji} *Trade Closed!*\n\n"
                    f"📊 ROI: `{pnl_sign}{roi:.2f}%`\n"
                    f"💰 P&L: `{pnl_sign}${profit_loss:.2f}`\n\n"
                    f"🔗 Trade on Polymarket with PolyBot!\n"
                    f"👉 {safe_referral_link}\n\n"
                    f"_Forward this image to share your trade!_"
                )

                # Send trade card image with share instructions
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=image_buffer,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📤 Share Again", callback_data="share_trade")],
                        [InlineKeyboardButton("📊 Portfolio", callback_data="menu_portfolio")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
                    ]),
                )

                logger.info(f"Trade card auto-generated for user {user.id}")

            except Exception as e:
                logger.error(f"Failed to auto-generate trade card: {e}")
                # If image generation fails, just show navigation buttons
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="📸 _Trade card generation failed. You can try again later._",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📸 Try Again", callback_data="share_trade")],
                        [InlineKeyboardButton("📊 Portfolio", callback_data="menu_portfolio")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
                    ]),
                )
        else:
            error_msg = result.get('error', 'Unknown error')

            # Check if it's an allowance error (needs CTF approval for selling)
            if "not enough balance / allowance" in error_msg.lower() or "allowance" in error_msg.lower():
                text = (
                    f"❌ *Trading Permission Required*\n\n"
                    f"⚠️ You need to approve the exchange to transfer your position shares.\n\n"
                    f"💡 This is a one-time approval for selling positions.\n\n"
                    f"📝 Please contact support to enable selling, or try depositing POL for gas fees and try again."
                )
                keyboard = [
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            elif "Insufficient balance" in error_msg:
                # Insufficient balance for gas fees
                text = (
                    f"❌ *Sell Order Failed*\n\n"
                    f"⚠️ Error: {error_msg}\n\n"
                    f"🔄 Please deposit funds and try again."
                )
                keyboard = [
                    [InlineKeyboardButton("💳 Deposit Funds", callback_data="wallet_deposit")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                # Generic error
                text = (
                    f"❌ *Sell Order Failed*\n\n"
                    f"⚠️ Error: {error_msg}\n\n"
                    f"🔄 Please try again."
                )
                reply_markup = None

            await query.edit_message_text(
                text,
                reply_markup=reply_markup,
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

    return ConversationState.MAIN_MENU


async def handle_share_trade(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Generate and send a shareable trade card image."""
    query = update.callback_query
    await query.answer("Generating trade card...")

    user = update.effective_user
    user_service = context.bot_data["user_service"]
    referral_service = context.bot_data["referral_service"]

    # Get last trade data
    last_trade = context.user_data.get("last_trade")
    if not last_trade:
        await query.edit_message_text(
            "❌ Trade data not found. Please close a position first."
        )
        return ConversationState.MAIN_MENU

    # Get user's referral code
    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Get referral stats to get code
    stats = await referral_service.get_referral_stats(db_user.id)
    referral_code = stats.get('referral_code', '')

    if not referral_code:
        await user_service.generate_referral_code_for_user(db_user.id)
        stats = await referral_service.get_referral_stats(db_user.id)
        referral_code = stats.get('referral_code', 'POLYBOT')

    # Get referral link
    bot_username = context.bot.username
    referral_link = await referral_service.get_referral_link(db_user.id, bot_username)

    try:
        # Generate trade card image
        image_buffer = generate_trade_card(
            market_question=last_trade["market_question"],
            outcome=last_trade["outcome"],
            entry_price=last_trade["entry_price"],
            exit_price=last_trade["exit_price"],
            size=last_trade["size"],
            pnl=last_trade["pnl"],
            pnl_percentage=last_trade["pnl_percentage"],
            referral_code=referral_code,
            referral_link=referral_link,
        )

        # Build caption
        pnl_sign = "+" if last_trade["pnl"] >= 0 else ""
        pnl_emoji = "🟢" if last_trade["pnl"] >= 0 else "🔴"

        caption = (
            f"{pnl_emoji} *Trade Closed!*\n\n"
            f"📊 ROI: `{pnl_sign}{last_trade['pnl_percentage']:.2f}%`\n"
            f"💰 P&L: `{pnl_sign}${last_trade['pnl']:.2f}`\n\n"
            f"🔗 Trade on Polymarket with PolyBot!\n"
            f"👉 {referral_link}"
        )

        # Send image
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=image_buffer,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Portfolio", callback_data="menu_portfolio")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]),
        )

        # Delete the original message
        try:
            await query.message.delete()
        except Exception:
            pass

        logger.info(f"Trade card generated for user {user.id}")

    except Exception as e:
        logger.error(f"Failed to generate trade card: {e}")
        await query.edit_message_text(
            f"❌ Failed to generate trade card: {str(e)}\n\n"
            f"Your referral link: `{referral_link}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]),
        )

    return ConversationState.MAIN_MENU

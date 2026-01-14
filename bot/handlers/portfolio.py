"""Portfolio handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.keyboards.common import get_back_keyboard

logger = logging.getLogger(__name__)


async def show_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show user's portfolio and positions."""
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]
    trading_service = context.bot_data["trading_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        text = "❌ User not found. Please /start to register."
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationState.MAIN_MENU

    # Get positions
    positions = await trading_service.get_positions(db_user.id)
    wallet = await user_service.get_wallet(user.id)

    # Get real-time balance from blockchain
    from core.blockchain.balance import get_balance_service
    balance_service = get_balance_service()
    balance = balance_service.get_balance(wallet.address) if wallet else 0

    if not positions:
        text = (
            "📊 *Portfolio*\n\n"
            "📭 You don't have any positions yet.\n\n"
            f"💵 Tradable Balance: `${balance:.2f}`\n\n"
            "💹 Browse markets to start trading!"
        )

        keyboard = [
            [InlineKeyboardButton("💹 Browse Markets", callback_data="menu_browse")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]

        if query:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        return ConversationState.PORTFOLIO_VIEW

    # Calculate totals
    total_value = sum(p.current_value for p in positions)
    total_pnl = sum(p.unrealized_pnl or 0 for p in positions)
    total_invested = sum(p.size * p.average_entry_price for p in positions)
    pnl_sign = "+" if total_pnl >= 0 else ""
    pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
    total_roi = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    # Build portfolio summary message
    message_lines = [
        "📊 *Your Portfolio*",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "💼 *Summary*",
        "",
        f"💰 Total Value: `${total_value:.2f}`",
        f"💵 Cash Balance: `${balance:.2f}`",
        f"📊 Invested: `${total_invested:.2f}`",
        "",
        f"{pnl_emoji} Unrealized P&L: `{pnl_sign}${total_pnl:.2f}` ({pnl_sign}{total_roi:.1f}%)",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🎯 *Active Positions* ({len(positions)})",
        "",
        "_Click a position to manage_",
        "",
    ]

    text = "\n".join(message_lines)

    keyboard = []

    # Create buttons for each position
    for i, position in enumerate(positions[:10], 1):  # Show max 10 positions
        # Format position
        pnl = position.unrealized_pnl or 0
        pnl_pct = position.pnl_percentage
        pos_emoji = "🟢" if pnl >= 0 else "🔴"

        question = position.market_question or "Unknown Market"
        short_question = question[:25] + "..." if len(question) > 25 else question

        # Create button label with position info
        button_label = f"{pos_emoji} {short_question}"

        # Add button for position details
        keyboard.append([
            InlineKeyboardButton(
                button_label,
                callback_data=f"position_{position.id}",
            )
        ])

    # Navigation buttons
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="menu_portfolio"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    if query:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    return ConversationState.PORTFOLIO_VIEW


async def handle_position_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show detailed position view with management options."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    position_id = int(callback_data.replace("position_", ""))

    user = update.effective_user
    user_service = context.bot_data["user_service"]
    trading_service = context.bot_data["trading_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Get position details
    from database.repositories.position_repo import PositionRepository
    position_repo = PositionRepository(context.bot_data["db"])
    position = await position_repo.get_by_id(position_id)

    if not position or position.user_id != db_user.id:
        await query.edit_message_text("❌ Position not found.")
        return await show_portfolio(update, context)

    # Store position ID for further actions
    context.user_data["selected_position_id"] = position_id

    # Build detailed position view
    message_lines = [
        "📊 *Position Details*",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🎯 *Market*",
        "",
    ]

    market_question = position.market_question or "Unknown Market"
    if len(market_question) > 60:
        market_question = market_question[:60] + "..."
    message_lines.append(f"_{market_question}_")
    message_lines.append(f"🎲 Outcome: *{position.outcome}*")
    message_lines.append("")

    # Position info
    message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    message_lines.append("📦 *Position Info*")
    message_lines.append("")
    message_lines.append(f"📊 Shares: `{position.size:.4f}`")
    message_lines.append(f"💰 Entry Price: `${position.average_entry_price:.4f}` ({position.average_entry_price * 100:.1f}c)")

    # Handle None current price
    if position.current_price is not None:
        message_lines.append(f"📈 Current Price: `${position.current_price:.4f}` ({position.current_price * 100:.1f}c)")
    else:
        message_lines.append(f"📈 Current Price: _Updating..._")

    message_lines.append("")

    # Value calculation
    cost_basis = position.size * position.average_entry_price
    current_value = position.current_value if position.current_value is not None else cost_basis
    message_lines.append(f"💵 Cost Basis: `${cost_basis:.2f}`")
    message_lines.append(f"💎 Current Value: `${current_value:.2f}`")

    # P&L
    message_lines.append("")
    message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    message_lines.append("💹 *Profit/Loss*")
    message_lines.append("")

    pnl = position.unrealized_pnl or 0
    pnl_pct = position.pnl_percentage if position.pnl_percentage is not None else 0
    pnl_sign = "+" if pnl >= 0 else ""

    if position.current_price is not None:
        if pnl >= 0:
            message_lines.append(f"🟢 Unrealized P&L: `{pnl_sign}${pnl:.2f}` ({pnl_sign}{pnl_pct:.1f}%)")
        else:
            message_lines.append(f"🔴 Unrealized P&L: `${pnl:.2f}` ({pnl_pct:.1f}%)")
    else:
        message_lines.append(f"⏳ P&L: _Calculating..._")

    # Max profit (to $1.00)
    if position.average_entry_price < 1.0:
        max_profit = (1.0 - position.average_entry_price) * position.size
        max_roi = (max_profit / cost_basis) * 100 if cost_basis > 0 else 0
        message_lines.append(f"🎯 Max Profit: `${max_profit:.2f}` ({max_roi:.1f}%)")

    # Stop loss info
    message_lines.append("")
    message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    message_lines.append("🛡️ *Risk Management*")
    message_lines.append("")

    # Check if stop loss exists
    from database.repositories.stop_loss_repo import StopLossRepository
    stop_loss_repo = StopLossRepository(context.bot_data["db"])
    active_stop_loss = await stop_loss_repo.get_active_for_position(position_id)

    if active_stop_loss:
        message_lines.append(f"✅ Stop Loss: `${active_stop_loss.trigger_price:.4f}` ({active_stop_loss.trigger_price * 100:.1f}c)")
        message_lines.append(f"📉 Will sell if price drops to trigger")
    else:
        message_lines.append("❌ No stop loss set")
        message_lines.append("_Set a stop loss to protect your position_")

    # Timestamps
    message_lines.append("")
    message_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    message_lines.append("🕒 *Timestamps*")
    message_lines.append("")

    from datetime import datetime
    created_time = datetime.fromisoformat(position.created_at).strftime("%Y-%m-%d %H:%M:%S")
    message_lines.append(f"📅 Opened: {created_time}")

    if position.updated_at:
        updated_time = datetime.fromisoformat(position.updated_at).strftime("%Y-%m-%d %H:%M:%S")
        message_lines.append(f"🔄 Updated: {updated_time}")

    text = "\n".join(message_lines)

    # Action buttons
    keyboard = []

    # Sell options
    keyboard.append([
        InlineKeyboardButton("📉 Sell All", callback_data=f"sell_position_{position_id}"),
        InlineKeyboardButton("📊 Sell Partial", callback_data=f"sell_partial_{position_id}"),
    ])

    # Stop loss management
    if active_stop_loss:
        keyboard.append([
            InlineKeyboardButton("✏️ Edit Stop Loss", callback_data=f"stoploss_{position_id}"),
            InlineKeyboardButton("🗑️ Remove Stop Loss", callback_data=f"remove_stoploss_{active_stop_loss.id}"),
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("🛡️ Set Stop Loss", callback_data=f"stoploss_{position_id}"),
        ])

    # Navigation
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Portfolio", callback_data="menu_portfolio"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.PORTFOLIO_VIEW

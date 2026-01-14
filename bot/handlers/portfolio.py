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
    pnl_sign = "+" if total_pnl >= 0 else ""
    pnl_emoji = "📈" if total_pnl >= 0 else "📉"

    text = (
        f"📊 *Portfolio*\n\n"
        f"💰 Total Value: `${total_value:.2f}`\n"
        f"{pnl_emoji} Unrealized P&L: `{pnl_sign}${total_pnl:.2f}`\n"
        f"💵 Tradable Balance: `${balance:.2f}`\n\n"
        f"🎯 *Positions ({len(positions)})*\n\n"
    )

    keyboard = []

    for i, position in enumerate(positions[:10], 1):  # Show max 10 positions
        # Format position
        pnl = position.unrealized_pnl or 0
        pnl_pct = position.pnl_percentage
        pnl_prefix = "+" if pnl >= 0 else ""
        pos_emoji = "📈" if pnl >= 0 else "📉"

        question = position.market_question or "Unknown Market"
        text += (
            f"{i}. {question[:40]}{'...' if len(question) > 40 else ''}\n"
            f"   🎯 {position.outcome}: `{position.size:.2f}` @ `{position.average_entry_price*100:.0f}c`\n"
            f"   {pos_emoji} P&L: `{pnl_prefix}${pnl:.2f}` ({pnl_prefix}{pnl_pct:.1f}%)\n\n"
        )

        # Add button to manage position
        keyboard.append([
            InlineKeyboardButton(
                f"⚙️ {i}. Manage",
                callback_data=f"position_{position.id}",
            )
        ])

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
    """Handle position management."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    position_id = int(callback_data.replace("position_", ""))

    # Store position ID for further actions
    context.user_data["selected_position_id"] = position_id

    keyboard = [
        [
            InlineKeyboardButton("📉 Sell", callback_data=f"sell_position_{position_id}"),
            InlineKeyboardButton("🛡️ Set Stop Loss", callback_data=f"stoploss_{position_id}"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="menu_portfolio"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
        ],
    ]

    await query.edit_message_text(
        "⚙️ *Position Actions*\n\n"
        "What would you like to do with this position?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.PORTFOLIO_VIEW

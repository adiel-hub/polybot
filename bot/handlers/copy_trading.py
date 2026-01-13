"""Copy trading handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.keyboards.common import get_back_keyboard

logger = logging.getLogger(__name__)


async def show_copy_trading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show copy trading menu."""
    query = update.callback_query
    if query:
        await query.answer()

    text = (
        "👥 *Copy Trading*\n\n"
        "🤖 Automatically copy trades from successful traders!\n\n"
        "📋 *How it works:*\n"
        "1️⃣ Browse top traders by performance\n"
        "2️⃣ Select a trader to follow\n"
        "3️⃣ Set your allocation percentage\n"
        "4️⃣ Trades are automatically mirrored\n\n"
        "👇 Select an option:"
    )

    keyboard = [
        [InlineKeyboardButton("🏆 Browse Top Traders", callback_data="copy_browse")],
        [InlineKeyboardButton("📋 My Subscriptions", callback_data="copy_subscriptions")],
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

    return ConversationState.COPY_TRADING_MENU


async def browse_top_traders(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show list of top traders."""
    query = update.callback_query
    await query.answer()

    # Placeholder - in production, fetch from API
    traders = [
        {"address": "0x1234...5678", "name": "CryptoWhale", "pnl": 15234.50, "win_rate": 67},
        {"address": "0xabcd...ef01", "name": "PredictionPro", "pnl": 8921.30, "win_rate": 72},
        {"address": "0x9876...5432", "name": "MarketMaster", "pnl": 5432.10, "win_rate": 58},
    ]

    text = "🏆 *Top Traders*\n\n"

    keyboard = []
    for i, trader in enumerate(traders, 1):
        pnl_emoji = "📈" if trader['pnl'] >= 0 else "📉"
        text += (
            f"{i}. 👤 {trader['name']}\n"
            f"   {pnl_emoji} P&L: `${trader['pnl']:,.2f}` │ 🎯 Win Rate: `{trader['win_rate']}%`\n\n"
        )
        keyboard.append([
            InlineKeyboardButton(
                f"👥 {i}. Copy {trader['name']}",
                callback_data=f"copy_trader_{trader['address'][:10]}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="menu_copy"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.SELECT_TRADER


async def show_subscriptions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show user's copy trading subscriptions."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Get subscriptions from database
    from database.repositories import CopyTraderRepository
    copy_repo = CopyTraderRepository(context.bot_data["db"])

    subscriptions = await copy_repo.get_user_subscriptions(db_user.id)

    if not subscriptions:
        text = (
            "📋 *My Subscriptions*\n\n"
            "📭 You're not following any traders yet.\n\n"
            "🏆 Browse top traders to start copy trading!"
        )

        keyboard = [
            [InlineKeyboardButton("🏆 Browse Traders", callback_data="copy_browse")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return ConversationState.COPY_TRADING_MENU

    text = f"📋 *My Subscriptions ({len(subscriptions)})*\n\n"

    keyboard = []
    for i, sub in enumerate(subscriptions, 1):
        status_emoji = "✅" if sub.is_active else "⏸️"
        status = "Active" if sub.is_active else "Paused"
        pnl_emoji = "📈" if sub.total_pnl >= 0 else "📉"
        text += (
            f"{i}. 👤 {sub.display_name}\n"
            f"   📊 Allocation: `{sub.allocation}%`\n"
            f"   📋 Trades Copied: `{sub.total_trades_copied}`\n"
            f"   {pnl_emoji} P&L: `${sub.total_pnl:.2f}`\n"
            f"   {status_emoji} Status: {status}\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"{'⏸️' if sub.is_active else '▶️'} {i}. {'Pause' if sub.is_active else 'Resume'}",
                callback_data=f"copy_toggle_{sub.id}",
            ),
            InlineKeyboardButton(
                "🗑️ Remove",
                callback_data=f"copy_remove_{sub.id}",
            ),
        ])

    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="menu_copy"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.COPY_TRADING_MENU


async def handle_copy_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle copy trading callbacks."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "copy_browse":
        return await browse_top_traders(update, context)

    elif callback_data == "copy_subscriptions":
        return await show_subscriptions(update, context)

    elif callback_data.startswith("copy_trader_"):
        # Start subscription flow
        trader_address = callback_data.replace("copy_trader_", "")
        context.user_data["copy_trader_address"] = trader_address

        await query.edit_message_text(
            f"👥 *Copy Trader*\n\n"
            f"👤 Trader: `{trader_address}`\n\n"
            f"📊 Enter allocation percentage (1-50):\n"
            f"💡 _This is the percentage of your balance used for each trade._",
            reply_markup=get_back_keyboard("copy_browse"),
            parse_mode="Markdown",
        )

        return ConversationState.ENTER_ALLOCATION

    elif callback_data.startswith("copy_toggle_"):
        # Toggle subscription
        sub_id = int(callback_data.replace("copy_toggle_", ""))
        from database.repositories import CopyTraderRepository
        copy_repo = CopyTraderRepository(context.bot_data["db"])

        sub = await copy_repo.get_by_id(sub_id)
        if sub:
            if sub.is_active:
                await copy_repo.deactivate(sub_id)
            else:
                # Reactivate would need a method
                pass

        return await show_subscriptions(update, context)

    elif callback_data.startswith("copy_remove_"):
        sub_id = int(callback_data.replace("copy_remove_", ""))
        from database.repositories import CopyTraderRepository
        copy_repo = CopyTraderRepository(context.bot_data["db"])
        await copy_repo.deactivate(sub_id)

        await query.edit_message_text("✅ Subscription removed.")
        return await show_subscriptions(update, context)

    return ConversationState.COPY_TRADING_MENU


async def handle_allocation_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle allocation percentage input."""
    try:
        allocation = float(update.message.text.strip())
        if allocation < 1 or allocation > 50:
            raise ValueError("Allocation out of range")
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid allocation. Please enter a number between 1 and 50."
        )
        return ConversationState.ENTER_ALLOCATION

    context.user_data["copy_allocation"] = allocation
    trader_address = context.user_data.get("copy_trader_address", "")

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data="copy_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu_copy"),
        ]
    ]

    await update.message.reply_text(
        f"📋 *Confirm Copy Trading*\n\n"
        f"👤 Trader: `{trader_address}`\n"
        f"📊 Allocation: `{allocation}%`\n\n"
        f"🤖 You will automatically copy trades from this trader.\n\n"
        f"✅ Confirm?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.CONFIRM_COPY


async def confirm_copy(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Confirm copy trading subscription."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    trader_address = context.user_data.get("copy_trader_address", "")
    allocation = context.user_data.get("copy_allocation", 10)

    from database.repositories import CopyTraderRepository
    copy_repo = CopyTraderRepository(context.bot_data["db"])

    try:
        await copy_repo.create(
            user_id=db_user.id,
            trader_address=trader_address,
            allocation=allocation,
        )

        await query.edit_message_text(
            "✅ *Success!*\n\n"
            f"👥 You are now copying trades from `{trader_address}`.\n"
            f"📊 Allocation: `{allocation}%`\n\n"
            f"🔔 You'll be notified when trades are copied.",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Failed to create copy subscription: {e}")
        await query.edit_message_text(
            f"❌ Failed to create subscription: {str(e)}"
        )

    # Clear context
    context.user_data.pop("copy_trader_address", None)
    context.user_data.pop("copy_allocation", None)

    from bot.handlers.menu import show_main_menu
    return await show_main_menu(update, context, send_new=True)

"""Stop loss handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.keyboards.common import get_back_keyboard
from database.repositories import StopLossRepository, PositionRepository

logger = logging.getLogger(__name__)


async def show_stop_loss_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show stop loss management menu."""
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]
    db = context.bot_data["db"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        text = "User not found. Please /start to register."
        if query:
            await query.edit_message_text(text)
        return ConversationState.MAIN_MENU

    # Get positions and stop losses
    position_repo = PositionRepository(db)
    stop_loss_repo = StopLossRepository(db)

    positions = await position_repo.get_user_positions(db_user.id)
    stop_losses = await stop_loss_repo.get_user_stop_losses(db_user.id)

    if not positions:
        text = (
            "*Stop Loss*\n\n"
            "You don't have any positions to protect.\n\n"
            "Open positions first, then set stop losses!"
        )
        keyboard = get_back_keyboard("menu_main")

        if query:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        return ConversationState.MAIN_MENU

    text = f"*Stop Loss Orders*\n\nActive Stop Losses: {len(stop_losses)}\n\n"

    # Show existing stop losses
    if stop_losses:
        text += "*Current Stop Losses:*\n"
        for sl in stop_losses:
            position = await position_repo.get_by_id(sl.position_id)
            if position:
                text += (
                    f"- {position.market_question[:30]}...\n"
                    f"  Trigger: {sl.trigger_price * 100:.0f}c | "
                    f"Sell: {sl.sell_percentage}%\n\n"
                )

    text += "\n*Positions without Stop Loss:*\n"

    keyboard = []
    positions_without_sl = [
        p for p in positions
        if not any(sl.position_id == p.id for sl in stop_losses)
    ]

    if positions_without_sl:
        for i, position in enumerate(positions_without_sl[:5], 1):
            text += (
                f"{i}. {position.market_question[:35]}...\n"
                f"   {position.outcome}: {position.size:.2f} shares\n\n"
            )
            keyboard.append([
                InlineKeyboardButton(
                    f"{i}. Add Stop Loss",
                    callback_data=f"sl_add_{position.id}",
                )
            ])
    else:
        text += "All positions have stop losses!\n"

    keyboard.append([
        InlineKeyboardButton("Main Menu", callback_data="menu_main"),
    ])

    if query:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    return ConversationState.SELECT_POSITION


async def handle_stop_loss_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle stop loss callbacks."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    db = context.bot_data["db"]

    if callback_data.startswith("sl_add_"):
        position_id = int(callback_data.replace("sl_add_", ""))
        context.user_data["sl_position_id"] = position_id

        position_repo = PositionRepository(db)
        position = await position_repo.get_by_id(position_id)

        if not position:
            await query.edit_message_text("Position not found.")
            return ConversationState.MAIN_MENU

        current_price = position.current_price or position.average_entry_price

        await query.edit_message_text(
            f"*Set Stop Loss*\n\n"
            f"Position: {position.market_question[:40]}...\n"
            f"Current Price: {current_price * 100:.0f}c\n"
            f"Entry Price: {position.average_entry_price * 100:.0f}c\n\n"
            f"Enter trigger price (1-99 cents):\n"
            f"Stop loss will execute when price falls to this level.",
            reply_markup=get_back_keyboard("menu_stoploss"),
            parse_mode="Markdown",
        )

        return ConversationState.ENTER_TRIGGER_PRICE

    elif callback_data.startswith("sl_remove_"):
        sl_id = int(callback_data.replace("sl_remove_", ""))
        stop_loss_repo = StopLossRepository(db)
        await stop_loss_repo.deactivate(sl_id)

        await query.edit_message_text("Stop loss removed.")
        return await show_stop_loss_menu(update, context)

    return ConversationState.SELECT_POSITION


async def handle_trigger_price_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle trigger price input."""
    from utils.validators import validate_price

    price = validate_price(update.message.text)

    if price is None:
        await update.message.reply_text(
            "Invalid price. Please enter a number between 1 and 99 cents."
        )
        return ConversationState.ENTER_TRIGGER_PRICE

    context.user_data["sl_trigger_price"] = price

    await update.message.reply_text(
        f"*Trigger Price: {price * 100:.0f}c*\n\n"
        f"Enter percentage of position to sell (1-100):\n"
        f"(e.g., 100 for full position, 50 for half)",
        reply_markup=get_back_keyboard("menu_stoploss"),
        parse_mode="Markdown",
    )

    return ConversationState.ENTER_SELL_PERCENTAGE


async def handle_sell_percentage_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle sell percentage input."""
    from utils.validators import validate_percentage

    percentage = validate_percentage(update.message.text, min_val=1, max_val=100)

    if percentage is None:
        await update.message.reply_text(
            "Invalid percentage. Please enter a number between 1 and 100."
        )
        return ConversationState.ENTER_SELL_PERCENTAGE

    context.user_data["sl_sell_percentage"] = percentage

    position_id = context.user_data.get("sl_position_id")
    trigger_price = context.user_data.get("sl_trigger_price")

    db = context.bot_data["db"]
    position_repo = PositionRepository(db)
    position = await position_repo.get_by_id(position_id)

    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data="sl_confirm"),
            InlineKeyboardButton("Cancel", callback_data="menu_stoploss"),
        ]
    ]

    await update.message.reply_text(
        f"*Confirm Stop Loss*\n\n"
        f"Position: {position.market_question[:40] if position else ''}...\n"
        f"Trigger Price: {trigger_price * 100:.0f}c\n"
        f"Sell: {percentage}% of position\n\n"
        f"Confirm?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.CONFIRM_STOP_LOSS


async def confirm_stop_loss(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Confirm and create stop loss order."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]
    db = context.bot_data["db"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("User not found.")
        return ConversationState.MAIN_MENU

    position_id = context.user_data.get("sl_position_id")
    trigger_price = context.user_data.get("sl_trigger_price")
    sell_percentage = context.user_data.get("sl_sell_percentage", 100)

    position_repo = PositionRepository(db)
    stop_loss_repo = StopLossRepository(db)

    position = await position_repo.get_by_id(position_id)
    if not position:
        await query.edit_message_text("Position not found.")
        return ConversationState.MAIN_MENU

    try:
        await stop_loss_repo.create(
            user_id=db_user.id,
            position_id=position_id,
            token_id=position.token_id,
            trigger_price=trigger_price,
            sell_percentage=sell_percentage,
        )

        await query.edit_message_text(
            f"*Stop Loss Created!*\n\n"
            f"Position: {position.market_question[:40]}...\n"
            f"Trigger: {trigger_price * 100:.0f}c\n"
            f"Sell: {sell_percentage}%\n\n"
            f"You'll be notified when the stop loss triggers.",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Failed to create stop loss: {e}")
        await query.edit_message_text(f"Failed to create stop loss: {str(e)}")

    # Clear context
    for key in ["sl_position_id", "sl_trigger_price", "sl_sell_percentage"]:
        context.user_data.pop(key, None)

    from bot.handlers.menu import show_main_menu
    return await show_main_menu(update, context, send_new=True)

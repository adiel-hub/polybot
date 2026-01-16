"""Price alert handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from database.repositories.price_alert_repo import PriceAlertRepository
from database.models import AlertDirection

logger = logging.getLogger(__name__)

# Maximum alerts per user
MAX_ALERTS_PER_USER = 20


async def show_alerts_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show the alerts management menu."""
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        text = "❌ User not found. Please /start to register."
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationState.MAIN_MENU

    # Get user's alerts
    alert_repo = PriceAlertRepository(context.bot_data["db"])
    alerts = await alert_repo.get_user_alerts(db_user.id, active_only=True)

    if not alerts:
        text = (
            "🔔 *Price Alerts*\n\n"
            "📭 You don't have any active alerts.\n\n"
            "💡 Set price alerts to get notified when a market reaches your target price!\n\n"
            "_To create an alert:_\n"
            "1. Browse to a market\n"
            "2. Click \"🔔 Set Alert\""
        )

        keyboard = [
            [InlineKeyboardButton("💹 Browse Markets", callback_data="menu_browse")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]
    else:
        text = (
            f"🔔 *Price Alerts* ({len(alerts)}/{MAX_ALERTS_PER_USER})\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "_Tap an alert to manage it_\n\n"
        )

        keyboard = []

        for alert in alerts[:10]:  # Show max 10 alerts
            # Truncate market question
            market_q = alert.market_question or "Unknown Market"
            if len(market_q) > 25:
                market_q = market_q[:25] + "..."

            direction_emoji = alert.direction_emoji
            price_cents = alert.target_price_cents

            button_label = f"{direction_emoji} {market_q} @ {price_cents:.0f}c"
            keyboard.append([
                InlineKeyboardButton(button_label, callback_data=f"alert_view_{alert.id}")
            ])

        # Add navigation buttons
        keyboard.append([
            InlineKeyboardButton("💹 Browse Markets", callback_data="menu_browse"),
        ])
        keyboard.append([
            InlineKeyboardButton("🗑️ Delete All", callback_data="alerts_delete_all"),
            InlineKeyboardButton("🔄 Refresh", callback_data="menu_alerts"),
        ])
        keyboard.append([
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

    return ConversationState.ALERTS_MENU


async def view_alert(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """View a specific alert with management options."""
    query = update.callback_query
    await query.answer()

    alert_id = int(query.data.replace("alert_view_", ""))

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Get alert
    alert_repo = PriceAlertRepository(context.bot_data["db"])
    alert = await alert_repo.get_by_id(alert_id)

    if not alert or alert.user_id != db_user.id:
        await query.edit_message_text("❌ Alert not found.")
        return await show_alerts_menu(update, context)

    # Store alert ID for editing
    context.user_data["editing_alert_id"] = alert_id

    # Get current price if available
    ws_service = context.bot_data.get("ws_service")
    current_price = None
    if ws_service:
        current_price = ws_service.get_current_price(alert.token_id)

    # Build alert detail view
    text = (
        f"🔔 *Alert Details*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Market*\n"
        f"_{alert.market_question or 'Unknown'}_\n\n"
        f"🎯 Outcome: *{alert.outcome}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ *Alert Settings*\n\n"
        f"{alert.direction_emoji} Direction: *{alert.direction.value}*\n"
        f"🎯 Target Price: `{alert.target_price_cents:.1f}c`\n"
    )

    if current_price is not None:
        text += f"💰 Current Price: `{current_price * 100:.1f}c`\n"

    if alert.note:
        text += f"\n📝 Note: _{alert.note}_\n"

    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Created: {alert.created_at}\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("✏️ Edit Price", callback_data=f"alert_edit_price_{alert_id}"),
            InlineKeyboardButton("🔄 Flip Direction", callback_data=f"alert_flip_{alert_id}"),
        ],
        [
            InlineKeyboardButton("🗑️ Delete", callback_data=f"alert_delete_{alert_id}"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Alerts", callback_data="menu_alerts"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
        ],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.ALERTS_VIEW


async def flip_alert_direction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Flip the alert direction (ABOVE <-> BELOW)."""
    query = update.callback_query
    await query.answer()

    alert_id = int(query.data.replace("alert_flip_", ""))

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Get and update alert
    alert_repo = PriceAlertRepository(context.bot_data["db"])
    alert = await alert_repo.get_by_id(alert_id)

    if not alert or alert.user_id != db_user.id:
        await query.edit_message_text("❌ Alert not found.")
        return await show_alerts_menu(update, context)

    # Flip direction
    new_direction = (
        AlertDirection.BELOW if alert.direction == AlertDirection.ABOVE
        else AlertDirection.ABOVE
    )

    await alert_repo.update(alert_id, direction=new_direction)

    # Update WebSocket monitoring
    ws_service = context.bot_data.get("ws_service")
    if ws_service:
        await ws_service.remove_alert(alert_id)
        updated_alert = await alert_repo.get_by_id(alert_id)
        await ws_service.add_alert(updated_alert)

    await query.answer(f"✅ Direction changed to {new_direction.value}")

    # Refresh the view
    context.user_data["editing_alert_id"] = alert_id
    query.data = f"alert_view_{alert_id}"
    return await view_alert(update, context)


async def start_edit_alert_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Start editing alert price - prompt for new price."""
    query = update.callback_query
    await query.answer()

    alert_id = int(query.data.replace("alert_edit_price_", ""))
    context.user_data["editing_alert_id"] = alert_id

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Get alert
    alert_repo = PriceAlertRepository(context.bot_data["db"])
    alert = await alert_repo.get_by_id(alert_id)

    if not alert or alert.user_id != db_user.id:
        await query.edit_message_text("❌ Alert not found.")
        return await show_alerts_menu(update, context)

    text = (
        f"✏️ *Edit Alert Price*\n\n"
        f"📊 Market: _{alert.market_question[:40] if alert.market_question else 'Unknown'}..._\n"
        f"🎯 Current Target: `{alert.target_price_cents:.1f}c`\n\n"
        f"Enter new target price in cents (1-99):\n"
        f"_Example: `45` for 45 cents_"
    )

    keyboard = [
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"alert_view_{alert_id}"),
        ],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.ALERTS_EDIT_PRICE


async def handle_edit_alert_price_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle new price input for alert editing."""
    alert_id = context.user_data.get("editing_alert_id")
    if not alert_id:
        await update.message.reply_text("❌ No alert being edited.")
        return await show_alerts_menu(update, context)

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await update.message.reply_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Parse price input
    text = update.message.text.strip()

    try:
        # Support both "45" and "0.45" formats
        if "." in text:
            new_price = float(text)
            if new_price > 1:
                new_price = new_price / 100  # Assume cents if > 1
        else:
            new_price = float(text) / 100  # Convert cents to decimal

        if new_price <= 0 or new_price >= 1:
            raise ValueError("Price must be between 1 and 99 cents")

    except ValueError as e:
        await update.message.reply_text(
            f"❌ Invalid price. Please enter a number between 1 and 99.\n"
            f"_Example: `45` for 45 cents_",
            parse_mode="Markdown",
        )
        return ConversationState.ALERTS_EDIT_PRICE

    # Update alert
    alert_repo = PriceAlertRepository(context.bot_data["db"])
    alert = await alert_repo.get_by_id(alert_id)

    if not alert or alert.user_id != db_user.id:
        await update.message.reply_text("❌ Alert not found.")
        return await show_alerts_menu(update, context)

    await alert_repo.update(alert_id, target_price=new_price)

    # Update WebSocket monitoring
    ws_service = context.bot_data.get("ws_service")
    if ws_service:
        await ws_service.remove_alert(alert_id)
        updated_alert = await alert_repo.get_by_id(alert_id)
        await ws_service.add_alert(updated_alert)

    await update.message.reply_text(
        f"✅ Alert price updated to `{new_price * 100:.1f}c`",
        parse_mode="Markdown",
    )

    # Clear editing state and show alert
    context.user_data.pop("editing_alert_id", None)

    # Return to alerts menu
    return await show_alerts_menu(update, context)


async def delete_alert(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Delete a specific alert."""
    query = update.callback_query
    await query.answer()

    alert_id = int(query.data.replace("alert_delete_", ""))

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Delete alert
    alert_repo = PriceAlertRepository(context.bot_data["db"])
    alert = await alert_repo.get_by_id(alert_id)

    if not alert or alert.user_id != db_user.id:
        await query.edit_message_text("❌ Alert not found.")
        return await show_alerts_menu(update, context)

    await alert_repo.delete(alert_id)

    # Remove from WebSocket monitoring
    ws_service = context.bot_data.get("ws_service")
    if ws_service:
        await ws_service.remove_alert(alert_id)

    await query.answer("✅ Alert deleted")

    return await show_alerts_menu(update, context)


async def delete_all_alerts(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Delete all alerts for the user."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Get all alerts first (to remove from WebSocket)
    alert_repo = PriceAlertRepository(context.bot_data["db"])
    alerts = await alert_repo.get_user_alerts(db_user.id, active_only=True)

    # Remove from WebSocket monitoring
    ws_service = context.bot_data.get("ws_service")
    if ws_service:
        for alert in alerts:
            await ws_service.remove_alert(alert.id)

    # Delete all alerts
    deleted_count = await alert_repo.delete_user_alerts(db_user.id)

    await query.answer(f"✅ Deleted {deleted_count} alerts")

    return await show_alerts_menu(update, context)


async def create_alert_from_market(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Start creating an alert from market detail view."""
    query = update.callback_query
    await query.answer()

    # Get market data from context
    market = context.user_data.get("current_market")
    if not market:
        await query.edit_message_text("❌ Market data not found. Please select a market first.")
        return ConversationState.BROWSE_RESULTS

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    # Check alert limit
    alert_repo = PriceAlertRepository(context.bot_data["db"])
    alert_count = await alert_repo.count_user_alerts(db_user.id)

    if alert_count >= MAX_ALERTS_PER_USER:
        await query.answer(
            f"⚠️ You've reached the maximum of {MAX_ALERTS_PER_USER} alerts. Delete some to create new ones.",
            show_alert=True,
        )
        return ConversationState.BROWSE_RESULTS

    # Store market data for alert creation
    context.user_data["alert_market"] = market

    # Get current prices
    yes_price = market.get("yes_price", 0.5)
    no_price = market.get("no_price", 0.5)

    text = (
        f"🔔 *Create Price Alert*\n\n"
        f"📊 Market: _{market.get('question', 'Unknown')[:60]}..._\n\n"
        f"💰 Current Prices:\n"
        f"├ YES: `{yes_price * 100:.1f}c`\n"
        f"└ NO: `{no_price * 100:.1f}c`\n\n"
        f"Select which outcome to track:"
    )

    keyboard = [
        [
            InlineKeyboardButton(f"📈 YES ({yes_price * 100:.0f}c)", callback_data="alert_outcome_YES"),
            InlineKeyboardButton(f"📉 NO ({no_price * 100:.0f}c)", callback_data="alert_outcome_NO"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="menu_browse"),
        ],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.ALERTS_CREATE_OUTCOME


async def select_alert_outcome(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle outcome selection for new alert."""
    query = update.callback_query
    await query.answer()

    outcome = query.data.replace("alert_outcome_", "")
    context.user_data["alert_outcome"] = outcome

    market = context.user_data.get("alert_market")
    if not market:
        await query.edit_message_text("❌ Market data not found.")
        return ConversationState.MAIN_MENU

    # Get current price for selected outcome
    if outcome == "YES":
        current_price = market.get("yes_price", 0.5)
    else:
        current_price = market.get("no_price", 0.5)

    context.user_data["alert_current_price"] = current_price

    text = (
        f"🔔 *Create Alert - Direction*\n\n"
        f"📊 {outcome} price is currently `{current_price * 100:.1f}c`\n\n"
        f"Alert me when price:"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                f"📈 Rises Above",
                callback_data="alert_direction_ABOVE"
            ),
        ],
        [
            InlineKeyboardButton(
                f"📉 Drops Below",
                callback_data="alert_direction_BELOW"
            ),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="menu_browse"),
        ],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.ALERTS_CREATE_DIRECTION


async def select_alert_direction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle direction selection for new alert."""
    query = update.callback_query
    await query.answer()

    direction = query.data.replace("alert_direction_", "")
    context.user_data["alert_direction"] = AlertDirection(direction)

    market = context.user_data.get("alert_market")
    outcome = context.user_data.get("alert_outcome")
    current_price = context.user_data.get("alert_current_price", 0.5)

    text = (
        f"🔔 *Create Alert - Target Price*\n\n"
        f"📊 {outcome} @ `{current_price * 100:.1f}c`\n"
        f"📍 Direction: {'📈 Rises Above' if direction == 'ABOVE' else '📉 Drops Below'}\n\n"
        f"Enter target price in cents (1-99):\n"
        f"_Example: `65` for 65 cents_"
    )

    # Suggest prices
    if direction == "ABOVE":
        suggested = [
            int(current_price * 100) + 5,
            int(current_price * 100) + 10,
            int(current_price * 100) + 20,
        ]
    else:
        suggested = [
            int(current_price * 100) - 5,
            int(current_price * 100) - 10,
            int(current_price * 100) - 20,
        ]

    # Filter valid suggestions (1-99)
    suggested = [s for s in suggested if 1 <= s <= 99]

    keyboard = []
    if suggested:
        row = []
        for price in suggested[:3]:
            row.append(InlineKeyboardButton(f"{price}c", callback_data=f"alert_price_{price}"))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("❌ Cancel", callback_data="menu_browse"),
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.ALERTS_CREATE_PRICE


async def handle_alert_price_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle quick price selection button."""
    query = update.callback_query
    await query.answer()

    price_cents = int(query.data.replace("alert_price_", ""))
    target_price = price_cents / 100

    return await create_alert_with_price(update, context, target_price)


async def handle_alert_price_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle manual price input for new alert."""
    text = update.message.text.strip()

    try:
        # Support both "45" and "0.45" formats
        if "." in text:
            target_price = float(text)
            if target_price > 1:
                target_price = target_price / 100
        else:
            target_price = float(text) / 100

        if target_price <= 0 or target_price >= 1:
            raise ValueError("Price must be between 1 and 99 cents")

    except ValueError:
        await update.message.reply_text(
            f"❌ Invalid price. Please enter a number between 1 and 99.\n"
            f"_Example: `45` for 45 cents_",
            parse_mode="Markdown",
        )
        return ConversationState.ALERTS_CREATE_PRICE

    return await create_alert_with_price(update, context, target_price)


async def create_alert_with_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_price: float,
) -> int:
    """Create the alert with the specified price."""
    query = update.callback_query if update.callback_query else None

    user = update.effective_user
    user_service = context.bot_data["user_service"]

    db_user = await user_service.get_user(user.id)
    if not db_user:
        if query:
            await query.edit_message_text("❌ User not found.")
        else:
            await update.message.reply_text("❌ User not found.")
        return ConversationState.MAIN_MENU

    market = context.user_data.get("alert_market")
    outcome = context.user_data.get("alert_outcome")
    direction = context.user_data.get("alert_direction")

    if not all([market, outcome, direction]):
        if query:
            await query.edit_message_text("❌ Alert data missing. Please start over.")
        else:
            await update.message.reply_text("❌ Alert data missing. Please start over.")
        return ConversationState.MAIN_MENU

    # Get token ID for the outcome
    tokens = market.get("tokens", {})
    token_id = tokens.get(outcome, {}).get("id") or tokens.get(outcome.lower(), {}).get("id")

    if not token_id:
        # Try alternative token format
        if outcome == "YES":
            token_id = market.get("yes_token_id") or market.get("clobTokenIds", [""])[0]
        else:
            token_id = market.get("no_token_id") or market.get("clobTokenIds", ["", ""])[1] if len(market.get("clobTokenIds", [])) > 1 else ""

    if not token_id:
        if query:
            await query.edit_message_text("❌ Could not determine token ID for this market.")
        else:
            await update.message.reply_text("❌ Could not determine token ID for this market.")
        return ConversationState.MAIN_MENU

    # Create alert
    alert_repo = PriceAlertRepository(context.bot_data["db"])

    alert = await alert_repo.create(
        user_id=db_user.id,
        token_id=token_id,
        market_condition_id=market.get("condition_id", ""),
        outcome=outcome,
        target_price=target_price,
        direction=direction,
        market_question=market.get("question"),
    )

    # Add to WebSocket monitoring
    ws_service = context.bot_data.get("ws_service")
    if ws_service:
        await ws_service.add_alert(alert)

    # Clear alert creation data
    context.user_data.pop("alert_market", None)
    context.user_data.pop("alert_outcome", None)
    context.user_data.pop("alert_direction", None)
    context.user_data.pop("alert_current_price", None)

    direction_text = "rises above" if direction == AlertDirection.ABOVE else "drops below"

    text = (
        f"✅ *Alert Created!*\n\n"
        f"📊 Market: _{market.get('question', 'Unknown')[:50]}..._\n"
        f"🎯 Outcome: *{outcome}*\n"
        f"📍 Alert when price {direction_text} `{target_price * 100:.1f}c`\n\n"
        f"🔔 You'll receive a notification when the price hits your target!"
    )

    keyboard = [
        [InlineKeyboardButton("🔔 View All Alerts", callback_data="menu_alerts")],
        [InlineKeyboardButton("💹 Browse More Markets", callback_data="menu_browse")],
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

    logger.info(f"Alert {alert.id} created for user {db_user.id}")

    return ConversationState.ALERTS_MENU

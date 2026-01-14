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
    """Show list of top traders with real data from Polymarket leaderboard."""
    query = update.callback_query
    await query.answer()

    # Get filter parameters from context or use defaults
    page = context.user_data.get("discover_page", 0)
    category = context.user_data.get("discover_category", "OVERALL")
    time_period = context.user_data.get("discover_time", "WEEK")
    order_by = context.user_data.get("discover_sort", "PNL")

    # Get bot username for deep links
    bot_username = context.bot.username

    # Fetch traders from leaderboard
    from services.leaderboard_service import LeaderboardService

    leaderboard_service = LeaderboardService()

    try:
        traders_per_page = 10
        offset = page * traders_per_page

        traders = await leaderboard_service.get_top_traders(
            limit=traders_per_page,
            offset=offset,
            category=category,
            time_period=time_period,
            order_by=order_by,
        )

        if not traders:
            text = "🏆 <b>Discover Traders</b>\n\n❌ No traders found for this filter."
            keyboard = [
                [InlineKeyboardButton("🔙 Back", callback_data="menu_copy")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
            return ConversationState.COPY_TRADING_MENU

        # Format header with current filters
        time_display = {"DAY": "24h", "WEEK": "7d", "MONTH": "30d", "ALL": "All Time"}
        category_display = category.replace("_", " ").title()
        sort_display = "P&L" if order_by == "PNL" else "Volume"

        text = (
            f"🏆 <b>Discover Traders</b>\n\n"
            f"🌍 {category_display} · ⏰ {time_display.get(time_period, '7d')} · "
            f"📊 by {sort_display}\n\n"
        )

        for i, trader in enumerate(traders, 1):
            # Format trader display
            rank = trader.get("rank", offset + i)
            name = trader.get("name", "Anonymous")
            pnl = trader.get("pnl", 0)
            volume = trader.get("volume", 0)
            verified = trader.get("verified", False)

            pnl_emoji = "📈" if pnl >= 0 else "📉"
            verified_badge = "✅ " if verified else ""

            # Create deep links for Copy and View
            copy_link = f"https://t.me/{bot_username}?start=ct_{trader['address']}"
            view_link = f"https://t.me/{bot_username}?start=vt_{trader['address']}"

            text += (
                f"{rank}. {verified_badge}{name}\n"
                f"├ {pnl_emoji} P&L: <code>${pnl:,.2f}</code> · 💹 Vol: <code>${volume:,.0f}</code>\n"
                f'└ <a href="{copy_link}">Copy</a> · <a href="{view_link}">View</a>\n\n'
            )

        # Navigation row: Prev / Page X/Y / Next
        total_possible_pages = 10  # API limits to 1000 offset, so max 100 pages with limit=10
        current_page_display = page + 1

        keyboard = []
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data="discover_prev"))

        nav_row.append(InlineKeyboardButton(
            f"{current_page_display}/{total_possible_pages}",
            callback_data="discover_page_info"
        ))

        if len(traders) == traders_per_page:  # More results available
            nav_row.append(InlineKeyboardButton("Next ▶️", callback_data="discover_next"))

        keyboard.append(nav_row)

        # Filter buttons row
        keyboard.append([
            InlineKeyboardButton("📂 Category", callback_data="discover_filter_category"),
            InlineKeyboardButton("⏰ Time", callback_data="discover_filter_time"),
            InlineKeyboardButton("📊 Sort", callback_data="discover_filter_sort"),
        ])

        # Back row
        keyboard.append([
            InlineKeyboardButton("🔙 Back", callback_data="menu_copy"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
        ])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Failed to fetch traders: {e}")
        await query.edit_message_text(
            "❌ Failed to load traders. Please try again.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="menu_copy")]
            ]),
        )

    finally:
        await leaderboard_service.close()

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


async def handle_discover_pagination(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle discover traders pagination."""
    query = update.callback_query
    callback_data = query.data

    if callback_data == "discover_next":
        context.user_data["discover_page"] = context.user_data.get("discover_page", 0) + 1
    elif callback_data == "discover_prev":
        context.user_data["discover_page"] = max(0, context.user_data.get("discover_page", 0) - 1)

    return await browse_top_traders(update, context)


async def show_category_filter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show category filter options."""
    query = update.callback_query
    await query.answer()

    text = "📂 *Select Category*\n\nChoose a market category to filter traders:"

    categories = [
        ("OVERALL", "🌍 All Markets"),
        ("POLITICS", "🏛️ Politics"),
        ("SPORTS", "⚽ Sports"),
        ("CRYPTO", "₿ Crypto"),
        ("CULTURE", "🎭 Culture"),
        ("ECONOMICS", "📈 Economics"),
        ("TECH", "💻 Tech"),
        ("FINANCE", "💰 Finance"),
    ]

    keyboard = []
    for cat_id, cat_name in categories:
        keyboard.append([
            InlineKeyboardButton(cat_name, callback_data=f"set_category_{cat_id}")
        ])

    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="copy_browse")
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.SELECT_TRADER


async def show_time_filter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show time period filter options."""
    query = update.callback_query
    await query.answer()

    text = "⏰ *Select Time Period*\n\nChoose time window for trader stats:"

    time_periods = [
        ("DAY", "📅 Last 24 Hours"),
        ("WEEK", "📆 Last 7 Days"),
        ("MONTH", "🗓️ Last 30 Days"),
        ("ALL", "🌐 All Time"),
    ]

    keyboard = []
    for period_id, period_name in time_periods:
        keyboard.append([
            InlineKeyboardButton(period_name, callback_data=f"set_time_{period_id}")
        ])

    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="copy_browse")
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.SELECT_TRADER


async def show_sort_filter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show sort options."""
    query = update.callback_query
    await query.answer()

    text = "📊 *Sort By*\n\nChoose how to rank traders:"

    keyboard = [
        [InlineKeyboardButton("💰 P&L (Profit & Loss)", callback_data="set_sort_PNL")],
        [InlineKeyboardButton("📈 Volume (Total Traded)", callback_data="set_sort_VOL")],
        [InlineKeyboardButton("🔙 Back", callback_data="copy_browse")],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.SELECT_TRADER


async def start_copy_from_deeplink(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    trader_address: str,
) -> int:
    """Start copy subscription flow from deep link."""
    logger.info(f"Starting copy flow from deep link for trader: {trader_address}")

    context.user_data["copy_trader_address"] = trader_address

    keyboard = [
        [InlineKeyboardButton("🔙 Back", callback_data="menu_copy")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ]

    await update.message.reply_text(
        f"👥 *Copy Trader*\n\n"
        f"👤 Trader: `{trader_address[:10]}...{trader_address[-8:]}`\n\n"
        f"📊 Enter allocation percentage (1-50):\n"
        f"💡 _This is the percentage of your balance used for each trade._",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.ENTER_ALLOCATION


async def view_trader_from_deeplink(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    trader_address: str,
) -> int:
    """Show trader profile from deep link."""
    logger.info(f"Viewing trader profile from deep link: {trader_address}")

    from services.leaderboard_service import LeaderboardService
    leaderboard_service = LeaderboardService()

    try:
        profile = await leaderboard_service.get_trader_profile(trader_address)

        if profile:
            # Full profile found on leaderboard
            name = profile.get("name", "Anonymous")
            pnl = profile.get("pnl", 0)
            volume = profile.get("volume", 0)
            rank = profile.get("rank", "N/A")
            x_username = profile.get("x_username", "")
            verified = profile.get("verified", False)

            pnl_emoji = "📈" if pnl >= 0 else "📉"
            verified_badge = "✅ Verified" if verified else ""

            text = (
                f"👤 *Trader Profile*\n\n"
                f"*{name}* {verified_badge}\n\n"
                f"🏆 Rank: `#{rank}`\n"
                f"{pnl_emoji} P&L: `${pnl:,.2f}`\n"
                f"💹 Volume: `${volume:,.0f}`\n"
                f"🔑 Address: `{trader_address[:10]}...{trader_address[-8:]}`\n"
            )

            if x_username:
                text += f"🐦 Twitter: @{x_username}\n"

            text += "\n💡 _Tap 'Copy' to start copying this trader's trades._"
        else:
            # Trader not on leaderboard - show basic info with address
            text = (
                f"👤 *Trader Profile*\n\n"
                f"🔑 Address: `{trader_address[:10]}...{trader_address[-8:]}`\n\n"
                f"ℹ️ _This trader is not currently on the leaderboard._\n"
                f"_Stats may be unavailable, but you can still copy their trades._\n\n"
                f"💡 _Tap 'Copy' to start copying this trader's trades._"
            )

        keyboard = [
            [InlineKeyboardButton("👥 Copy This Trader", callback_data=f"copy_trader_{trader_address}")],
            [InlineKeyboardButton("🏆 Browse Traders", callback_data="copy_browse")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Failed to fetch trader profile from deep link: {e}")
        await update.message.reply_text(
            "❌ Failed to load trader profile. Please try again.",
        )
        from bot.handlers.menu import show_main_menu
        return await show_main_menu(update, context, send_new=True)

    finally:
        await leaderboard_service.close()

    return ConversationState.SELECT_TRADER


async def view_trader_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show detailed trader profile."""
    query = update.callback_query
    await query.answer()

    trader_address = query.data.replace("view_trader_", "")

    from services.leaderboard_service import LeaderboardService
    leaderboard_service = LeaderboardService()

    try:
        profile = await leaderboard_service.get_trader_profile(trader_address)

        if not profile:
            await query.answer("❌ Trader not found", show_alert=True)
            return await browse_top_traders(update, context)

        name = profile.get("name", "Anonymous")
        pnl = profile.get("pnl", 0)
        volume = profile.get("volume", 0)
        rank = profile.get("rank", "N/A")
        x_username = profile.get("x_username", "")
        verified = profile.get("verified", False)

        pnl_emoji = "📈" if pnl >= 0 else "📉"
        verified_badge = "✅ Verified" if verified else ""

        text = (
            f"👤 *Trader Profile*\n\n"
            f"**{name}** {verified_badge}\n\n"
            f"🏆 Rank: `#{rank}`\n"
            f"{pnl_emoji} P&L: `${pnl:,.2f}`\n"
            f"💹 Volume: `${volume:,.0f}`\n"
            f"🔑 Address: `{trader_address[:10]}...{trader_address[-8:]}`\n"
        )

        if x_username:
            text += f"🐦 Twitter: @{x_username}\n"

        text += "\n💡 _Tap 'Copy' to start copying this trader's trades._"

        keyboard = [
            [InlineKeyboardButton("👥 Copy This Trader", callback_data=f"copy_trader_{trader_address}")],
            [InlineKeyboardButton("🔙 Back to List", callback_data="copy_browse")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Failed to fetch trader profile: {e}")
        await query.answer("❌ Failed to load profile", show_alert=True)
        return await browse_top_traders(update, context)

    finally:
        await leaderboard_service.close()

    return ConversationState.SELECT_TRADER


async def handle_copy_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle copy trading callbacks."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    # Pagination
    if callback_data in ["discover_next", "discover_prev"]:
        return await handle_discover_pagination(update, context)

    # Filters
    elif callback_data == "discover_filter_category":
        return await show_category_filter(update, context)

    elif callback_data == "discover_filter_time":
        return await show_time_filter(update, context)

    elif callback_data == "discover_filter_sort":
        return await show_sort_filter(update, context)

    # Set filter values
    elif callback_data.startswith("set_category_"):
        category = callback_data.replace("set_category_", "")
        context.user_data["discover_category"] = category
        context.user_data["discover_page"] = 0  # Reset to first page
        return await browse_top_traders(update, context)

    elif callback_data.startswith("set_time_"):
        time_period = callback_data.replace("set_time_", "")
        context.user_data["discover_time"] = time_period
        context.user_data["discover_page"] = 0
        return await browse_top_traders(update, context)

    elif callback_data.startswith("set_sort_"):
        order_by = callback_data.replace("set_sort_", "")
        context.user_data["discover_sort"] = order_by
        context.user_data["discover_page"] = 0
        return await browse_top_traders(update, context)

    # View trader profile
    elif callback_data.startswith("view_trader_"):
        return await view_trader_profile(update, context)

    # Main actions
    elif callback_data == "copy_browse":
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
                await query.answer("⏸️ Subscription paused")
            else:
                await copy_repo.activate(sub_id)
                await query.answer("▶️ Subscription reactivated")

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

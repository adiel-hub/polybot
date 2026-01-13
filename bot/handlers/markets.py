"""Market browsing handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from bot.keyboards.main_menu import get_browse_keyboard
from bot.keyboards.common import get_back_keyboard
from utils.url_parser import is_polymarket_url, extract_slug_from_url, extract_url_from_text

logger = logging.getLogger(__name__)


async def show_browse_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show market browsing options."""
    query = update.callback_query
    if query:
        await query.answer()

    text = (
        "🔍 *Market Search*\n\n"
        '✏️ Type any keyword to search (e.g. "bitcoin", "trump")\n'
        '🔗 Or paste a Polymarket URL (e.g. polymarket.com/event/...)\n\n'
        "📂 Or browse by:"
    )

    keyboard = get_browse_keyboard()

    if query:
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    # Set flag to expect search input
    context.user_data["awaiting_search"] = True

    return ConversationState.BROWSE_CATEGORY


async def handle_browse_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle browse category selection."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    market_service = context.bot_data["market_service"]

    # Extract category and page
    if callback_data.startswith("browse_"):
        parts = callback_data.replace("browse_", "").split("_page_")
        category = parts[0]
        page = int(parts[1]) if len(parts) > 1 else 1
    else:
        category = "trending"
        page = 1

    # Reset search flag
    context.user_data["awaiting_search"] = False

    # Handle category selection
    if category == "category":
        # Show category list
        keyboard = [
            [
                InlineKeyboardButton("🏛️ Politics", callback_data="browse_politics"),
                InlineKeyboardButton("⚽ Sports", callback_data="browse_sports"),
            ],
            [
                InlineKeyboardButton("₿ Crypto", callback_data="browse_crypto"),
                InlineKeyboardButton("🎬 Entertainment", callback_data="browse_entertainment"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="menu_browse"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
            ],
        ]
        await query.edit_message_text(
            "🏷️ *Select Category*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return ConversationState.BROWSE_CATEGORY

    # Fetch markets
    limit = 5
    offset = (page - 1) * limit

    markets = await market_service.get_markets_by_category(
        category=category,
        limit=limit,
        offset=offset,
    )

    if not markets:
        await query.edit_message_text(
            "📭 No markets found in this category.",
            reply_markup=get_back_keyboard("menu_browse"),
        )
        return ConversationState.BROWSE_RESULTS

    # Store markets in context for selection
    context.user_data["browse_markets"] = {m.condition_id: m for m in markets}
    context.user_data["browse_category"] = category
    context.user_data["browse_page"] = page

    # Build market list text
    category_names = {
        "volume": "📊 Top Volume",
        "trending": "🔥 Trending",
        "new": "✨ New Markets",
        "politics": "🏛️ Politics",
        "sports": "⚽ Sports",
        "crypto": "₿ Crypto",
        "entertainment": "🎬 Entertainment",
        "15m": "⏱️ 15m Up or Down",
    }

    text = f"💹 *Market Search - {category_names.get(category, category.title())}*\n\n"

    keyboard = []
    for i, market in enumerate(markets, 1):
        # Format prices as percentages
        yes_cents = int(market.yes_price * 100)
        no_cents = int(market.no_price * 100)

        text += (
            f"{i}) {market.question[:60]}{'...' if len(market.question) > 60 else ''}\n"
            f"  ├ ✅ YES `{yes_cents}c` │ ❌ NO `{no_cents}c`\n"
            f"  ├ 📊 24h Vol `${market.volume_24h:,.0f}` │ 💧 Liq `${market.liquidity:,.0f}`\n"
            f"  └ 📈 Trade │ 🔗 View on Polymarket\n\n"
        )

        # Add trade button for each market
        keyboard.append([
            InlineKeyboardButton(
                f"📈 {i}. Trade",
                callback_data=f"market_{market.condition_id[:20]}",
            )
        ])

    # Pagination
    total_pages = 5  # Assume 5 pages max
    nav_row = []

    if page > 1:
        nav_row.append(
            InlineKeyboardButton("◀️ Prev", callback_data=f"browse_{category}_page_{page-1}")
        )

    nav_row.append(
        InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop")
    )

    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton("Next ▶️", callback_data=f"browse_{category}_page_{page+1}")
        )

    keyboard.append(nav_row)
    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="menu_browse"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.BROWSE_RESULTS


async def show_market_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show detailed market view with trading options."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    condition_id_prefix = callback_data.replace("market_", "")

    # Find full condition ID from stored markets
    browse_markets = context.user_data.get("browse_markets", {})
    market = None

    for cid, m in browse_markets.items():
        if cid.startswith(condition_id_prefix):
            market = m
            break

    if not market:
        # Try fetching from API
        market_service = context.bot_data["market_service"]
        market = await market_service.get_market_detail(condition_id_prefix)

    if not market:
        await query.edit_message_text(
            "❌ Market not found.",
            reply_markup=get_back_keyboard("menu_browse"),
        )
        return ConversationState.BROWSE_RESULTS

    # Store current market in context
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

    text = (
        f"📊 {market.question}\n"
        f"{'─' * 35}\n\n"
        f"💰 *Current Prices*\n"
        f"├ ✅ Yes: `{yes_cents:.1f}c`\n"
        f"└ ❌ No: `{no_cents:.1f}c`\n\n"
        f"📈 *Market Stats*\n"
        f"├ 📊 Volume (All): `${market.total_volume:,.2f}`\n"
        f"├ 📊 Volume (24h): `${market.volume_24h:,.2f}`\n"
        f"└ 💧 Liquidity: `${market.liquidity:,.2f}`\n"
    )

    if market.end_date:
        text += f"\n⏰ *Timeline*\n└ 📅 Expires: {market.end_date}\n"

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
            InlineKeyboardButton("🔄 Refresh", callback_data=f"market_{condition_id_prefix}"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
        ],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.MARKET_DETAIL


async def handle_search_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle search keyword input or Polymarket URL."""
    if not context.user_data.get("awaiting_search"):
        return ConversationState.MAIN_MENU

    query_text = update.message.text.strip()
    market_service = context.bot_data["market_service"]

    context.user_data["awaiting_search"] = False

    # Check if input is a Polymarket URL
    if is_polymarket_url(query_text):
        url = extract_url_from_text(query_text)
        slug = extract_slug_from_url(url) if url else None

        if not slug:
            # Show error with format help
            await update.message.reply_text(
                "❌ Invalid Polymarket URL format.\n\n"
                "Expected:\n"
                "• https://polymarket.com/event/your-market\n"
                "• https://polymarket.com/market/your-market",
                reply_markup=get_back_keyboard("menu_browse"),
            )
            return ConversationState.BROWSE_RESULTS

        # Fetch market by slug
        market = await market_service.get_market_by_slug(slug)

        if not market:
            await update.message.reply_text(
                f"❌ Market not found for slug: `{slug}`\n\n"
                "The market may have been removed or the URL is invalid.",
                reply_markup=get_back_keyboard("menu_browse"),
                parse_mode="Markdown",
            )
            return ConversationState.BROWSE_RESULTS

        # Store market and display details
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

        text = (
            f"🔗 *Market from URL*\n"
            f"{'─' * 35}\n\n"
            f"📊 {market.question}\n\n"
            f"💰 *Current Prices*\n"
            f"├ ✅ Yes: `{yes_cents:.1f}c`\n"
            f"└ ❌ No: `{no_cents:.1f}c`\n\n"
            f"📈 *Market Stats*\n"
            f"├ 📊 Volume (All): `${market.total_volume:,.2f}`\n"
            f"├ 📊 Volume (24h): `${market.volume_24h:,.2f}`\n"
            f"└ 💧 Liquidity: `${market.liquidity:,.2f}`\n"
        )

        if market.end_date:
            text += f"\n⏰ *Timeline*\n└ 📅 Expires: {market.end_date}\n"

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
                InlineKeyboardButton("🔙 Browse", callback_data="menu_browse"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
            ],
        ]

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return ConversationState.MARKET_DETAIL

    # If not URL, continue with existing keyword search logic
    markets = await market_service.search_markets(query_text, limit=5)

    if not markets:
        await update.message.reply_text(
            f'📭 No markets found for "{query_text}"',
            reply_markup=get_back_keyboard("menu_browse"),
        )
        return ConversationState.BROWSE_RESULTS

    # Store and display results
    context.user_data["browse_markets"] = {m.condition_id: m for m in markets}

    text = f'🔍 *Search Results for "{query_text}"*\n\n'

    keyboard = []
    for i, market in enumerate(markets, 1):
        yes_cents = int(market.yes_price * 100)

        text += (
            f"{i}) {market.question[:60]}{'...' if len(market.question) > 60 else ''}\n"
            f"  ├ ✅ YES `{yes_cents}c` │ 📊 Vol `${market.volume_24h:,.0f}`\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"📈 {i}. Trade",
                callback_data=f"market_{market.condition_id[:20]}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="menu_browse"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.BROWSE_RESULTS

"""Market browsing handlers."""

import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from bot.conversations.states import ConversationState
from bot.keyboards.main_menu import get_browse_keyboard
from bot.keyboards.common import get_back_keyboard
from utils.url_parser import is_polymarket_url, extract_slug_from_url, extract_url_from_text
from utils.polymarket_scraper import scrape_market_from_url
from utils.short_id import generate_short_id

logger = logging.getLogger(__name__)


def is_market_expired(market) -> bool:
    """Check if a market has expired based on its end_date."""
    if not market.end_date:
        return False
    try:
        end_dt = datetime.fromisoformat(market.end_date.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) > end_dt
    except (ValueError, AttributeError):
        return False


def is_market_tradeable(market) -> bool:
    """Check if a market has liquidity and is tradeable."""
    # Must have liquidity to be tradeable
    return market.liquidity > 0


def filter_active_markets(markets: list, sort_by_volume: bool = False) -> list:
    """Filter out expired and non-tradeable markets.

    Args:
        markets: List of markets to filter
        sort_by_volume: If True, sort by total_volume descending
    """
    filtered = [
        m for m in markets
        if not is_market_expired(m) and is_market_tradeable(m)
    ]
    if sort_by_volume:
        filtered.sort(key=lambda m: m.total_volume, reverse=True)
    return filtered


async def show_browse_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show market browsing options."""
    query = update.callback_query
    if query:
        await query.answer()

    text = (
        "🔍 *Market Search*\n\n"
        '✏️ Type any keyword to search (e.g. "bitcoin", "trump")\n'
        '🔗 Or paste a Polymarket link directly\n\n'
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

    # Pagination setup
    total_pages = 5  # Assume 5 pages max

    text = f"💹 <b>Market Search - {category_names.get(category, category.title())}</b>\n"
    text += f"📄 Page {page}/{total_pages}\n\n"

    # Get bot username for deep links
    bot_username = context.bot.username

    # Filter out expired and non-tradeable markets, limit to 5 per page
    tradeable_markets = filter_active_markets(markets)[:5]

    if not tradeable_markets:
        text += "<i>No tradeable markets found in this category.</i>\n"
    else:
        for i, market in enumerate(tradeable_markets, 1):
            # Format prices as percentages
            yes_cents = int(market.yes_price * 100)
            no_cents = int(market.no_price * 100)

            # Check if multi-outcome event
            is_multi_outcome = hasattr(market, 'outcomes_count') and market.outcomes_count > 1 and market.event_id

            # Use event title for multi-outcome events, question for single markets
            display_title = market.event_title if is_multi_outcome and market.event_title else market.question
            display_title = display_title[:50] + ('...' if len(display_title) > 50 else '')

            if is_multi_outcome:
                # Multi-outcome event: show options link instead of trade link
                event_link = f"https://t.me/{bot_username}?start=e_{market.event_id}"
                actions_html = f'🎯 <a href="{event_link}">{market.outcomes_count} Options</a>'

                text += (
                    f"{i}) {display_title}\n"
                    f"  ├ 📊 Vol <code>${market.total_volume:,.0f}</code> │ 💧 Liq <code>${market.liquidity:,.0f}</code>\n"
                    f"  └ {actions_html}\n\n"
                )
            else:
                # Single market: show trade link
                short_id = generate_short_id(market.condition_id)
                trade_link = f"https://t.me/{bot_username}?start=m_{short_id}"

                # Store mapping for lookup
                if "market_short_ids" not in context.bot_data:
                    context.bot_data["market_short_ids"] = {}
                context.bot_data["market_short_ids"][short_id] = market.condition_id

                trade_html = f'📈 <a href="{trade_link}">Trade</a>'
                polymarket_html = ""
                if market.slug:
                    polymarket_url = f"https://polymarket.com/market/{market.slug}"
                    polymarket_html = f' │ <a href="{polymarket_url}">View</a>'

                text += (
                    f"{i}) {display_title}\n"
                    f"  ├ ✅ YES <code>{yes_cents}c</code> │ ❌ NO <code>{no_cents}c</code>\n"
                    f"  ├ 📊 Vol <code>${market.volume_24h:,.0f}</code> │ 💧 Liq <code>${market.liquidity:,.0f}</code>\n"
                    f"  └ {trade_html}{polymarket_html}\n\n"
                )

    # Pagination navigation
    keyboard = []
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

    try:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except BadRequest as e:
        if "message is not modified" in str(e):
            # Message content is identical, just answer the callback
            await query.answer("Already on this page")
        elif "too long" in str(e).lower():
            # Message too long - truncate and retry
            logger.warning(f"Message too long ({len(text)} chars), truncating")
            truncated_text = text[:3500] + "\n\n<i>... (truncated)</i>"
            await query.edit_message_text(
                truncated_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        else:
            raise

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

    # Format expiration date
    from datetime import datetime
    expiry_text = ""
    is_expired = False
    if market.end_date:
        try:
            # Parse ISO format date
            end_dt = datetime.fromisoformat(market.end_date.replace('Z', '+00:00'))
            expiry_text = end_dt.strftime("%b %d, %Y at %I:%M %p UTC")
            # Check if expired
            is_expired = datetime.now(end_dt.tzinfo) > end_dt
        except:
            expiry_text = market.end_date

    text = (
        f"📊 *{market.question}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # Add expiration warning if expired
    if is_expired:
        text += f"⚠️ *This market has expired and is closed for trading*\n\n"

    text += (
        f"💰 *Current Prices*\n"
        f"├ ✅ Yes: `{yes_cents:.1f}c`\n"
        f"└ ❌ No: `{no_cents:.1f}c`\n\n"
        f"📈 *Market Stats*\n"
        f"├ 📊 Volume (All): `${market.total_volume:,.2f}`\n"
        f"├ 📊 Volume (24h): `${market.volume_24h:,.2f}`\n"
        f"└ 💧 Liquidity: `${market.liquidity:,.2f}`\n"
    )

    if expiry_text:
        status = "Expired" if is_expired else "Expires"
        text += f"\n⏰ *Timeline*\n└ 📅 {status}: {expiry_text}\n"

    # Add Polymarket link if slug exists
    if market.slug:
        polymarket_url = f"https://polymarket.com/market/{market.slug}"
        text += f"\n[View on Polymarket]({polymarket_url})\n"

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
            InlineKeyboardButton("🧠 AI Analysis", callback_data="ai_analysis"),
            InlineKeyboardButton("🔔 Set Alert", callback_data="create_alert"),
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
        disable_web_page_preview=True,
    )

    return ConversationState.MARKET_DETAIL


async def show_event_options(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show all outcomes for a multi-outcome event with pagination."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    # Format: event_options_{event_id}_page_{page}
    parts = callback_data.replace("event_options_", "").split("_page_")
    event_id = parts[0]
    page = int(parts[1]) if len(parts) > 1 else 1

    market_service = context.bot_data["market_service"]

    # Fetch all markets for this event
    markets = await market_service.get_event_markets(event_id)

    if not markets:
        await query.edit_message_text(
            "❌ Event not found or has no tradeable outcomes.",
            reply_markup=get_back_keyboard("menu_browse"),
        )
        return ConversationState.BROWSE_RESULTS

    # Filter active markets (with liquidity) and sort by volume
    tradeable_markets = filter_active_markets(markets, sort_by_volume=True)

    # Get event title from first market
    event_title = markets[0].event_title or "Event Options"
    total_outcomes = len(tradeable_markets)

    # Pagination: 5 per page
    per_page = 5
    total_pages = max(1, (total_outcomes + per_page - 1) // per_page)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_markets = tradeable_markets[start_idx:end_idx]

    # Store markets in context
    context.user_data["browse_markets"] = {m.condition_id: m for m in tradeable_markets}

    # Build message
    text = f"🎯 <b>{event_title[:50]}{'...' if len(event_title) > 50 else ''}</b>\n"
    text += f"📊 {total_outcomes} tradeable outcomes │ Page {page}/{total_pages}\n\n"

    bot_username = context.bot.username

    if not page_markets:
        text += "<i>No tradeable outcomes on this page.</i>\n"
    else:
        for i, market in enumerate(page_markets, start_idx + 1):
            yes_cents = int(market.yes_price * 100)

            # Build trade deep link with short ID
            short_id = generate_short_id(market.condition_id)
            trade_link = f"https://t.me/{bot_username}?start=m_{short_id}"

            # Store mapping for lookup
            if "market_short_ids" not in context.bot_data:
                context.bot_data["market_short_ids"] = {}
            context.bot_data["market_short_ids"][short_id] = market.condition_id

            # Extract outcome name from question (e.g., "Will X win?" -> "X")
            outcome_name = market.question
            if outcome_name.startswith("Will "):
                outcome_name = outcome_name[5:]
            if outcome_name.endswith("?"):
                outcome_name = outcome_name[:-1]
            # Truncate for display
            outcome_name = outcome_name[:50] + ("..." if len(outcome_name) > 50 else "")

            no_cents = int(market.no_price * 100)

            trade_html = f'📈 <a href="{trade_link}">Trade</a>'
            polymarket_html = ""
            if market.slug:
                polymarket_url = f"https://polymarket.com/market/{market.slug}"
                polymarket_html = f' │ <a href="{polymarket_url}">View</a>'

            text += (
                f"{i}) {outcome_name}\n"
                f"  ├ ✅ YES <code>{yes_cents}c</code> │ ❌ NO <code>{no_cents}c</code>\n"
                f"  ├ 📊 Vol <code>${market.volume_24h:,.0f}</code> │ 💧 Liq <code>${market.liquidity:,.0f}</code>\n"
                f"  └ {trade_html}{polymarket_html}\n\n"
            )

    # Pagination navigation
    keyboard = []
    nav_row = []

    if page > 1:
        nav_row.append(
            InlineKeyboardButton("◀️ Prev", callback_data=f"event_options_{event_id}_page_{page-1}")
        )

    nav_row.append(
        InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop")
    )

    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton("Next ▶️", callback_data=f"event_options_{event_id}_page_{page+1}")
        )

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="menu_browse"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    try:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except BadRequest as e:
        if "message is not modified" not in str(e):
            raise

    return ConversationState.EVENT_OPTIONS


async def show_event_options_from_deeplink(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    event_id: str,
    page: int = 1,
) -> int:
    """Show all outcomes for a multi-outcome event from a deep link."""
    market_service = context.bot_data["market_service"]

    # Fetch all markets for this event
    markets = await market_service.get_event_markets(event_id)

    if not markets:
        await update.message.reply_text(
            "❌ Event not found or has no tradeable outcomes.",
            reply_markup=get_back_keyboard("menu_browse"),
        )
        return ConversationState.BROWSE_RESULTS

    # Filter active markets (with liquidity) and sort by volume
    tradeable_markets = filter_active_markets(markets, sort_by_volume=True)

    # Get event title from first market
    event_title = markets[0].event_title or "Event Options"
    total_outcomes = len(tradeable_markets)

    # Pagination: 5 per page
    per_page = 5
    total_pages = max(1, (total_outcomes + per_page - 1) // per_page)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_markets = tradeable_markets[start_idx:end_idx]

    # Store markets in context
    context.user_data["browse_markets"] = {m.condition_id: m for m in tradeable_markets}

    # Build message
    text = f"🎯 <b>{event_title[:50]}{'...' if len(event_title) > 50 else ''}</b>\n"
    text += f"📊 {total_outcomes} tradeable outcomes │ Page {page}/{total_pages}\n\n"

    bot_username = context.bot.username

    if not page_markets:
        text += "<i>No tradeable outcomes on this page.</i>\n"
    else:
        for i, market in enumerate(page_markets, start_idx + 1):
            yes_cents = int(market.yes_price * 100)

            # Build trade deep link with short ID
            short_id = generate_short_id(market.condition_id)
            trade_link = f"https://t.me/{bot_username}?start=m_{short_id}"

            # Store mapping for lookup
            if "market_short_ids" not in context.bot_data:
                context.bot_data["market_short_ids"] = {}
            context.bot_data["market_short_ids"][short_id] = market.condition_id

            # Extract outcome name from question
            outcome_name = market.question
            if outcome_name.startswith("Will "):
                outcome_name = outcome_name[5:]
            if outcome_name.endswith("?"):
                outcome_name = outcome_name[:-1]
            outcome_name = outcome_name[:50] + ("..." if len(outcome_name) > 50 else "")

            no_cents = int(market.no_price * 100)

            trade_html = f'📈 <a href="{trade_link}">Trade</a>'
            polymarket_html = ""
            if market.slug:
                polymarket_url = f"https://polymarket.com/market/{market.slug}"
                polymarket_html = f' │ <a href="{polymarket_url}">View</a>'

            text += (
                f"{i}) {outcome_name}\n"
                f"  ├ ✅ YES <code>{yes_cents}c</code> │ ❌ NO <code>{no_cents}c</code>\n"
                f"  ├ 📊 Vol <code>${market.volume_24h:,.0f}</code> │ 💧 Liq <code>${market.liquidity:,.0f}</code>\n"
                f"  └ {trade_html}{polymarket_html}\n\n"
            )

    # Pagination navigation
    keyboard = []
    nav_row = []

    if page > 1:
        nav_row.append(
            InlineKeyboardButton("◀️ Prev", callback_data=f"event_options_{event_id}_page_{page-1}")
        )

    nav_row.append(
        InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop")
    )

    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton("Next ▶️", callback_data=f"event_options_{event_id}_page_{page+1}")
        )

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="menu_browse"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    return ConversationState.EVENT_OPTIONS


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

        # If slug lookup fails, try searching with keywords from slug
        if not market:
            # Convert slug to search query (replace hyphens with spaces)
            search_query = slug.replace("-", " ")
            logger.info(f"Slug lookup failed for '{slug}', trying search with '{search_query}'")

            markets = await market_service.search_markets(search_query, limit=10)

            if markets:
                # If we found results, show them as search results
                context.user_data["browse_markets"] = {m.condition_id: m for m in markets[:5]}

                text = f'🔍 <b>Results for Polymarket URL</b>\n\n'
                text += f"<i>Direct slug lookup failed, showing search results for: {search_query}</i>\n\n"

                # Get bot username for deep links
                bot_username = context.bot.username

                # Filter out expired and non-tradeable markets
                tradeable_markets = filter_active_markets(markets[:5])

                for i, m in enumerate(tradeable_markets, 1):
                    yes_cents = int(m.yes_price * 100)
                    no_cents = int(m.no_price * 100)

                    # Build trade deep link with short ID
                    short_id = generate_short_id(m.condition_id)
                    trade_link = f"https://t.me/{bot_username}?start=m_{short_id}"

                    # Store mapping for lookup
                    if "market_short_ids" not in context.bot_data:
                        context.bot_data["market_short_ids"] = {}
                    context.bot_data["market_short_ids"][short_id] = m.condition_id

                    # Build trade and view links (HTML format)
                    trade_html = f'📈 <a href="{trade_link}">Trade</a>'
                    polymarket_html = ""
                    if m.slug:
                        polymarket_url = f"https://polymarket.com/market/{m.slug}"
                        polymarket_html = f' │ <a href="{polymarket_url}">View</a>'

                    text += (
                        f"{i}) {m.question[:60]}{'...' if len(m.question) > 60 else ''}\n"
                        f"  ├ ✅ YES <code>{yes_cents}c</code> │ ❌ NO <code>{no_cents}c</code>\n"
                        f"  ├ 📊 Vol <code>${m.volume_24h:,.0f}</code> │ 💧 Liq <code>${m.liquidity:,.0f}</code>\n"
                        f"  └ {trade_html}{polymarket_html}\n\n"
                    )

                keyboard = []

                keyboard.append([
                    InlineKeyboardButton("🔙 Back", callback_data="menu_browse"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
                ])

                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )

                return ConversationState.BROWSE_RESULTS

            # No results from search either, try web scraping as final fallback
            logger.info(f"Search failed, trying web scraper for {url}")

            scraped_data = await scrape_market_from_url(url)

            if scraped_data and scraped_data.get("condition_id"):
                # Try to fetch market details using the scraped condition_id
                condition_id = scraped_data["condition_id"]
                market = await market_service.get_market_detail(condition_id)

                if market:
                    # Success! Store and display the market
                    context.user_data["current_market"] = {
                        "condition_id": market.condition_id,
                        "question": market.question,
                        "yes_token_id": market.yes_token_id,
                        "no_token_id": market.no_token_id,
                        "yes_price": market.yes_price,
                        "no_price": market.no_price,
                    }

                    yes_cents = market.yes_price * 100
                    no_cents = market.no_price * 100

                    # Format expiration date
                    from datetime import datetime
                    expiry_text = ""
                    is_expired = False
                    if market.end_date:
                        try:
                            end_dt = datetime.fromisoformat(market.end_date.replace('Z', '+00:00'))
                            expiry_text = end_dt.strftime("%b %d, %Y at %I:%M %p UTC")
                            is_expired = datetime.now(end_dt.tzinfo) > end_dt
                        except:
                            expiry_text = market.end_date

                    text = (
                        f"🔗 *Market from URL*\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📊 *{market.question}*\n\n"
                    )

                    if is_expired:
                        text += f"⚠️ *This market has expired and is closed for trading*\n\n"

                    text += (
                        f"💰 *Current Prices*\n"
                        f"├ ✅ Yes: `{yes_cents:.1f}c`\n"
                        f"└ ❌ No: `{no_cents:.1f}c`\n\n"
                        f"📈 *Market Stats*\n"
                        f"├ 📊 Volume (All): `${market.total_volume:,.2f}`\n"
                        f"├ 📊 Volume (24h): `${market.volume_24h:,.2f}`\n"
                        f"└ 💧 Liquidity: `${market.liquidity:,.2f}`\n"
                    )

                    if expiry_text:
                        status = "Expired" if is_expired else "Expires"
                        text += f"\n⏰ *Timeline*\n└ 📅 {status}: {expiry_text}\n"

                    # Add Polymarket link if slug exists
                    if market.slug:
                        polymarket_url = f"https://polymarket.com/market/{market.slug}"
                        text += f"\n[View on Polymarket]({polymarket_url})\n"

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
                        disable_web_page_preview=True,
                    )

                    return ConversationState.MARKET_DETAIL

            # Final failure - couldn't find market via any method
            await update.message.reply_text(
                f"❌ Market not found for URL.\n\n"
                f"Slug: `{slug}`\n"
                "The market may have been removed or is not available.",
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

        # Format expiration date
        from datetime import datetime
        expiry_text = ""
        is_expired = False
        if market.end_date:
            try:
                end_dt = datetime.fromisoformat(market.end_date.replace('Z', '+00:00'))
                expiry_text = end_dt.strftime("%b %d, %Y at %I:%M %p UTC")
                is_expired = datetime.now(end_dt.tzinfo) > end_dt
            except:
                expiry_text = market.end_date

        text = (
            f"🔗 *Market from URL*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 *{market.question}*\n\n"
        )

        if is_expired:
            text += f"⚠️ *This market has expired and is closed for trading*\n\n"

        text += (
            f"💰 *Current Prices*\n"
            f"├ ✅ Yes: `{yes_cents:.1f}c`\n"
            f"└ ❌ No: `{no_cents:.1f}c`\n\n"
            f"📈 *Market Stats*\n"
            f"├ 📊 Volume (All): `${market.total_volume:,.2f}`\n"
            f"├ 📊 Volume (24h): `${market.volume_24h:,.2f}`\n"
            f"└ 💧 Liquidity: `${market.liquidity:,.2f}`\n"
        )

        if expiry_text:
            status = "Expired" if is_expired else "Expires"
            text += f"\n⏰ *Timeline*\n└ 📅 {status}: {expiry_text}\n"

        # Add Polymarket link if slug exists
        if market.slug:
            polymarket_url = f"https://polymarket.com/market/{market.slug}"
            text += f"\n[View on Polymarket]({polymarket_url})\n"

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
            disable_web_page_preview=True,
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

    text = f'🔍 <b>Search Results for "{query_text}"</b>\n\n'

    # Get bot username for deep links
    bot_username = context.bot.username

    # Filter out expired and non-tradeable markets, limit to 5
    tradeable_markets = filter_active_markets(markets)[:5]

    if not tradeable_markets:
        text += "<i>No tradeable markets found.</i>\n"
    else:
        for i, market in enumerate(tradeable_markets, 1):
            yes_cents = int(market.yes_price * 100)
            no_cents = int(market.no_price * 100)

            # Check if multi-outcome event
            is_multi_outcome = hasattr(market, 'outcomes_count') and market.outcomes_count > 1 and market.event_id

            # Use event title for multi-outcome events, question for single markets
            display_title = market.event_title if is_multi_outcome and market.event_title else market.question
            display_title = display_title[:50] + ('...' if len(display_title) > 50 else '')

            if is_multi_outcome:
                # Multi-outcome event: show options link instead of trade link
                event_link = f"https://t.me/{bot_username}?start=e_{market.event_id}"
                actions_html = f'🎯 <a href="{event_link}">{market.outcomes_count} Options</a>'

                text += (
                    f"{i}) {display_title}\n"
                    f"  ├ 📊 Vol <code>${market.total_volume:,.0f}</code> │ 💧 Liq <code>${market.liquidity:,.0f}</code>\n"
                    f"  └ {actions_html}\n\n"
                )
            else:
                # Single market: show trade link
                short_id = generate_short_id(market.condition_id)
                trade_link = f"https://t.me/{bot_username}?start=m_{short_id}"

                # Store mapping for lookup
                if "market_short_ids" not in context.bot_data:
                    context.bot_data["market_short_ids"] = {}
                context.bot_data["market_short_ids"][short_id] = market.condition_id

                trade_html = f'📈 <a href="{trade_link}">Trade</a>'
                polymarket_html = ""
                if market.slug:
                    polymarket_url = f"https://polymarket.com/market/{market.slug}"
                    polymarket_html = f' │ <a href="{polymarket_url}">View</a>'

                text += (
                    f"{i}) {display_title}\n"
                    f"  ├ ✅ YES <code>{yes_cents}c</code> │ ❌ NO <code>{no_cents}c</code>\n"
                    f"  ├ 📊 Vol <code>${market.volume_24h:,.0f}</code> │ 💧 Liq <code>${market.liquidity:,.0f}</code>\n"
                    f"  └ {trade_html}{polymarket_html}\n\n"
                )

    keyboard = []

    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="menu_browse"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    return ConversationState.BROWSE_RESULTS

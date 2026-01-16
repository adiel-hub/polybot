"""AI Market Analysis handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from services.ai_analysis_service import get_ai_analysis_service

logger = logging.getLogger(__name__)


async def handle_ai_analysis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Generate and display AI market analysis."""
    query = update.callback_query
    await query.answer("🧠 Analyzing market...")

    # Get market data from context
    market = context.user_data.get("current_market")
    if not market:
        await query.edit_message_text(
            "❌ Market data not found. Please select a market first.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💹 Browse Markets", callback_data="menu_browse")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]),
        )
        return ConversationState.MAIN_MENU

    try:
        # Get AI analysis service
        ai_service = get_ai_analysis_service()

        # Extract market data
        question = market.get("question", "Unknown Market")
        yes_price = market.get("yes_price", 0.5)
        no_price = market.get("no_price", 0.5)
        volume_24h = market.get("volume_24h", 0)
        total_volume = market.get("total_volume", 0)
        liquidity = market.get("liquidity", 0)

        # Get price changes if available
        price_change_24h = market.get("price_change_24h", 0)
        price_change_7d = market.get("price_change_7d", 0)

        # Generate analysis
        analysis = ai_service.analyze_market(
            question=question,
            yes_price=yes_price,
            no_price=no_price,
            volume_24h=volume_24h,
            total_volume=total_volume,
            liquidity=liquidity,
            price_change_24h=price_change_24h,
            price_change_7d=price_change_7d,
        )

        # Format message
        message = ai_service.format_analysis_message(analysis)

        # Build keyboard
        keyboard = [
            [
                InlineKeyboardButton("📈 Trade", callback_data="trade_buy_yes"),
                InlineKeyboardButton("🔔 Set Alert", callback_data="create_alert"),
            ],
            [
                InlineKeyboardButton("🔄 Refresh Analysis", callback_data="ai_analysis"),
            ],
            [
                InlineKeyboardButton("🔙 Back to Market", callback_data=f"market_{market.get('condition_id', '')[:20]}"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
            ],
        ]

        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        logger.info(f"AI analysis generated for market: {question[:50]}")

    except Exception as e:
        logger.error(f"Failed to generate AI analysis: {e}")
        await query.edit_message_text(
            f"❌ Failed to generate analysis: {str(e)}\n\n"
            f"Please try again.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", callback_data="ai_analysis")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]),
        )

    return ConversationState.MARKET_DETAIL


async def handle_ai_education(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show educational content about prediction markets."""
    query = update.callback_query
    await query.answer()

    education_text = (
        "📚 *Understanding Prediction Markets*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *What Are Prediction Markets?*\n"
        "Prediction markets are platforms where people trade "
        "on the outcomes of future events. Prices reflect the "
        "crowd's collective estimate of probability.\n\n"
        "📊 *How to Read Prices*\n"
        "├ Price of 65c = 65% implied probability\n"
        "├ Price of 20c = 20% implied probability\n"
        "└ YES + NO prices ≈ $1.00\n\n"
        "⚠️ *Key Risks*\n"
        "├ 🔸 Markets can be wrong\n"
        "├ 🔸 Prices can be manipulated\n"
        "├ 🔸 Liquidity affects execution\n"
        "├ 🔸 Resolution rules matter\n"
        "└ 🔸 You can lose your entire position\n\n"
        "🧠 *Common Biases*\n"
        "├ *FOMO* - Fear of missing out pushes prices\n"
        "├ *Anchoring* - First price seen affects judgment\n"
        "├ *Confirmation* - Seeking info that confirms belief\n"
        "└ *Recency* - Overweighting recent events\n\n"
        "📈 *What Moves Prices*\n"
        "├ New information\n"
        "├ News and events\n"
        "├ Large trades\n"
        "└ Market sentiment\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *This is educational content only.*\n"
        "_Not financial advice. Trade responsibly._"
    )

    keyboard = [
        [InlineKeyboardButton("💹 Browse Markets", callback_data="menu_browse")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ]

    await query.edit_message_text(
        education_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return ConversationState.MAIN_MENU

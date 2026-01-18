"""Admin builder stats handler."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.utils.decorators import admin_only
from config.settings import settings

logger = logging.getLogger(__name__)


@admin_only
async def show_builder_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display builder account statistics and recent trades."""
    query = update.callback_query
    if query:
        await query.answer("Loading builder stats...")

    # Check if builder credentials are configured
    if not settings.poly_builder_api_key:
        text = (
            "🏗️ *Builder Stats*\n\n"
            "⚠️ Builder credentials not configured.\n\n"
            "Add to your `.env` file:\n"
            "```\n"
            "POLY_BUILDER_API_KEY=your_key\n"
            "POLY_BUILDER_SECRET=your_secret\n"
            "POLY_BUILDER_PASSPHRASE=your_passphrase\n"
            "```\n\n"
            "Get credentials at:\n"
            "https://polymarket.com/settings?tab=builder"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_menu")]]

        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return AdminState.BUILDER_STATS

    # Fetch builder trades
    try:
        # Create a temporary client to fetch builder trades
        from py_clob_client.client import ClobClient
        from py_builder_signing_sdk.config import BuilderConfig
        from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds

        builder_creds = BuilderApiKeyCreds(
            key=settings.poly_builder_api_key,
            secret=settings.poly_builder_secret,
            passphrase=settings.poly_builder_passphrase,
        )
        builder_config = BuilderConfig(local_builder_creds=builder_creds)

        client = ClobClient(
            host=settings.clob_host,
            chain_id=settings.chain_id,
            builder_config=builder_config,
        )

        trades = client.get_builder_trades() or []

        # Calculate stats
        total_trades = len(trades)
        total_volume = sum(float(t.get('size', 0)) * float(t.get('price', 0)) for t in trades)

        # Format recent trades
        text = (
            "🏗️ *Builder Stats*\n\n"
            f"✅ Builder credentials configured\n\n"
            f"📊 *Overview*\n"
            f"├ Total Trades: `{total_trades}`\n"
            f"└ Total Volume: `${total_volume:.2f}`\n\n"
        )

        if trades:
            text += "📋 *Recent Trades*\n"
            for i, trade in enumerate(trades[:10]):  # Show last 10
                side = trade.get('side', 'N/A')
                size = float(trade.get('size', 0))
                price = float(trade.get('price', 0))
                value = size * price
                timestamp = trade.get('created_at', trade.get('timestamp', 'N/A'))

                side_emoji = "🟢" if side == "BUY" else "🔴"
                text += f"{side_emoji} {side} ${value:.2f} @ {price:.2f}\n"

            if total_trades > 10:
                text += f"\n_...and {total_trades - 10} more trades_"
        else:
            text += "📭 No trades attributed yet.\n\n_Place a trade to see it here._"

        text += "\n\n🔗 [View on Polymarket](https://polymarket.com/settings?tab=builder)"

    except Exception as e:
        logger.error(f"Failed to fetch builder stats: {e}")
        text = (
            "🏗️ *Builder Stats*\n\n"
            "❌ Failed to fetch builder trades.\n\n"
            f"Error: `{str(e)[:100]}`\n\n"
            "Try again later or check your credentials."
        )

    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_builder_refresh")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_menu")],
    ]

    if query:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    return AdminState.BUILDER_STATS


@admin_only
async def refresh_builder_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Refresh builder stats."""
    return await show_builder_stats(update, context)

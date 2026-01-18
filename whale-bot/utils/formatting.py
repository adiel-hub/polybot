"""Message formatting utilities."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from monitors.whale_monitor import WhaleTrade

logger = logging.getLogger(__name__)

# Shared mapping file for short ID -> condition ID
# Located in polybot/data/ so both whale-bot and polybot can access it
SHORT_ID_MAP_FILE = Path(__file__).parent.parent.parent / "data" / "short_id_map.json"


def generate_short_id(condition_id: str, length: int = 8) -> str:
    """
    Generate a short, URL-friendly ID from a condition_id.
    Same algorithm as PolyBot for compatibility.
    """
    clean_id = condition_id.lower()
    if clean_id.startswith("0x"):
        clean_id = clean_id[2:]

    hash_obj = hashlib.sha256(clean_id.encode())
    hash_hex = hash_obj.hexdigest()

    return hash_hex[:length]


def save_short_id_mapping(short_id: str, condition_id: str) -> None:
    """
    Save a short ID -> condition ID mapping to the shared file.
    This allows PolyBot to resolve short IDs from whale alerts.
    """
    try:
        SHORT_ID_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Load existing mappings
        mappings = {}
        if SHORT_ID_MAP_FILE.exists():
            with open(SHORT_ID_MAP_FILE, "r") as f:
                mappings = json.load(f)

        # Add new mapping
        mappings[short_id] = condition_id

        # Keep only last 1000 mappings to prevent unbounded growth
        if len(mappings) > 1000:
            # Keep most recent entries (dict maintains insertion order in Python 3.7+)
            mappings = dict(list(mappings.items())[-1000:])

        # Save back
        with open(SHORT_ID_MAP_FILE, "w") as f:
            json.dump(mappings, f)

        logger.debug(f"Saved short ID mapping: {short_id} -> {condition_id[:20]}...")
    except Exception as e:
        logger.error(f"Failed to save short ID mapping: {e}")


def shorten_address(address: str, chars: int = 6) -> str:
    """Shorten an Ethereum address for display."""
    if not address or len(address) < 12:
        return address or "Unknown"
    return f"{address[:chars]}...{address[-4:]}"


def format_whale_alert(
    trade: WhaleTrade,
    polybot_username: Optional[str] = None,
) -> str:
    """
    Format a whale trade into a Telegram message.

    Args:
        trade: The whale trade data
        polybot_username: PolyBot username for deep links (optional)

    Returns:
        Formatted message string
    """
    # Format timestamp
    timestamp_str = trade.timestamp.strftime("%Y-%m-%d • %H:%M:%S")

    # Determine side emoji and text
    if trade.side.upper() == "BUY":
        side_emoji = "📈"
        side_text = "BUYING"
    else:
        side_emoji = "📉"
        side_text = "SELLING"

    # Format price as percentage
    price_pct = trade.price * 100

    # Trader display name
    trader_display = trade.trader_name or shorten_address(trade.trader_address)

    # Build the message
    message = (
        f"🐋 *WHALE ALERT* on Polymarket\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *MARKET:*\n"
        f"_{trade.market_title}_\n\n"
        f"🎯 *POSITION:*\n"
        f"{side_emoji} {side_text} \"{trade.outcome}\" @ {price_pct:.0f}%\n\n"
        f"💰 *VALUE:* `${trade.value:,.2f}`\n"
        f"📦 *SIZE:* {trade.size:,.0f} contracts\n\n"
        f"👤 *TRADER:*\n"
        f"`{trade.trader_address}`"
    )

    # Add trader name if available and different from address
    # Skip if trader_name contains the address (sometimes API returns address as name)
    if trade.trader_name:
        # Normalize for comparison (case-insensitive, check if address is contained)
        name_lower = trade.trader_name.lower()
        addr_lower = trade.trader_address.lower() if trade.trader_address else ""
        # Skip if name contains address or address contains name (avoid duplicates)
        if addr_lower not in name_lower and name_lower not in addr_lower:
            message += f"\n({trade.trader_name})"

    message += f"\n\n⏰ {timestamp_str}"

    return message


def create_deep_link(condition_id: str, bot_username: str) -> str:
    """
    Create a PolyBot deep link for a market.

    Args:
        condition_id: Market condition ID
        bot_username: PolyBot's Telegram username

    Returns:
        Deep link URL
    """
    short_id = generate_short_id(condition_id)

    # Save the mapping so PolyBot can resolve the short ID
    save_short_id_mapping(short_id, condition_id)

    return f"https://t.me/{bot_username}?start=m_{short_id}"


def format_amount(amount: float) -> str:
    """Format a USD amount with commas and 2 decimal places."""
    return f"${amount:,.2f}"

"""Admin display formatters."""

from datetime import datetime
from typing import Optional


def format_number(value: float, decimals: int = 2) -> str:
    """Format a number with commas and decimals."""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.2f}K"
    else:
        return f"${value:.{decimals}f}"


def format_pnl(value: float) -> str:
    """Format P&L with color indicator."""
    if value > 0:
        return f"+${value:.2f}"
    elif value < 0:
        return f"-${abs(value):.2f}"
    else:
        return "$0.00"


def format_pnl_emoji(value: float) -> str:
    """Format P&L with emoji indicator."""
    if value > 0:
        return f"📈 +${value:.2f}"
    elif value < 0:
        return f"📉 -${abs(value):.2f}"
    else:
        return "➖ $0.00"


def format_datetime(dt: Optional[datetime | str]) -> str:
    """Format datetime for display."""
    if not dt:
        return "N/A"
    # Handle string datetime from SQLite
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt[:16] if len(dt) >= 16 else dt
    return dt.strftime("%Y-%m-%d %H:%M")


def format_user_summary(user, wallet=None) -> str:
    """Format user info for admin display."""
    status = "✅ Active" if user.is_active else "⛔ Suspended"
    username = f"@{user.telegram_username}" if user.telegram_username else "No username"
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "No name"

    text = (
        f"👤 *User #{user.id}*\n"
        f"├ Telegram ID: `{user.telegram_id}`\n"
        f"├ Username: {username}\n"
        f"├ Name: {name}\n"
        f"├ Status: {status}\n"
        f"├ Registered: {format_datetime(user.created_at)}\n"
    )

    if wallet:
        text += (
            f"├ 💰 Balance: ${wallet.usdc_balance:.2f}\n"
            f"└ 📍 Wallet: `{wallet.address[:10]}...{wallet.address[-6:]}`"
        )
    else:
        text += "└ 💰 No wallet"

    return text


def format_order_summary(order) -> str:
    """Format order info for admin display."""
    status_emoji = {
        "PENDING": "⏳",
        "OPEN": "📋",
        "PARTIALLY_FILLED": "📊",
        "FILLED": "✅",
        "CANCELLED": "❌",
        "FAILED": "🚫",
    }
    emoji = status_emoji.get(order.status.name, "❓")

    return (
        f"{emoji} *Order #{order.id}*\n"
        f"├ User ID: {order.user_id}\n"
        f"├ Market: {order.market_question[:40]}...\n"
        f"├ Side: {order.side.name} {order.outcome.name}\n"
        f"├ Type: {order.order_type.name}\n"
        f"├ Size: {order.size:.2f} @ ${order.price or 'Market'}\n"
        f"├ Filled: {order.filled_size:.2f}\n"
        f"├ Status: {order.status.name}\n"
        f"└ Created: {format_datetime(order.created_at)}"
    )


def format_position_summary(position) -> str:
    """Format position info for admin display."""
    pnl = position.unrealized_pnl or 0
    pnl_text = format_pnl_emoji(pnl)

    return (
        f"🎯 *Position #{position.id}*\n"
        f"├ User ID: {position.user_id}\n"
        f"├ Market: {position.market_question[:40]}...\n"
        f"├ Outcome: {position.outcome}\n"
        f"├ Size: {position.size:.2f}\n"
        f"├ Avg Entry: ${position.average_entry_price:.4f}\n"
        f"├ Current: ${position.current_price or 0:.4f}\n"
        f"├ P&L: {pnl_text}\n"
        f"└ Opened: {format_datetime(position.created_at)}"
    )


def format_wallet_summary(wallet, user=None) -> str:
    """Format wallet info for admin display."""
    text = (
        f"💰 *Wallet #{wallet.id}*\n"
        f"├ Address: `{wallet.address}`\n"
        f"├ Balance: ${wallet.usdc_balance:.2f}\n"
        f"├ Last Check: {format_datetime(wallet.last_balance_check)}\n"
    )

    if user:
        username = f"@{user.telegram_username}" if user.telegram_username else "No username"
        text += f"└ Owner: User #{user.id} ({username})"
    else:
        text += f"└ User ID: {wallet.user_id}"

    return text


def format_stop_loss_summary(stop_loss, position=None) -> str:
    """Format stop loss info for admin display."""
    status = "🟢 Active" if stop_loss.is_active else "🔴 Inactive"

    text = (
        f"🛑 *Stop Loss #{stop_loss.id}*\n"
        f"├ User ID: {stop_loss.user_id}\n"
        f"├ Position ID: {stop_loss.position_id}\n"
        f"├ Trigger Price: ${stop_loss.trigger_price:.4f}\n"
        f"├ Sell %: {stop_loss.sell_percentage:.0f}%\n"
        f"├ Status: {status}\n"
        f"└ Created: {format_datetime(stop_loss.created_at)}"
    )

    return text


def format_copy_trader_summary(subscription) -> str:
    """Format copy trader subscription for admin display."""
    status = "🟢 Active" if subscription.is_active else "🔴 Paused"
    pnl_text = format_pnl_emoji(subscription.total_pnl)

    return (
        f"👥 *Subscription #{subscription.id}*\n"
        f"├ Follower: User #{subscription.user_id}\n"
        f"├ Trader: `{subscription.trader_address[:10]}...`\n"
        f"├ Name: {subscription.trader_name or 'Unknown'}\n"
        f"├ Allocation: {subscription.allocation:.0f}%\n"
        f"├ Max Trade: ${subscription.max_trade_size or 'No limit'}\n"
        f"├ Trades Copied: {subscription.total_trades_copied}\n"
        f"├ P&L: {pnl_text}\n"
        f"├ Status: {status}\n"
        f"└ Started: {format_datetime(subscription.created_at)}"
    )

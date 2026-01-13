"""Formatting utilities for bot messages."""


def format_price(price: float) -> str:
    """Format price as cents."""
    cents = price * 100
    return f"{cents:.1f}c"


def format_amount(amount: float) -> str:
    """Format dollar amount."""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"${amount / 1_000:.1f}K"
    else:
        return f"${amount:.2f}"


def format_pnl(pnl: float) -> str:
    """Format profit/loss with sign."""
    sign = "+" if pnl >= 0 else ""
    return f"{sign}${pnl:.2f}"


def format_percentage(value: float) -> str:
    """Format as percentage."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def format_address(address: str) -> str:
    """Format wallet address (shortened)."""
    return f"{address[:6]}...{address[-4:]}"


def format_tx_hash(tx_hash: str) -> str:
    """Format transaction hash (shortened)."""
    return f"{tx_hash[:10]}...{tx_hash[-6:]}"

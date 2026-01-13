"""Input validation utilities."""

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from config.constants import MIN_PRICE, MAX_PRICE, MIN_WITHDRAWAL, MAX_WITHDRAWAL


def validate_amount(
    text: str,
    min_val: float = 0.01,
    max_val: float = 100000,
) -> Optional[float]:
    """
    Validate and sanitize amount input.

    Args:
        text: Input text
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Validated amount or None if invalid
    """
    try:
        # Use Decimal for precision
        amount = Decimal(text.strip())

        if amount < Decimal(str(min_val)):
            return None
        if amount > Decimal(str(max_val)):
            return None

        return float(amount)

    except (InvalidOperation, ValueError):
        return None


def validate_price(text: str) -> Optional[float]:
    """
    Validate limit price (1-99 cents).

    Args:
        text: Input text (can be in cents like "45" or decimal like "0.45")

    Returns:
        Validated price as decimal (0.01-0.99) or None if invalid
    """
    try:
        value = float(text.strip())

        # If value > 1, assume it's in cents
        if value > 1:
            value = value / 100

        if value < MIN_PRICE or value > MAX_PRICE:
            return None

        return value

    except (ValueError, TypeError):
        return None


def validate_address(address: str) -> Optional[str]:
    """
    Validate Ethereum/Polygon address.

    Args:
        address: Address string

    Returns:
        Validated address (lowercase) or None if invalid
    """
    address = address.strip()

    # Check format
    if not re.match(r"^0x[a-fA-F0-9]{40}$", address):
        return None

    return address.lower()


def validate_percentage(text: str, min_val: float = 1, max_val: float = 100) -> Optional[float]:
    """
    Validate percentage input.

    Args:
        text: Input text
        min_val: Minimum percentage
        max_val: Maximum percentage

    Returns:
        Validated percentage or None if invalid
    """
    try:
        value = float(text.strip())

        if value < min_val or value > max_val:
            return None

        return value

    except (ValueError, TypeError):
        return None


def validate_withdrawal_amount(text: str, balance: float) -> Optional[float]:
    """
    Validate withdrawal amount.

    Args:
        text: Input text
        balance: Available balance

    Returns:
        Validated amount or None if invalid
    """
    amount = validate_amount(text, min_val=MIN_WITHDRAWAL, max_val=MAX_WITHDRAWAL)

    if amount is None:
        return None

    if amount > balance:
        return None

    return amount

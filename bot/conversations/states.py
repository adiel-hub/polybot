"""Conversation states for the bot."""

from enum import IntEnum, auto


class ConversationState(IntEnum):
    """Conversation states for multi-step interactions."""

    # Registration flow
    LICENSE_PROMPT = auto()

    # Main menu
    MAIN_MENU = auto()

    # Market browsing
    BROWSE_CATEGORY = auto()
    BROWSE_RESULTS = auto()
    MARKET_DETAIL = auto()
    SEARCH_INPUT = auto()

    # Trading flow
    SELECT_OUTCOME = auto()
    SELECT_ORDER_TYPE = auto()
    ENTER_AMOUNT = auto()
    ENTER_PRICE = auto()
    CONFIRM_ORDER = auto()

    # Stop loss flow
    SELECT_POSITION = auto()
    ENTER_TRIGGER_PRICE = auto()
    ENTER_SELL_PERCENTAGE = auto()
    CONFIRM_STOP_LOSS = auto()

    # Wallet flow
    WALLET_MENU = auto()
    WITHDRAW_AMOUNT = auto()
    WITHDRAW_ADDRESS = auto()
    CONFIRM_WITHDRAW = auto()

    # Copy trading flow
    COPY_TRADING_MENU = auto()
    SELECT_TRADER = auto()
    ENTER_ALLOCATION = auto()
    CONFIRM_COPY = auto()

    # Settings
    SETTINGS_MENU = auto()
    SETTINGS_FAST_THRESHOLD = auto()
    SETTINGS_QUICKBUY_EDIT = auto()
    SETTINGS_EXPORT_KEY = auto()

    # Orders
    ORDERS_LIST = auto()

    # Portfolio
    PORTFOLIO_VIEW = auto()

    # Sell position flow
    SELL_AMOUNT = auto()
    CONFIRM_SELL = auto()

    # Two-Factor Authentication
    TWO_FA_SETUP = auto()
    TWO_FA_VERIFY = auto()

    # Group features
    GROUP_SETUP = auto()
    GROUP_SETTINGS = auto()

    # Referral program
    REFERRAL_MENU = auto()
    REFERRAL_CLAIM = auto()
    REFERRAL_QR = auto()

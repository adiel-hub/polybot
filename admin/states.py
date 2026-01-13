"""Admin conversation states."""

from enum import IntEnum, auto


class AdminState(IntEnum):
    """Conversation states for admin panel."""

    # Main menu
    ADMIN_MENU = auto()

    # Dashboard
    DASHBOARD = auto()

    # User management
    USER_LIST = auto()
    USER_DETAIL = auto()
    USER_SEARCH = auto()
    USER_CONFIRM_ACTION = auto()

    # Order management
    ORDER_LIST = auto()
    ORDER_DETAIL = auto()
    ORDER_CONFIRM_CANCEL = auto()

    # Position management
    POSITION_LIST = auto()
    POSITION_DETAIL = auto()

    # Stop loss management
    STOP_LOSS_LIST = auto()

    # Copy trading management
    COPY_TRADING_LIST = auto()
    TRADER_DETAIL = auto()

    # Wallet/Financial management
    WALLET_LIST = auto()
    DEPOSIT_LIST = auto()
    WITHDRAWAL_LIST = auto()

    # System monitoring
    SYSTEM_MONITOR = auto()

    # Settings
    SYSTEM_SETTINGS = auto()
    SETTINGS_EDIT = auto()

    # Broadcast
    BROADCAST_MENU = auto()
    BROADCAST_COMPOSE = auto()
    BROADCAST_COMPOSE_TEXT = auto()
    BROADCAST_COMPOSE_IMAGE = auto()
    BROADCAST_ADD_BUTTONS = auto()
    BROADCAST_BUTTON_INPUT = auto()
    BROADCAST_CONFIRM = auto()

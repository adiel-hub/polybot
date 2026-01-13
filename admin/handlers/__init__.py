"""Admin handlers."""

from admin.handlers.start import admin_command, show_admin_menu
from admin.handlers.dashboard import show_dashboard, refresh_dashboard
from admin.handlers.users import (
    show_user_list,
    show_user_detail,
    prompt_user_search,
    handle_user_search,
    suspend_user,
    activate_user,
)
from admin.handlers.orders import (
    show_order_list,
    show_order_detail,
    handle_order_filter,
    cancel_order,
)
from admin.handlers.positions import show_position_list, show_position_detail
from admin.handlers.stop_loss import show_stop_loss_list, deactivate_stop_loss
from admin.handlers.copy_trading import (
    show_copy_trading_list,
    show_trader_detail,
    deactivate_subscription,
)
from admin.handlers.wallets import (
    show_wallet_list,
    show_deposit_list,
    show_withdrawal_list,
)
from admin.handlers.system import show_system_monitor, check_component_status
from admin.handlers.settings import show_settings, handle_setting_toggle
from admin.handlers.broadcast import (
    show_broadcast_menu,
    prompt_broadcast_compose,
    handle_broadcast_message,
    confirm_broadcast,
    send_broadcast,
)

__all__ = [
    "admin_command",
    "show_admin_menu",
    "show_dashboard",
    "refresh_dashboard",
    "show_user_list",
    "show_user_detail",
    "prompt_user_search",
    "handle_user_search",
    "suspend_user",
    "activate_user",
    "show_order_list",
    "show_order_detail",
    "handle_order_filter",
    "cancel_order",
    "show_position_list",
    "show_position_detail",
    "show_stop_loss_list",
    "deactivate_stop_loss",
    "show_copy_trading_list",
    "show_trader_detail",
    "deactivate_subscription",
    "show_wallet_list",
    "show_deposit_list",
    "show_withdrawal_list",
    "show_system_monitor",
    "check_component_status",
    "show_settings",
    "handle_setting_toggle",
    "show_broadcast_menu",
    "prompt_broadcast_compose",
    "handle_broadcast_message",
    "confirm_broadcast",
    "send_broadcast",
]

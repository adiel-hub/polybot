"""Admin panel ConversationHandler factory."""

import logging
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from admin.states import AdminState
from admin.handlers.start import admin_command, show_admin_menu, close_admin_panel
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
from admin.handlers.stop_loss import (
    show_stop_loss_list,
    show_stop_loss_detail,
    deactivate_stop_loss,
)
from admin.handlers.copy_trading import (
    show_copy_trading_list,
    show_trader_detail,
    deactivate_subscription,
)
from admin.handlers.wallets import (
    show_wallet_list,
    show_wallets,
    show_wallet_detail,
    show_deposit_list,
    show_withdrawal_list,
)
from admin.handlers.system import show_system_monitor, check_component_status
from admin.handlers.builder import show_builder_stats, refresh_builder_stats
from admin.handlers.settings import show_settings, handle_setting_toggle
from admin.handlers.broadcast import (
    show_broadcast_menu,
    prompt_broadcast_compose,
    handle_broadcast_type,
    handle_broadcast_text,
    handle_broadcast_image,
    prompt_add_buttons,
    prompt_button_details,
    handle_button_input,
    confirm_broadcast,
    send_broadcast,
)

logger = logging.getLogger(__name__)


def create_admin_handler() -> ConversationHandler:
    """Create the admin panel ConversationHandler."""

    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_command),
        ],
        states={
            # Main menu
            AdminState.ADMIN_MENU: [
                CallbackQueryHandler(show_dashboard, pattern="^admin_dashboard$"),
                CallbackQueryHandler(show_user_list, pattern="^admin_users$"),
                CallbackQueryHandler(show_order_list, pattern="^admin_orders$"),
                CallbackQueryHandler(show_position_list, pattern="^admin_positions$"),
                CallbackQueryHandler(show_stop_loss_list, pattern="^admin_stoploss$"),
                CallbackQueryHandler(show_copy_trading_list, pattern="^admin_copy$"),
                CallbackQueryHandler(show_wallet_list, pattern="^admin_wallets$"),
                CallbackQueryHandler(show_system_monitor, pattern="^admin_system$"),
                CallbackQueryHandler(show_settings, pattern="^admin_settings$"),
                CallbackQueryHandler(show_builder_stats, pattern="^admin_builder$"),
                CallbackQueryHandler(show_broadcast_menu, pattern="^admin_broadcast$"),
                CallbackQueryHandler(close_admin_panel, pattern="^admin_close$"),
            ],
            # Dashboard
            AdminState.DASHBOARD: [
                CallbackQueryHandler(refresh_dashboard, pattern="^admin_dashboard_refresh$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            # User management
            AdminState.USER_LIST: [
                CallbackQueryHandler(show_user_detail, pattern=r"^admin_user_\d+$"),
                CallbackQueryHandler(prompt_user_search, pattern="^admin_user_search$"),
                CallbackQueryHandler(show_user_list, pattern=r"^admin_users_page_\d+$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            AdminState.USER_DETAIL: [
                CallbackQueryHandler(suspend_user, pattern=r"^admin_suspend_\d+$"),
                CallbackQueryHandler(activate_user, pattern=r"^admin_activate_\d+$"),
                CallbackQueryHandler(show_order_list, pattern=r"^admin_user_orders_\d+$"),
                CallbackQueryHandler(show_position_list, pattern=r"^admin_user_positions_\d+$"),
                CallbackQueryHandler(show_user_list, pattern="^admin_users$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            AdminState.USER_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_search),
                CallbackQueryHandler(show_user_list, pattern="^admin_users$"),
            ],
            # Order management
            AdminState.ORDER_LIST: [
                CallbackQueryHandler(show_order_detail, pattern=r"^admin_order_\d+$"),
                CallbackQueryHandler(handle_order_filter, pattern=r"^admin_orders_filter_"),
                CallbackQueryHandler(show_order_list, pattern=r"^admin_orders_page_\d+$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
                CallbackQueryHandler(lambda u, c: None, pattern="^noop$"),
            ],
            AdminState.ORDER_DETAIL: [
                CallbackQueryHandler(cancel_order, pattern=r"^admin_cancel_order_\d+$"),
                CallbackQueryHandler(show_user_detail, pattern=r"^admin_user_\d+$"),
                CallbackQueryHandler(show_order_list, pattern="^admin_orders$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            # Position management
            AdminState.POSITION_LIST: [
                CallbackQueryHandler(show_position_detail, pattern=r"^admin_position_\d+$"),
                CallbackQueryHandler(show_position_list, pattern=r"^admin_positions_page_\d+$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
                CallbackQueryHandler(lambda u, c: None, pattern="^noop$"),
            ],
            AdminState.POSITION_DETAIL: [
                CallbackQueryHandler(show_user_detail, pattern=r"^admin_user_\d+$"),
                CallbackQueryHandler(show_position_list, pattern="^admin_positions$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            # Stop loss management
            AdminState.STOP_LOSS_LIST: [
                CallbackQueryHandler(show_stop_loss_detail, pattern=r"^admin_sl_\d+$"),
                CallbackQueryHandler(deactivate_stop_loss, pattern=r"^admin_sl_deactivate_\d+$"),
                CallbackQueryHandler(show_stop_loss_list, pattern=r"^admin_stoploss_page_\d+$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
                CallbackQueryHandler(lambda u, c: None, pattern="^noop$"),
            ],
            # Copy trading management
            AdminState.COPY_TRADING_LIST: [
                CallbackQueryHandler(show_trader_detail, pattern=r"^admin_copy_sub_\d+$"),
                CallbackQueryHandler(show_copy_trading_list, pattern=r"^admin_copy_page_\d+$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
                CallbackQueryHandler(lambda u, c: None, pattern="^noop$"),
            ],
            AdminState.TRADER_DETAIL: [
                CallbackQueryHandler(
                    deactivate_subscription, pattern=r"^admin_copy_deactivate_\d+$"
                ),
                CallbackQueryHandler(show_user_detail, pattern=r"^admin_user_\d+$"),
                CallbackQueryHandler(show_copy_trading_list, pattern="^admin_copy$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            # Wallet/Financial management
            AdminState.WALLET_LIST: [
                CallbackQueryHandler(show_wallets, pattern="^admin_wallets_list$"),
                CallbackQueryHandler(show_wallets, pattern=r"^admin_wallets_list_page_\d+$"),
                CallbackQueryHandler(show_wallet_detail, pattern=r"^admin_wallet_\d+$"),
                CallbackQueryHandler(show_deposit_list, pattern="^admin_deposits$"),
                CallbackQueryHandler(show_withdrawal_list, pattern="^admin_withdrawals$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
                CallbackQueryHandler(lambda u, c: None, pattern="^noop$"),
            ],
            AdminState.WALLET_DETAIL: [
                CallbackQueryHandler(show_user_detail, pattern=r"^admin_user_\d+$"),
                CallbackQueryHandler(show_wallets, pattern="^admin_wallets_list$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            AdminState.DEPOSIT_LIST: [
                CallbackQueryHandler(show_deposit_list, pattern=r"^admin_deposits_page_\d+$"),
                CallbackQueryHandler(show_wallet_list, pattern="^admin_wallets$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
                CallbackQueryHandler(lambda u, c: None, pattern="^noop$"),
            ],
            AdminState.WITHDRAWAL_LIST: [
                CallbackQueryHandler(show_withdrawal_list, pattern=r"^admin_withdrawals_page_\d+$"),
                CallbackQueryHandler(show_wallet_list, pattern="^admin_wallets$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
                CallbackQueryHandler(lambda u, c: None, pattern="^noop$"),
            ],
            # Builder stats
            AdminState.BUILDER_STATS: [
                CallbackQueryHandler(refresh_builder_stats, pattern="^admin_builder_refresh$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            # System monitoring
            AdminState.SYSTEM_MONITOR: [
                CallbackQueryHandler(check_component_status, pattern="^admin_system_refresh$"),
                CallbackQueryHandler(check_component_status, pattern="^admin_check_ws$"),
                CallbackQueryHandler(check_component_status, pattern="^admin_check_apis$"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            # Settings
            AdminState.SYSTEM_SETTINGS: [
                CallbackQueryHandler(handle_setting_toggle, pattern=r"^admin_setting_toggle_"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            # Broadcast
            AdminState.BROADCAST_MENU: [
                CallbackQueryHandler(prompt_broadcast_compose, pattern=r"^admin_broadcast_"),
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
            ],
            AdminState.BROADCAST_COMPOSE: [
                CallbackQueryHandler(handle_broadcast_type, pattern=r"^admin_broadcast_type_"),
                CallbackQueryHandler(show_broadcast_menu, pattern="^admin_broadcast$"),
            ],
            AdminState.BROADCAST_COMPOSE_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_text),
                CallbackQueryHandler(show_broadcast_menu, pattern="^admin_broadcast$"),
            ],
            AdminState.BROADCAST_COMPOSE_IMAGE: [
                MessageHandler(filters.PHOTO, handle_broadcast_image),
                CallbackQueryHandler(show_broadcast_menu, pattern="^admin_broadcast$"),
            ],
            AdminState.BROADCAST_ADD_BUTTONS: [
                CallbackQueryHandler(prompt_button_details, pattern="^admin_broadcast_add_button$"),
                CallbackQueryHandler(confirm_broadcast, pattern="^admin_broadcast_confirm_preview$"),
                CallbackQueryHandler(show_broadcast_menu, pattern="^admin_broadcast$"),
            ],
            AdminState.BROADCAST_BUTTON_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_input),
                CallbackQueryHandler(prompt_add_buttons, pattern="^admin_broadcast_buttons_back$"),
            ],
            AdminState.BROADCAST_CONFIRM: [
                CallbackQueryHandler(send_broadcast, pattern="^admin_broadcast_send$"),
                CallbackQueryHandler(prompt_broadcast_compose, pattern=r"^admin_broadcast_"),
                CallbackQueryHandler(show_broadcast_menu, pattern="^admin_broadcast$"),
            ],
        },
        fallbacks=[
            CommandHandler("admin", admin_command),
            CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
        ],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
        name="admin_handler",
    )

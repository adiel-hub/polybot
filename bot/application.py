"""Bot application factory."""

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

from config import settings
from database.connection import Database
from core.wallet import KeyEncryption
from services import UserService, TradingService, MarketService
from services.referral_service import ReferralService

from bot.conversations.states import ConversationState
from bot.handlers.start import start_command, license_accept, license_decline
from bot.handlers.menu import show_main_menu, handle_menu_callback
from bot.handlers.markets import (
    show_browse_menu,
    handle_browse_callback,
    show_market_detail,
    handle_search_input,
)
from bot.handlers.trading import (
    handle_trade_callback,
    handle_amount_input,
    handle_price_input,
    confirm_order,
    handle_sell_position,
    handle_sell_percentage,
    handle_sell_amount_input,
    confirm_sell,
)
from bot.handlers.wallet import (
    show_wallet,
    handle_wallet_callback,
    handle_withdraw_amount,
    handle_withdraw_address,
    confirm_withdraw,
)
from bot.handlers.portfolio import show_portfolio, handle_position_callback
from bot.handlers.orders import show_orders, handle_cancel_order
from bot.handlers.copy_trading import (
    show_copy_trading,
    handle_copy_callback,
    handle_allocation_input,
    confirm_copy,
)
from bot.handlers.stop_loss import (
    show_stop_loss_menu,
    handle_stop_loss_callback,
    handle_trigger_price_input,
    handle_sell_percentage_input,
    confirm_stop_loss,
)
from bot.handlers.settings import (
    show_settings_menu,
    handle_settings_callback,
    handle_settings_input,
)
from bot.handlers.two_factor import (
    show_2fa_intro,
    handle_2fa_continue,
    handle_2fa_verify,
    verify_2fa_for_action,
)
from bot.handlers.referral import (
    show_referral_menu,
    handle_claim_earnings,
    handle_create_qr,
    handle_add_to_group,
)

# Admin panel
from admin import create_admin_handler

logger = logging.getLogger(__name__)


async def create_application(db: Database) -> Application:
    """Create and configure the bot application."""

    # Initialize services
    encryption = KeyEncryption(settings.master_encryption_key)
    user_service = UserService(db, encryption)
    trading_service = TradingService(db, encryption)
    market_service = MarketService()
    referral_service = ReferralService(db)

    # Initialize market categories
    await market_service.initialize_categories()

    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Store dependencies in bot_data
    application.bot_data["db"] = db
    application.bot_data["encryption"] = encryption
    application.bot_data["user_service"] = user_service
    application.bot_data["trading_service"] = trading_service
    application.bot_data["market_service"] = market_service
    application.bot_data["referral_service"] = referral_service

    # Main conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            CommandHandler("menu", show_main_menu),
        ],
        states={
            # License flow
            ConversationState.LICENSE_PROMPT: [
                CallbackQueryHandler(license_accept, pattern="^license_accept$"),
                CallbackQueryHandler(license_decline, pattern="^license_decline$"),
            ],

            # Main menu
            ConversationState.MAIN_MENU: [
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^noop$"),
            ],

            # Market browsing
            ConversationState.BROWSE_CATEGORY: [
                CallbackQueryHandler(handle_browse_callback, pattern="^browse_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_input),
            ],
            ConversationState.BROWSE_RESULTS: [
                CallbackQueryHandler(show_market_detail, pattern="^market_"),
                CallbackQueryHandler(handle_browse_callback, pattern="^browse_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_input),
            ],

            # Market detail and trading
            ConversationState.MARKET_DETAIL: [
                CallbackQueryHandler(handle_trade_callback, pattern="^trade_"),
                CallbackQueryHandler(show_market_detail, pattern="^market_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.ENTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount_input),
                CallbackQueryHandler(show_market_detail, pattern="^market_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.ENTER_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price_input),
                CallbackQueryHandler(show_market_detail, pattern="^market_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.CONFIRM_ORDER: [
                CallbackQueryHandler(confirm_order, pattern="^order_confirm$"),
                CallbackQueryHandler(show_market_detail, pattern="^market_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],

            # Wallet
            ConversationState.WALLET_MENU: [
                CallbackQueryHandler(handle_wallet_callback, pattern="^wallet_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.WITHDRAW_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.WITHDRAW_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_address),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.CONFIRM_WITHDRAW: [
                CallbackQueryHandler(confirm_withdraw, pattern="^withdraw_confirm$"),
                CallbackQueryHandler(handle_wallet_callback, pattern="^wallet_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],

            # Portfolio
            ConversationState.PORTFOLIO_VIEW: [
                CallbackQueryHandler(handle_position_callback, pattern="^position_"),
                CallbackQueryHandler(handle_sell_position, pattern="^sell_position_"),
                CallbackQueryHandler(handle_stop_loss_callback, pattern="^stoploss_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],

            # Sell position flow
            ConversationState.SELL_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_sell_amount_input),
                CallbackQueryHandler(handle_sell_percentage, pattern="^sell_pct_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.CONFIRM_SELL: [
                CallbackQueryHandler(confirm_sell, pattern="^sell_confirm$"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],

            # Orders
            ConversationState.ORDERS_LIST: [
                CallbackQueryHandler(handle_cancel_order, pattern="^cancel_order_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],

            # Copy trading
            ConversationState.COPY_TRADING_MENU: [
                CallbackQueryHandler(handle_copy_callback, pattern="^copy_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.SELECT_TRADER: [
                CallbackQueryHandler(handle_copy_callback, pattern="^copy_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.ENTER_ALLOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_allocation_input),
                CallbackQueryHandler(handle_copy_callback, pattern="^copy_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.CONFIRM_COPY: [
                CallbackQueryHandler(confirm_copy, pattern="^copy_confirm$"),
                CallbackQueryHandler(handle_copy_callback, pattern="^copy_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],

            # Stop loss
            ConversationState.SELECT_POSITION: [
                CallbackQueryHandler(handle_stop_loss_callback, pattern="^sl_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.ENTER_TRIGGER_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trigger_price_input),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.ENTER_SELL_PERCENTAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_sell_percentage_input),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.CONFIRM_STOP_LOSS: [
                CallbackQueryHandler(confirm_stop_loss, pattern="^sl_confirm$"),
                CallbackQueryHandler(handle_stop_loss_callback, pattern="^sl_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],

            # Settings
            ConversationState.SETTINGS_MENU: [
                CallbackQueryHandler(handle_settings_callback, pattern="^settings_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
                CallbackQueryHandler(handle_settings_callback, pattern="^noop$"),
            ],
            ConversationState.SETTINGS_FAST_THRESHOLD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_settings_input),
                CallbackQueryHandler(handle_settings_callback, pattern="^settings_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.SETTINGS_QUICKBUY_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_settings_input),
                CallbackQueryHandler(handle_settings_callback, pattern="^settings_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.SETTINGS_EXPORT_KEY: [
                CallbackQueryHandler(handle_settings_callback, pattern="^settings_"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],

            # Two-Factor Authentication
            ConversationState.TWO_FA_SETUP: [
                CallbackQueryHandler(handle_2fa_continue, pattern="^2fa_continue$"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.TWO_FA_VERIFY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_2fa_verify),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],

            # Referral program
            ConversationState.REFERRAL_MENU: [
                CallbackQueryHandler(handle_claim_earnings, pattern="^ref_claim$"),
                CallbackQueryHandler(handle_create_qr, pattern="^ref_qr$"),
                CallbackQueryHandler(handle_add_to_group, pattern="^ref_group$"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
                CallbackQueryHandler(show_referral_menu, pattern="^noop$"),
            ],
            ConversationState.REFERRAL_CLAIM: [
                CallbackQueryHandler(show_referral_menu, pattern="^menu_rewards$"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
            ConversationState.REFERRAL_QR: [
                CallbackQueryHandler(show_referral_menu, pattern="^menu_rewards$"),
                CallbackQueryHandler(handle_menu_callback, pattern="^menu_"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CommandHandler("menu", show_main_menu),
            CallbackQueryHandler(handle_menu_callback, pattern="^menu_main$"),
        ],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )

    application.add_handler(conv_handler)

    # Add standalone command handlers
    application.add_handler(CommandHandler("wallet", show_wallet))
    application.add_handler(CommandHandler("portfolio", show_portfolio))
    application.add_handler(CommandHandler("orders", show_orders))

    # Add admin panel handler
    admin_handler = create_admin_handler()
    application.add_handler(admin_handler)

    logger.info("Bot application configured with all handlers (including admin panel)")

    return application

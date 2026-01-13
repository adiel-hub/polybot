"""Settings handler for user preferences."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.conversations.states import ConversationState
from services import UserService

logger = logging.getLogger(__name__)


def build_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Build the settings menu keyboard."""
    trading_mode = settings.get("trading_mode", "standard")
    threshold = settings.get("fast_mode_threshold", 100.0)
    presets = settings.get("quickbuy_presets", [10, 25, 50])
    auto_claim = settings.get("auto_claim", False)
    auto_preset = settings.get("auto_apply_preset", False)
    two_fa = settings.get("two_factor_enabled", False)

    keyboard = [
        # Section header - Trading Mode
        [InlineKeyboardButton("🚀 —— TRADING MODE ——", callback_data="noop")],
        # Trading mode buttons
        [
            InlineKeyboardButton(
                f"{'✅ ' if trading_mode == 'standard' else ''}🐢 Standard",
                callback_data="settings_mode_standard",
            ),
            InlineKeyboardButton(
                f"{'✅ ' if trading_mode == 'fast' else ''}⚡ Fast",
                callback_data="settings_mode_fast",
            ),
            InlineKeyboardButton(
                f"{'✅ ' if trading_mode == 'ludicrous' else ''}🚀 Ludicrous",
                callback_data="settings_mode_ludicrous",
            ),
        ],
        # Fast mode threshold
        [
            InlineKeyboardButton(
                f"✏️ Fast Mode Threshold: ${threshold:.2f}",
                callback_data="settings_threshold",
            )
        ],
        # Section header - Quickbuy Presets
        [InlineKeyboardButton("💵 —— QUICKBUY PRESETS ——", callback_data="noop")],
        # Preset buttons
        [
            InlineKeyboardButton(
                f"✏️ ${presets[0]}",
                callback_data="settings_preset_0",
            ),
            InlineKeyboardButton(
                f"✏️ ${presets[1]}",
                callback_data="settings_preset_1",
            ),
            InlineKeyboardButton(
                f"✏️ ${presets[2]}",
                callback_data="settings_preset_2",
            ),
        ],
        # Section header - Auto-Claim
        [InlineKeyboardButton("🎯 —— AUTO-CLAIM ——", callback_data="noop")],
        [
            InlineKeyboardButton(
                f"{'✅' if auto_claim else '⬜'} Enable Auto-Claim Positions",
                callback_data="settings_toggle_autoclaim",
            )
        ],
        # Section header - Presets
        [InlineKeyboardButton("⚡ —— PRESETS ——", callback_data="noop")],
        [
            InlineKeyboardButton(
                f"{'✅' if auto_preset else '⬜'} Enable Auto-Apply Default Preset",
                callback_data="settings_toggle_autopreset",
            )
        ],
        # Section header - Security
        [InlineKeyboardButton("🔒 —— SECURITY ——", callback_data="noop")],
        [
            InlineKeyboardButton(
                f"{'✅' if two_fa else '⬜'} 🛡️ Enable Two-Factor (2FA)",
                callback_data="settings_toggle_2fa",
            )
        ],
        [
            InlineKeyboardButton(
                "🔑 Export Private Key",
                callback_data="settings_export_key",
            )
        ],
        # Main menu
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def build_settings_text(settings: dict) -> str:
    """Build the settings menu text."""
    return """⚙️ *Settings*

🚀 *Trading Modes*
• Standard — Require confirmation for every market order
• Fast — Only orders above the threshold require confirmation
• Ludicrous — fires market orders immediately with NO CONFIRMATION

📊 *Quickbuy Presets*
Tap any preset amount to edit the preset quickbuy amounts when you trade.

⚡ *Presets*
Auto-apply your default preset to new purchases.

🔒 *Security*
Export your smart-wallet private key.

Select an option below to manage it."""


async def show_settings_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Display the settings menu."""
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    user_service: UserService = context.bot_data["user_service"]

    # Get user settings
    settings = await user_service.get_user_settings(user.id)

    text = build_settings_text(settings)
    keyboard = build_settings_keyboard(settings)

    if query:
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    return ConversationState.SETTINGS_MENU


async def handle_settings_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle settings button callbacks."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    user = update.effective_user
    user_service: UserService = context.bot_data["user_service"]

    # Trading mode changes
    if callback_data == "settings_mode_standard":
        await user_service.update_user_setting(user.id, "trading_mode", "standard")
        return await show_settings_menu(update, context)

    elif callback_data == "settings_mode_fast":
        await user_service.update_user_setting(user.id, "trading_mode", "fast")
        return await show_settings_menu(update, context)

    elif callback_data == "settings_mode_ludicrous":
        await user_service.update_user_setting(user.id, "trading_mode", "ludicrous")
        return await show_settings_menu(update, context)

    # Fast mode threshold
    elif callback_data == "settings_threshold":
        settings = await user_service.get_user_settings(user.id)
        current = settings.get("fast_mode_threshold", 100.0)

        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_settings")],
        ]

        await query.edit_message_text(
            f"✏️ *Edit Fast Mode Threshold*\n\n"
            f"💰 Current threshold: `${current:.2f}`\n\n"
            f"📋 Orders above this amount will require confirmation in Fast mode.\n\n"
            f"✏️ Enter new threshold amount (in USD):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        context.user_data["settings_editing"] = "threshold"
        return ConversationState.SETTINGS_FAST_THRESHOLD

    # Quickbuy preset editing
    elif callback_data.startswith("settings_preset_"):
        preset_index = int(callback_data.split("_")[-1])
        settings = await user_service.get_user_settings(user.id)
        presets = settings.get("quickbuy_presets", [10, 25, 50])
        current = presets[preset_index]

        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_settings")],
        ]

        await query.edit_message_text(
            f"✏️ *Edit Quickbuy Preset*\n\n"
            f"💵 Current preset #{preset_index + 1}: `${current}`\n\n"
            f"✏️ Enter new preset amount (in USD):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        context.user_data["settings_editing"] = "preset"
        context.user_data["preset_index"] = preset_index
        return ConversationState.SETTINGS_QUICKBUY_EDIT

    # Toggle auto-claim
    elif callback_data == "settings_toggle_autoclaim":
        settings = await user_service.get_user_settings(user.id)
        current = settings.get("auto_claim", False)
        await user_service.update_user_setting(user.id, "auto_claim", not current)
        return await show_settings_menu(update, context)

    # Toggle auto-apply preset
    elif callback_data == "settings_toggle_autopreset":
        settings = await user_service.get_user_settings(user.id)
        current = settings.get("auto_apply_preset", False)
        await user_service.update_user_setting(user.id, "auto_apply_preset", not current)
        return await show_settings_menu(update, context)

    # Toggle 2FA
    elif callback_data == "settings_toggle_2fa":
        settings = await user_service.get_user_settings(user.id)
        current = settings.get("two_factor_enabled", False)
        await user_service.update_user_setting(user.id, "two_factor_enabled", not current)
        return await show_settings_menu(update, context)

    # Export private key
    elif callback_data == "settings_export_key":
        keyboard = [
            [
                InlineKeyboardButton(
                    "⚠️ Yes, Show Private Key",
                    callback_data="settings_export_confirm",
                ),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_settings")],
        ]

        await query.edit_message_text(
            "🚨 *Security Warning*\n\n"
            "🔑 You are about to export your private key.\n\n"
            "⛔ *NEVER share this key with anyone!*\n"
            "👤 Anyone with this key can access your funds.\n\n"
            "❓ Are you sure you want to continue?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return ConversationState.SETTINGS_EXPORT_KEY

    elif callback_data == "settings_export_confirm":
        # Get user's wallet and decrypt private key
        user_db = await user_service.get_user(user.id)
        if not user_db:
            await query.edit_message_text(
                "❌ Error: User not found.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="menu_settings")]
                ]),
            )
            return ConversationState.SETTINGS_MENU

        private_key = await user_service.get_private_key(user_db.id)

        keyboard = [
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="menu_settings")],
        ]

        await query.edit_message_text(
            "🔐 *Your Private Key*\n\n"
            f"`{private_key}`\n\n"
            "⚠️ *Keep this safe and NEVER share it!*\n"
            "🗑️ This message will not be stored.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return ConversationState.SETTINGS_MENU

    # Noop for section headers
    elif callback_data == "noop":
        await query.answer("This is a section header")
        return ConversationState.SETTINGS_MENU

    return ConversationState.SETTINGS_MENU


async def handle_settings_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle text input for settings (threshold, presets)."""
    user = update.effective_user
    user_service: UserService = context.bot_data["user_service"]

    editing = context.user_data.get("settings_editing")
    text = update.message.text.strip()

    # Parse amount
    try:
        # Remove $ if present
        if text.startswith("$"):
            text = text[1:]
        amount = float(text)

        if amount <= 0:
            raise ValueError("Amount must be positive")

    except ValueError:
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_settings")],
        ]
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a valid number.\n\n"
            "💡 Example: `50` or `100.50`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return context.user_data.get("_current_state", ConversationState.SETTINGS_MENU)

    if editing == "threshold":
        await user_service.update_user_setting(user.id, "fast_mode_threshold", amount)

        await update.message.reply_text(
            f"✅ Fast mode threshold updated to ${amount:.2f}",
            parse_mode="Markdown",
        )

    elif editing == "preset":
        preset_index = context.user_data.get("preset_index", 0)
        settings = await user_service.get_user_settings(user.id)
        presets = settings.get("quickbuy_presets", [10, 25, 50]).copy()
        presets[preset_index] = int(amount)

        await user_service.update_user_setting(user.id, "quickbuy_presets", presets)

        await update.message.reply_text(
            f"✅ Quickbuy preset #{preset_index + 1} updated to ${int(amount)}",
            parse_mode="Markdown",
        )

    # Clean up
    context.user_data.pop("settings_editing", None)
    context.user_data.pop("preset_index", None)

    # Show settings menu again
    settings = await user_service.get_user_settings(user.id)
    text = build_settings_text(settings)
    keyboard = build_settings_keyboard(settings)

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )

    return ConversationState.SETTINGS_MENU

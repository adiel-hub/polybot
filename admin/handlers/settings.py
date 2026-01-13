"""Admin system settings handler."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin.states import AdminState
from admin.utils.decorators import admin_only

logger = logging.getLogger(__name__)

# System settings that can be viewed/toggled
SYSTEM_SETTINGS = {
    "maintenance_mode": {
        "label": "🔧 Maintenance Mode",
        "description": "Disable trading for all users",
        "default": False,
    },
    "new_registrations": {
        "label": "👤 New Registrations",
        "description": "Allow new user registrations",
        "default": True,
    },
    "copy_trading_enabled": {
        "label": "👥 Copy Trading",
        "description": "Enable copy trading feature",
        "default": True,
    },
    "stop_loss_enabled": {
        "label": "🛑 Stop Loss",
        "description": "Enable stop loss feature",
        "default": True,
    },
}


def get_system_settings(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Get current system settings from bot_data."""
    if "system_settings" not in context.bot_data:
        context.bot_data["system_settings"] = {
            key: config["default"] for key, config in SYSTEM_SETTINGS.items()
        }
    return context.bot_data["system_settings"]


@admin_only
async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display system settings."""
    query = update.callback_query
    if query:
        await query.answer()

    settings = get_system_settings(context)

    text = "🔧 *System Settings*\n\nToggle system-wide features:\n"

    keyboard = []

    for key, config in SYSTEM_SETTINGS.items():
        current_value = settings.get(key, config["default"])
        status = "✅" if current_value else "⬜"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {config['label']}",
                callback_data=f"admin_setting_toggle_{key}",
            )
        ])

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    return AdminState.SYSTEM_SETTINGS


@admin_only
async def handle_setting_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Toggle a system setting."""
    query = update.callback_query
    await query.answer()

    setting_key = query.data.replace("admin_setting_toggle_", "")

    if setting_key not in SYSTEM_SETTINGS:
        await query.answer("Unknown setting", show_alert=True)
        return AdminState.SYSTEM_SETTINGS

    settings = get_system_settings(context)
    current_value = settings.get(setting_key, SYSTEM_SETTINGS[setting_key]["default"])
    settings[setting_key] = not current_value

    logger.info(f"Admin toggled {setting_key} to {settings[setting_key]}")

    return await show_settings(update, context)

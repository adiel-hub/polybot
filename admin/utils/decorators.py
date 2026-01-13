"""Admin authentication decorators."""

import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from admin.config import is_admin

logger = logging.getLogger(__name__)


def admin_only(func):
    """Decorator to restrict handler to admin users only."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if not is_admin(user_id):
            logger.warning(f"Unauthorized admin access attempt by user {user_id}")

            if update.callback_query:
                await update.callback_query.answer(
                    "Unauthorized. Admin access only.", show_alert=True
                )
            elif update.message:
                await update.message.reply_text(
                    "You are not authorized to access the admin panel."
                )

            return ConversationHandler.END

        return await func(update, context)

    return wrapper

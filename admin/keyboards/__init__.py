"""Admin keyboards."""

from admin.keyboards.menus import (
    get_admin_main_menu,
    get_back_keyboard,
    get_confirmation_keyboard,
)
from admin.keyboards.pagination import build_pagination_keyboard

__all__ = [
    "get_admin_main_menu",
    "get_back_keyboard",
    "get_confirmation_keyboard",
    "build_pagination_keyboard",
]

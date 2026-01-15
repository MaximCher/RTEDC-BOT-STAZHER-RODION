from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.legacy.content import PAYMENTS_SUBSERVICES, SERVICES


def legacy_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Legacy main menu layout (2 buttons per row + extra rows).
    Mirrors bot/utils/keyboards.py in the legacy bot.
    """
    keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for name, callback in SERVICES:
        row.append(InlineKeyboardButton(text=name, callback_data=callback))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton(
                text="📅 Ближайшие мероприятия СРВТ",
                callback_data="srvtevents",
            ),
            InlineKeyboardButton(
                text="💱 Курсы валют", callback_data="currency_rates"
            ),
        ]
    )
    # Our improved CTA should be present in the main menu.
    # If user hasn't picked a direction yet, lead handler will show the service picker.
    keyboard.append(
        [
            InlineKeyboardButton(
                text="✉️ Подать запрос", callback_data="lead:start:choose"
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                text="ВСТУПИТЬ В КЛУБ ЭКСПОРТЕРОВ И ИМПОРТЕРОВ СРВТ.РФ",
                callback_data="join_club",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def legacy_service_menu_keyboard(
    extra_rows: list[list[InlineKeyboardButton]] | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if extra_rows:
        rows.extend(extra_rows)
    rows.append(
        [InlineKeyboardButton(text="✉️ Подать запрос", callback_data="apply")]
    )
    rows.append(
        [InlineKeyboardButton(text="В главное меню", callback_data="menu:new")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def legacy_payments_submenu_keyboard() -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for name, callback in PAYMENTS_SUBSERVICES:
        keyboard.append(
            [InlineKeyboardButton(text=name, callback_data=callback)]
        )
    keyboard.append(
        [InlineKeyboardButton(text="В главное меню", callback_data="menu:new")]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

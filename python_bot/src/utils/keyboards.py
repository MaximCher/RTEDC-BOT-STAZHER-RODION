from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.config import SERVICES


def services_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key, label in SERVICES.items():
        rows.append([InlineKeyboardButton(text=label, callback_data=f"service:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")]
        ]
    )


def lead_actions_keyboard(service_key: str) -> InlineKeyboardMarkup:
    first_row = [
        InlineKeyboardButton(
            text="📩 Передать эксперту",
            callback_data=f"lead:start:{service_key}",
        )
    ]
    if service_key == "subsidies_financing":
        first_row.append(
            InlineKeyboardButton(
                text="🔎 Вопрос по субсидиям",
                callback_data=f"subsidy:chat:start:{service_key}",
            )
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            first_row,
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")],
        ]
    )



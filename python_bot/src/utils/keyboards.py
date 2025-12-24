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


def flow_nav_keyboard(back_callback_data: str | None = None) -> InlineKeyboardMarkup:
    """
    Navigation keyboard for multi-step flows.
    - If back_callback_data is provided: show "Назад" + "В меню" in one row.
    - Otherwise: show only "В меню".
    """
    row = []
    if back_callback_data:
        row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback_data))
    row.append(InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


def lead_actions_keyboard(service_key: str) -> InlineKeyboardMarkup:
    first_row = [
        InlineKeyboardButton(
            text="📩 Оставить заявку",
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


def subsidies_entry_keyboard() -> InlineKeyboardMarkup:
    """Entry keyboard for SRVT subsidies/financing direction (SRVT-style CTAs)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Рассчитать объём субсидии (2 мин)",
                    callback_data="subsidy:calc:start:subsidies_financing",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Рассчитать финансирование/рефинанс (2 мин)",
                    callback_data="finance:calc:start:subsidies_financing",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔎 Вопрос по субсидиям",
                    callback_data="subsidy:chat:start:subsidies_financing",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Заполнить анкету",
                    callback_data="service:questionnaire:subsidies_financing",
                )
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")],
        ]
    )


def payments_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💸 Оценить международный платеж (1 мин)",
                    callback_data="payments:precheck:start:international_payments",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Заполнить анкету",
                    callback_data="service:questionnaire:international_payments",
                )
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")],
        ]
    )


def logistics_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚚 Получить расчёт логистики (1 мин)",
                    callback_data="logistics:quote:start:logistics_ved",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Заполнить анкету",
                    callback_data="service:questionnaire:logistics_ved",
                )
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")],
        ]
    )


def analytics_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📈 Заказать аналитический отчёт (1 мин)",
                    callback_data="analytics:report:start:analytics_tnved",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Заполнить анкету",
                    callback_data="service:questionnaire:analytics_tnved",
                )
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")],
        ]
    )


def quick_audit_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧾 Быстрый аудит по ИНН (1 мин)",
                    callback_data="audit:quick:start:quick_audit_inn",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Заполнить анкету",
                    callback_data="service:questionnaire:quick_audit_inn",
                )
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")],
        ]
    )


def club_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤝 Стать партнёром/агентом (1 мин)",
                    callback_data="club:apply:start:club_partnership",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Заполнить анкету",
                    callback_data="service:questionnaire:club_partnership",
                )
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")],
        ]
    )


def meeting_window_keyboard(include_back: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня 10:00–13:00", callback_data="lead:mw:today_am"),
                InlineKeyboardButton(text="Сегодня 14:00–18:00", callback_data="lead:mw:today_pm"),
            ],
            [
                InlineKeyboardButton(text="Завтра 10:00–13:00", callback_data="lead:mw:tomorrow_am"),
                InlineKeyboardButton(text="Завтра 14:00–18:00", callback_data="lead:mw:tomorrow_pm"),
            ],
            [
                InlineKeyboardButton(text="Будни после 19:00", callback_data="lead:mw:weekdays_19"),
                InlineKeyboardButton(text="Не важно", callback_data="lead:mw:any"),
            ],
            (
                [
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="lead:back"),
                    InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root"),
                ]
                if include_back
                else [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")]
            ),
        ]
    )



from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.config import SERVICES


def services_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key, label in SERVICES.items():
        rows.append([InlineKeyboardButton(text=label, callback_data=f"service:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def flow_nav_keyboard(back_callback_data: str | None = None) -> InlineKeyboardMarkup:
    """
    Navigation keyboard for multi-step flows.
    We prefer a consistent UX: show "Назад" + "В меню".
    If back_callback_data is not provided, "Назад" will behave as "В меню".
    """
    back_cb = back_callback_data or "menu:root"
    # UX: keep navigation buttons full-width and stable across screens
    # (1 button per row prevents "jumping" between wide and narrow layouts).
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")],
        ]
    )


def lead_actions_keyboard(service_key: str) -> InlineKeyboardMarkup:
    first_row = [
        InlineKeyboardButton(
            text="📩 Заявка на консультацию",
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
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"entry:new:{service_key}"),
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:new")],
        ]
    )


def subsidy_chat_keyboard(service_key: str) -> InlineKeyboardMarkup:
    """Keyboard for the 'subsidy question' mode."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📩 Заявка на консультацию",
                    callback_data=f"lead:start:{service_key}",
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"entry:new:{service_key}"),
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:new")],
        ]
    )


def subsidies_entry_keyboard() -> InlineKeyboardMarkup:
    """Entry keyboard for SRVT subsidies/financing direction (SRVT-style CTAs)."""
    rows = [
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
                text="📩 Заявка на консультацию",
                callback_data="lead:start:subsidies_financing",
            )
        ],
    ]
    rows += flow_nav_keyboard().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payments_entry_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="💸 Оценить международный платеж (1 мин)",
                callback_data="payments:precheck:start:international_payments",
            )
        ],
        [
            InlineKeyboardButton(
                text="📩 Заявка на консультацию",
                callback_data="lead:start:international_payments",
            )
        ],
    ]
    rows += flow_nav_keyboard().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def logistics_entry_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🚚 Получить расчёт логистики (1 мин)",
                callback_data="logistics:quote:start:logistics_ved",
            )
        ],
        [
            InlineKeyboardButton(
                text="📩 Заявка на консультацию",
                callback_data="lead:start:logistics_ved",
            )
        ],
    ]
    rows += flow_nav_keyboard().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def analytics_entry_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="📈 Заказать аналитический отчёт (1 мин)",
                callback_data="analytics:report:start:analytics_tnved",
            )
        ],
        [
            InlineKeyboardButton(
                text="📩 Заявка на консультацию",
                callback_data="lead:start:analytics_tnved",
            )
        ],
    ]
    rows += flow_nav_keyboard().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quick_audit_entry_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🧾 Быстрый аудит по ИНН (1 мин)",
                callback_data="audit:quick:start:quick_audit_inn",
            )
        ],
        [
            InlineKeyboardButton(
                text="📩 Заявка на консультацию",
                callback_data="lead:start:quick_audit_inn",
            )
        ],
    ]
    rows += flow_nav_keyboard().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def club_entry_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🤝 Стать партнёром/агентом (1 мин)",
                callback_data="club:apply:start:club_partnership",
            )
        ],
        [
            InlineKeyboardButton(
                text="📩 Заявка на консультацию",
                callback_data="lead:start:club_partnership",
            )
        ],
    ]
    rows += flow_nav_keyboard().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
                ]
                if include_back
                else []
            ),
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:root")],
        ]
    )


def staff_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Взять в работу",
                    callback_data=f"staff:ticket:claim:{ticket_id}",
                ),
                InlineKeyboardButton(
                    text="💬 Запросить чат",
                    callback_data=f"staff:ticket:request_chat:{ticket_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗂 Открыть чат",
                    callback_data=f"staff:ticket:open:{ticket_id}",
                ),
                InlineKeyboardButton(
                    text="🔁 Передать",
                    callback_data=f"staff:ticket:transfer:{ticket_id}",
                ),
                InlineKeyboardButton(
                    text="✅ Закрыть",
                    callback_data=f"staff:ticket:close:{ticket_id}",
                ),
            ],
        ]
    )


def lead_chat_request_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, хочу консультацию",
                    callback_data=f"lead:chat:accept:{ticket_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Не сейчас",
                    callback_data=f"lead:chat:decline:{ticket_id}",
                )
            ],
        ]
    )


def lead_chat_active_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚪 Выйти из чата",
                    callback_data=f"lead:chat:exit:{ticket_id}",
                )
            ]
        ]
    )


def staff_chat_active_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚪 Выйти",
                    callback_data=f"staff:chat:exit:{ticket_id}",
                )
            ]
        ]
    )



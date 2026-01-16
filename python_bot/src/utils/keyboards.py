from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.config import SERVICES


def services_keyboard() -> InlineKeyboardMarkup:
    # Legacy-style layout: 2 buttons per row (where possible)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key, label in SERVICES.items():
        row.append(
            InlineKeyboardButton(text=label, callback_data=f"service:{key}")
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    # Always allow exit to main menu from calculators hub.
    rows.append(
        [InlineKeyboardButton(text="В главное меню", callback_data="menu:new")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lead_services_keyboard() -> InlineKeyboardMarkup:
    """
    Service picker that immediately starts the lead flow for the chosen
    direction. Used when user clicks a global CTA like
    "Заявка на консультацию" from menus.
    """
    # Legacy-style layout: 2 buttons per row (where possible)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key, label in SERVICES.items():
        row.append(
            InlineKeyboardButton(text=label, callback_data=f"lead:start:{key}")
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [InlineKeyboardButton(text="В главное меню", callback_data="menu:new")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def flow_nav_keyboard(
    back_callback_data: str | None = None,
    menu_callback_data: str = "menu:new",
) -> InlineKeyboardMarkup:
    """
    Navigation keyboard for multi-step flows.
    We prefer a consistent UX: show "Назад" + "В меню".
    If back_callback_data is not provided, "Назад" will behave as "В меню".
    """
    # Prefer opening menu as a new message so we never overwrite "important"
    # bot messages.
    back_cb = back_callback_data or "menu:new"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=back_cb)],
            [
                InlineKeyboardButton(
                    text="В главное меню", callback_data=menu_callback_data
                )
            ],
        ]
    )


def flow_nav_with_choices_keyboard(
    *,
    back_callback_data: str | None,
    choices: list[str],
    choice_callback_prefix: str,
) -> InlineKeyboardMarkup:
    """
    Render 2–3 "quick answer" buttons above the standard navigation.

    - choices are shown as full-width (1 per row) to keep button sizing
      consistent
    - navigation buttons remain full-width and stable (1 per row)
    """
    rows: list[list[InlineKeyboardButton]] = []
    if choices:
        for i, ch in enumerate(choices):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=ch,
                        callback_data=f"{choice_callback_prefix}:{i}",
                    )
                ]
            )
    rows += flow_nav_keyboard(back_callback_data).inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lead_actions_keyboard(service_key: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="✉️ Подать запрос",
                callback_data=f"lead:start:{service_key}",
            )
        ]
    ]
    if service_key == "subsidies_financing":
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔎 Вопрос по субсидиям",
                    callback_data=f"subsidy:chat:start:{service_key}",
                )
            ]
        )
    rows += [
        [
            InlineKeyboardButton(
                text="Назад", callback_data=f"entry:new:{service_key}"
            )
        ],
        [
            InlineKeyboardButton(
                text="В главное меню", callback_data="menu:new"
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subsidy_chat_keyboard(service_key: str) -> InlineKeyboardMarkup:
    """Keyboard for the 'subsidy question' mode."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Подать запрос",
                    callback_data=f"lead:start:{service_key}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Назад", callback_data=f"entry:new:{service_key}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="В главное меню", callback_data="menu:new"
                )
            ],
        ]
    )


def subsidies_entry_keyboard() -> InlineKeyboardMarkup:
    """
    Entry keyboard for SRVT subsidies/financing direction (SRVT-style CTAs).
    """
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
                text="✉️ Подать запрос",
                callback_data="lead:start:subsidies_financing",
            )
        ],
    ]
    rows += flow_nav_keyboard("srvt:services").inline_keyboard
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
                text="✉️ Подать запрос",
                callback_data="lead:start:international_payments",
            )
        ],
    ]
    rows += flow_nav_keyboard("srvt:services").inline_keyboard
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
                text="✉️ Подать запрос",
                callback_data="lead:start:logistics_ved",
            )
        ],
    ]
    rows += flow_nav_keyboard("srvt:services").inline_keyboard
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
                text="✉️ Подать запрос",
                callback_data="lead:start:analytics_tnved",
            )
        ],
    ]
    rows += flow_nav_keyboard("srvt:services").inline_keyboard
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
                text="✉️ Подать запрос",
                callback_data="lead:start:quick_audit_inn",
            )
        ],
    ]
    rows += flow_nav_keyboard("srvt:services").inline_keyboard
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
                text="✉️ Подать запрос",
                callback_data="lead:start:club_partnership",
            )
        ],
    ]
    rows += flow_nav_keyboard("srvt:services").inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def meeting_window_keyboard(
    include_back: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="Сегодня 10:00–13:00", callback_data="lead:mw:today_am"
            )
        ],
        [
            InlineKeyboardButton(
                text="Сегодня 14:00–18:00", callback_data="lead:mw:today_pm"
            )
        ],
        [
            InlineKeyboardButton(
                text="Завтра 10:00–13:00", callback_data="lead:mw:tomorrow_am"
            )
        ],
        [
            InlineKeyboardButton(
                text="Завтра 14:00–18:00", callback_data="lead:mw:tomorrow_pm"
            )
        ],
        [
            InlineKeyboardButton(
                text="Будни после 19:00", callback_data="lead:mw:weekdays_19"
            )
        ],
        [InlineKeyboardButton(text="Не важно", callback_data="lead:mw:any")],
    ]
    if include_back:
        rows.append(
            [InlineKeyboardButton(text="Назад", callback_data="lead:back")]
        )
    rows.append(
        [InlineKeyboardButton(text="В главное меню", callback_data="menu:new")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_link_keyboard(
    payment_url: str, payment_id: int
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Оплатить консультацию", url=payment_url
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Проверить оплату",
                    callback_data=f"payment:check:{payment_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="В главное меню", callback_data="menu:new"
                )
            ],
        ]
    )


def staff_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Взять в работу",
                    callback_data=f"staff:ticket:claim:{ticket_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Запросить чат",
                    callback_data=f"staff:ticket:request_chat:{ticket_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗂 Открыть чат",
                    callback_data=f"staff:ticket:open:{ticket_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔁 Передать",
                    callback_data=f"staff:ticket:transfer:{ticket_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Закрыть",
                    callback_data=f"staff:ticket:close:{ticket_id}",
                )
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

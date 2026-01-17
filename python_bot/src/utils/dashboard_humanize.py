from __future__ import annotations

import json
from typing import Any, Dict, Optional

# Dashboard compatibility helpers.
# Keep these as pure functions/constants so web/api stays thin.

ACTION_LABELS: Dict[str, str] = {
    # Original RTEDC-BOT events
    "start": "Запуск бота",
    "menu": "Переход в главное меню",
    "service_select": "Выбор услуги",
    "subservice_select": "Выбор подуслуги",
    "form_start": "Начало заполнения заявки",
    "form_step": "Заполнение шага формы",
    "form_submit": "Отправка заявки",
    "club_join_start": "Начало вступления в клуб",
    "club_join_step": "Заполнение шага вступления в клуб",
    "club_join_submit": "Отправка заявки в клуб",
    "currency_view": "Просмотр курсов валют",
    "event_view": "Просмотр информации о мероприятии",
    "callback": "Другое действие (кнопка)",
    "join_request_instruction_sent": "Вступление в клуб: инструкция отправлена",
    "join_request_submitted": "Вступление в клуб: анкета отправлена",
    "join_request_approved": "Вступление в клуб: одобрено",
    "join_request_declined": "Вступление в клуб: отклонено",
    # Normalized funnel events (python_bot)
    "entry_service": "Вошли в услугу",
    "engagement_start": "Старт сценария",
    "engagement_complete": "Сценарий завершён",
    "cta_lead_start": "Нажали «Оставить заявку»",
    "contact_submitted": "Оставили контакт",
    "meeting_window_selected": "Выбрали время для созвона",
    "meeting_window_submitted": "Ввели время для созвона",
    "lead_created": "Лид создан",
    "payment_link_created": "Сформирована ссылка на оплату",
    "payment_paid": "Оплата подтверждена",
    "payment_failed": "Ошибка оплаты",
}

SERVICE_LABELS: Dict[str, str] = {
    # Service ids (classic menu)
    "service_payments": "Международные платежи",
    "service_credits": "Льготные кредиты",
    "service_subsidies": "Субсидии",
    "service_logistics": "Логистика",
    "service_check": "Проверка контрагента",
    "service_translate": "Лингвистические переводы",
    # New service ids (python_bot)
    "subsidies_financing": "Субсидии и льготное финансирование",
    "logistics_ved": "Логистика и ВЭД",
    "international_payments": "Международные платежи",
    "analytics_tnved": "Аналитика и ТН ВЭД",
    "quick_audit_inn": "Проверка по ИНН (quick audit)",
    "club_partnership": "Клуб экспортёров и партнёрство",
}

STEP_LABELS: Dict[str, str] = {
    "name": "Имя",
    "company": "Компания",
    "description": "Описание задачи",
    "fio": "ФИО",
    "expectations": "Ожидания",
    "inn": "ИНН",
}


def _safe_json(params: Any) -> Optional[Dict[str, Any]]:
    if not params:
        return None
    if isinstance(params, dict):
        return params
    if not isinstance(params, str):
        return None
    raw = params.strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def humanize_event(action: str, params: Any) -> str:
    """
    Human-readable event description for the admin dashboard.
    """
    action = str(action or "")
    label = ACTION_LABELS.get(action, action or "event")
    # If action itself is a service key, show it as a service selection.
    if action in SERVICE_LABELS and not params:
        return f"Выбор услуги: {SERVICE_LABELS[action]}"

    p = _safe_json(params)
    if not p:
        return label

    # Prefer "label" and optional "value" if provided.
    if "label" in p and p.get("label"):
        if p.get("value"):
            return f"{p['label']} — {p['value']}"
        return str(p["label"])

    # Prefer service label if present in payload
    service_key = p.get("service") or p.get("service_key")
    if service_key:
        service_name = SERVICE_LABELS.get(str(service_key), str(service_key))
        return f"{label}: {service_name}"

    # Service-specific cases
    if action == "service_select":
        service = p.get("service")
        service_name = SERVICE_LABELS.get(str(service), service)
        return f"{label}: {service_name}"
    if action == "subservice_select":
        subservice = p.get("subservice")
        return f"{label}: {subservice}"
    if action in {"form_step", "club_join_step"}:
        step = p.get("step")
        value = p.get("value")
        return f"{label}: {STEP_LABELS.get(str(step), step)} — {value}"
    if action == "callback":
        data = p.get("data")
        if data in SERVICE_LABELS:
            return f"Выбор услуги: {SERVICE_LABELS[data]}"
        return f"{label}: {data}"

    return f"{label}: {p}"

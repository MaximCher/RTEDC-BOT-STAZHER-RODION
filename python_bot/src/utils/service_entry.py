from __future__ import annotations

from typing import Tuple

from aiogram.types import InlineKeyboardMarkup

from src.config import SERVICE_FLOWS
from src.utils.keyboards import (
    analytics_entry_keyboard,
    club_entry_keyboard,
    logistics_entry_keyboard,
    payments_entry_keyboard,
    services_keyboard,
    subsidies_entry_keyboard,
)
from src.utils.messages import msg


def entry_screen_for_service(service_key: str) -> Tuple[str, InlineKeyboardMarkup, str | None]:
    """
    Returns (text, keyboard, parse_mode) for service "entry" screen.
    This is the screen user sees after selecting a service (before starting questionnaires/quizzes).
    """
    flow = SERVICE_FLOWS.get(service_key)
    text = (flow.get("description") if isinstance(flow, dict) else None) or msg("choose_service")

    if service_key == "subsidies_financing":
        return text, subsidies_entry_keyboard(), None
    if service_key == "international_payments":
        return text, payments_entry_keyboard(), None
    if service_key == "logistics_ved":
        return text, logistics_entry_keyboard(), None
    if service_key == "analytics_tnved":
        return text, analytics_entry_keyboard(), None
    if service_key == "club_partnership":
        return text, club_entry_keyboard(), None

    return msg("choose_service"), services_keyboard(), None



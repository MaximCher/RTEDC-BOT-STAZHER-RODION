from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.models.required_subscription import RequiredSubscription


@dataclass(frozen=True)
class GateCheckResult:
    enabled: bool
    missing: List[RequiredSubscription]
    error: Optional[str] = None


def gate_keyboard(items: List[RequiredSubscription]) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for it in items:
        if it.url:
            label = (it.title or it.chat_ref or "Открыть").strip()
            rows.append([InlineKeyboardButton(text=f"🔗 {label}"[:60], url=it.url)])
    rows.append([InlineKeyboardButton(text="✅ Проверить доступ", callback_data="gate:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def gate_text(missing: List[RequiredSubscription]) -> str:
    lines = [
        "Чтобы пользоваться ботом, нужно подписаться на ресурсы SRVT:",
        "",
    ]
    for it in missing:
        label = (it.title or it.chat_ref).strip()
        lines.append(f"- {label}")
    lines.append("")
    lines.append("После подписки нажмите «✅ Проверить доступ».")
    return "\n".join(lines).strip()



from __future__ import annotations

import re
from typing import Dict, List, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dialog_message import DialogMessage
from src.models.user_memory import UserMemory
from src.utils.funnel import log_event
from src.utils.keyboards import lead_actions_keyboard

router = Router()


class QuickAudit(StatesGroup):
    waiting_for_answer = State()


_INN_RE = re.compile(r"\b\d{10}\b|\b\d{12}\b")

_QA_QUESTIONS: List[Tuple[str, str]] = [
    ("inn", "1) ИНН компании (10 или 12 цифр)"),
    ("target", "2) Кого проверяем: потенциального партнёра или свою компанию?"),
    ("focus", "3) Что важно проверить? (риски/суды/финансы/исп. производства/всё)"),
    ("urgency", "4) Срочность: сейчас / сегодня / не срочно"),
]


@router.callback_query(F.data.startswith("audit:quick:start:"))
async def start_quick_audit(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    service_key = (callback.data or "").split("audit:quick:start:", 1)[-1].strip()
    if not service_key:
        service_key = "quick_audit_inn"

    await state.set_state(QuickAudit.waiting_for_answer)
    await state.update_data(service_key=service_key, qa_step=0, qa_answers={})

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="quick_audit_start",
        service_key=service_key,
    )

    await callback.message.answer("Ок, сделаем быстрый аудит по ИНН. Это займёт ~1 минуту.")
    await callback.message.answer(_QA_QUESTIONS[0][1])
    await callback.answer()


@router.message(QuickAudit.waiting_for_answer)
async def handle_quick_audit_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    step = int(data.get("qa_step", 0))
    answers: Dict[str, str] = dict(data.get("qa_answers") or {})
    service_key = data.get("service_key") if isinstance(data.get("service_key"), str) else "quick_audit_inn"

    if step < 0 or step >= len(_QA_QUESTIONS):
        await state.clear()
        return

    key, q_text = _QA_QUESTIONS[step]
    if key == "inn":
        m = _INN_RE.search(text)
        if not m:
            await message.answer("Не вижу ИНН. Пришлите 10 или 12 цифр (без пробелов).")
            return
        text = m.group(0)

    answers[key] = text[:400]

    await UserMemory.add_message(session, message.from_user.id, "user", f"{q_text}\nОтвет: {text}")
    await DialogMessage.create(
        session,
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=None,
        phone=None,
        message_text=text,
        role="user",
        chat_id=message.chat.id,
        message_id=message.message_id,
    )

    step += 1
    await state.update_data(qa_step=step, qa_answers=answers)

    if step < len(_QA_QUESTIONS):
        await message.answer(_QA_QUESTIONS[step][1])
        return

    result = (
        "Готово ✅\n\n"
        "Менеджер SRVT подготовит сводный аудит (реквизиты, суды/арбитраж, финансы, исполнительные производства, риски) и пришлёт выводы.\n\n"
        "Оставьте контакт + удобное окно созвона — передам заявку."
    )

    summary_lines = ["SRVT • Quick audit по ИНН"]
    for k, q in _QA_QUESTIONS:
        summary_lines.append(f"{q}\nОтвет: {answers.get(k, '')}")
    summary_lines.append("SRVT обещание: персональный менеджер свяжется в течение 15 минут (в рабочее время).")
    summary_text = "\n\n".join(summary_lines)

    await log_event(
        session,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        username=message.from_user.username,
        event="quick_audit_complete",
        service_key=service_key,
    )

    await UserMemory.add_message(session, message.from_user.id, "system", summary_text)
    await state.update_data(questionnaire_summary=summary_text)

    await message.answer(result, reply_markup=lead_actions_keyboard(service_key))

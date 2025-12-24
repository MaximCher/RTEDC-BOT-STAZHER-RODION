from __future__ import annotations

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


class AnalyticsReport(StatesGroup):
    waiting_for_answer = State()


_AN_QUESTIONS: List[Tuple[str, str]] = [
    ("countries", "1) Какие страны интересуют? (до 10, можно 1–2)"),
    ("product", "2) Товар/позиция: название или ТН ВЭД (если знаете)"),
    ("report_type", "3) Отчёт: краткий или расширенный? (краткий/расширенный)"),
    ("inn", "4) ИНН вашей компании (если есть). Если не хотите — напишите «нет»"),
    ("timeline", "5) Когда нужен результат? (сейчас/в течение недели/позже)"),
]


@router.callback_query(F.data.startswith("analytics:report:start:"))
async def start_analytics_report(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    service_key = (callback.data or "").split("analytics:report:start:", 1)[-1].strip()
    if not service_key:
        service_key = "analytics_tnved"

    await state.set_state(AnalyticsReport.waiting_for_answer)
    await state.update_data(service_key=service_key, an_step=0, an_answers={})

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="analytics_report_start",
        service_key=service_key,
    )

    await callback.message.answer("Ок, соберу вводные для аналитического отчёта SRVT. Это займёт ~1 минуту.")
    await callback.message.answer(_AN_QUESTIONS[0][1])
    await callback.answer()


@router.message(AnalyticsReport.waiting_for_answer)
async def handle_analytics_report_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    step = int(data.get("an_step", 0))
    answers: Dict[str, str] = dict(data.get("an_answers") or {})
    service_key = data.get("service_key") if isinstance(data.get("service_key"), str) else "analytics_tnved"

    if step < 0 or step >= len(_AN_QUESTIONS):
        await state.clear()
        return

    key, q_text = _AN_QUESTIONS[step]
    answers[key] = text[:700]

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
    await state.update_data(an_step=step, an_answers=answers)

    if step < len(_AN_QUESTIONS):
        await message.answer(_AN_QUESTIONS[step][1])
        return

    result = (
        "Готово ✅\n\n"
        "Менеджер SRVT уточнит детали и предложит формат отчёта.\n"
        "В отчёте обычно есть: тренды/динамика, цены, реестры импортеров/экспортеров по ТН ВЭД, ограничения.\n\n"
        "Оставьте контакт + удобное окно созвона — передам заявку."
    )

    summary_lines = ["SRVT • Заказ аналитического отчёта (TN VED)"]
    for k, q in _AN_QUESTIONS:
        summary_lines.append(f"{q}\nОтвет: {answers.get(k, '')}")
    summary_lines.append("SRVT обещание: персональный менеджер свяжется в течение 15 минут (в рабочее время).")
    summary_text = "\n\n".join(summary_lines)

    await log_event(
        session,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        username=message.from_user.username,
        event="analytics_report_complete",
        service_key=service_key,
    )

    await UserMemory.add_message(session, message.from_user.id, "system", summary_text)
    await state.update_data(questionnaire_summary=summary_text)

    await message.answer(result, reply_markup=lead_actions_keyboard(service_key))



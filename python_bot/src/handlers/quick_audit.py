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
from src.utils.keyboards import flow_nav_keyboard, lead_actions_keyboard
from src.utils.ui_flow import format_step, ui_upsert
from src.utils.service_entry import entry_screen_for_service

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


@router.callback_query(F.data == "audit:quick:back")
async def quick_audit_back(callback: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    if current != QuickAudit.waiting_for_answer.state:
        await callback.answer()
        return

    data = await state.get_data()
    step = int(data.get("qa_step", 0))
    answers: Dict[str, str] = dict(data.get("qa_answers") or {})
    service_key = data.get("service_key") if isinstance(data.get("service_key"), str) else "quick_audit_inn"

    if step <= 0:
        await state.clear()
        text, kb, pm = entry_screen_for_service(service_key)
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            prefer_message_id=callback.message.message_id,
            text=text,
            reply_markup=kb,
            parse_mode=pm,
            keep_at_bottom=True,
        )
        await callback.answer()
        return

    new_step = step - 1
    key, _ = _QA_QUESTIONS[new_step]
    answers.pop(key, None)
    await state.update_data(qa_step=new_step, qa_answers=answers)

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Quick Audit по ИНН",
            step=new_step + 1,
            total=len(_QA_QUESTIONS),
            question=_QA_QUESTIONS[new_step][1],
        ),
        reply_markup=flow_nav_keyboard("audit:quick:back"),
        keep_at_bottom=True,
    )
    await callback.answer()


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

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Quick Audit по ИНН",
            step=1,
            total=len(_QA_QUESTIONS),
            intro="Ок, сделаем быстрый аудит по ИНН. Это займёт ~1 минуту.",
            question=_QA_QUESTIONS[0][1],
        ),
        reply_markup=flow_nav_keyboard("audit:quick:back"),
        keep_at_bottom=True,
    )
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
            await ui_upsert(
                bot=message.bot,
                state=state,
                chat_id=message.chat.id,
                text=format_step(
                    title="SRVT • Quick Audit по ИНН",
                    step=step + 1,
                    total=len(_QA_QUESTIONS),
                    intro="Ошибка: не вижу ИНН. Пришлите 10 или 12 цифр (без пробелов).",
                    question=q_text,
                ),
                reply_markup=flow_nav_keyboard("audit:quick:back"),
                keep_at_bottom=True,
            )
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
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Quick Audit по ИНН",
                step=step + 1,
                total=len(_QA_QUESTIONS),
                question=_QA_QUESTIONS[step][1],
            ),
            reply_markup=flow_nav_keyboard("audit:quick:back"),
            keep_at_bottom=True,
        )
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

    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=result,
        reply_markup=lead_actions_keyboard(service_key),
        parse_mode=None,
        keep_at_bottom=True,
    )

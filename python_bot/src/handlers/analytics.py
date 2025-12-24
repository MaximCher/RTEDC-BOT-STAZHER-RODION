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
from src.utils.keyboards import flow_nav_keyboard, lead_actions_keyboard
from src.utils.ui_flow import format_step, ui_upsert
from src.utils.service_entry import entry_screen_for_service


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


@router.callback_query(F.data == "analytics:report:back")
async def analytics_report_back(callback: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    if current != AnalyticsReport.waiting_for_answer.state:
        await callback.answer()
        return

    data = await state.get_data()
    step = int(data.get("an_step", 0))
    answers: Dict[str, str] = dict(data.get("an_answers") or {})
    service_key = data.get("service_key") if isinstance(data.get("service_key"), str) else "analytics_tnved"

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
    key, _ = _AN_QUESTIONS[new_step]
    answers.pop(key, None)
    await state.update_data(an_step=new_step, an_answers=answers)

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Аналитика / ТН ВЭД",
            step=new_step + 1,
            total=len(_AN_QUESTIONS),
            question=_AN_QUESTIONS[new_step][1],
        ),
        reply_markup=flow_nav_keyboard("analytics:report:back"),
        keep_at_bottom=True,
    )
    await callback.answer()


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

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Аналитика / ТН ВЭД",
            step=1,
            total=len(_AN_QUESTIONS),
            intro="Ок, соберу вводные для аналитического отчёта SRVT. Это займёт ~1 минуту.",
            question=_AN_QUESTIONS[0][1],
        ),
        reply_markup=flow_nav_keyboard("analytics:report:back"),
        keep_at_bottom=True,
    )
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
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Аналитика / ТН ВЭД",
                step=step + 1,
                total=len(_AN_QUESTIONS),
                question=_AN_QUESTIONS[step][1],
            ),
            reply_markup=flow_nav_keyboard("analytics:report:back"),
            keep_at_bottom=True,
        )
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

    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=result,
        reply_markup=lead_actions_keyboard(service_key),
        parse_mode=None,
        keep_at_bottom=True,
    )



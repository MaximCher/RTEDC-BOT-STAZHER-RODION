from __future__ import annotations

from typing import Dict, List, Optional, Tuple

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


class LogisticsQuote(StatesGroup):
    waiting_for_answer = State()


_LOG_QUESTIONS: List[Tuple[str, str]] = [
    ("route", "1) Откуда → куда (страна/город). Пример: «Шанхай → Москва»"),
    ("cargo", "2) Что за товар/груз? (можно ТН ВЭД, если знаете)"),
    ("dims", "3) Вес и объём (или кол-во мест). Пример: «1200 кг, 6 м³»"),
    ("terms", "4) Условия: Incoterms (EXW/FOB/CIF/DDP) или «не знаю»"),
    ("timeline", "5) Когда нужно доставить? (сейчас/1–2 недели/месяц+)"),
    ("special", "6) Особые требования: опасный/температура/сертификация/ничего"),
]


def _has_any_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in (text or ""))


@router.callback_query(F.data == "logistics:quote:back")
async def logistics_quote_back(callback: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    if current != LogisticsQuote.waiting_for_answer.state:
        await callback.answer()
        return

    data = await state.get_data()
    step = int(data.get("log_step", 0))
    answers: Dict[str, str] = dict(data.get("log_answers") or {})
    service_key = data.get("service_key") if isinstance(data.get("service_key"), str) else "logistics_ved"

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
    key, _ = _LOG_QUESTIONS[new_step]
    answers.pop(key, None)
    await state.update_data(log_step=new_step, log_answers=answers)

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Логистика и ВЭД",
            step=new_step + 1,
            total=len(_LOG_QUESTIONS),
            question=_LOG_QUESTIONS[new_step][1],
        ),
        reply_markup=flow_nav_keyboard("logistics:quote:back"),
        keep_at_bottom=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("logistics:quote:start:"))
async def start_logistics_quote(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    service_key = (callback.data or "").split("logistics:quote:start:", 1)[-1].strip()
    if not service_key:
        service_key = "logistics_ved"

    await state.set_state(LogisticsQuote.waiting_for_answer)
    await state.update_data(service_key=service_key, log_step=0, log_answers={})

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="logistics_quote_start",
        service_key=service_key,
    )

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Логистика и ВЭД",
            step=1,
            total=len(_LOG_QUESTIONS),
            intro="Ок, соберу вводные для расчёта логистики SRVT. Это займёт ~1 минуту.",
            question=_LOG_QUESTIONS[0][1],
        ),
        reply_markup=flow_nav_keyboard("logistics:quote:back"),
        keep_at_bottom=True,
    )
    await callback.answer()


@router.message(LogisticsQuote.waiting_for_answer)
async def handle_logistics_quote_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    step = int(data.get("log_step", 0))
    answers: Dict[str, str] = dict(data.get("log_answers") or {})
    service_key = data.get("service_key") if isinstance(data.get("service_key"), str) else "logistics_ved"

    if step < 0 or step >= len(_LOG_QUESTIONS):
        await state.clear()
        return

    key, q_text = _LOG_QUESTIONS[step]
    if key == "dims" and not _has_any_digit(text):
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Логистика и ВЭД",
                step=step + 1,
                total=len(_LOG_QUESTIONS),
                intro="Ошибка: не вижу цифры по весу/объёму. Пример: «1200 кг, 6 м³» или «10 мест».",
                question=q_text,
            ),
            reply_markup=flow_nav_keyboard("logistics:quote:back"),
            keep_at_bottom=True,
        )
        return

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
    await state.update_data(log_step=step, log_answers=answers)

    if step < len(_LOG_QUESTIONS):
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Логистика и ВЭД",
                step=step + 1,
                total=len(_LOG_QUESTIONS),
                question=_LOG_QUESTIONS[step][1],
            ),
            reply_markup=flow_nav_keyboard("logistics:quote:back"),
            keep_at_bottom=True,
        )
        return

    result = (
        "Готово ✅\n\n"
        "По этим вводным менеджер SRVT:\n"
        "- посчитает 2–3 маршрута (срок/стоимость/риски)\n"
        "- уточнит документы и ограничения по товару\n"
        "- предложит оптимальный вариант «под ключ»\n\n"
        "Оставьте контакт + удобное окно созвона — передам заявку."
    )

    summary_lines = ["SRVT • Расчёт логистики (pre-quote)"]
    for k, q in _LOG_QUESTIONS:
        summary_lines.append(f"{q}\nОтвет: {answers.get(k, '')}")
    summary_lines.append("SRVT обещание: персональный менеджер свяжется в течение 15 минут (в рабочее время).")
    summary_text = "\n\n".join(summary_lines)

    await log_event(
        session,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        username=message.from_user.username,
        event="logistics_quote_complete",
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



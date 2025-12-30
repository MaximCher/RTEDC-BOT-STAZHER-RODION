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
from src.utils.keyboards import (
    flow_nav_keyboard,
    flow_nav_with_choices_keyboard,
    lead_actions_keyboard,
)
from src.utils.service_entry import entry_screen_for_service
from src.utils.ui_flow import format_step, ui_send_persistent, ui_upsert
from src.utils.quick_choices import extract_quick_choices

router = Router()


class ClubApply(StatesGroup):
    waiting_for_answer = State()


_CLUB_QUESTIONS: List[Tuple[str, str]] = [
    (
        "format",
        "1) Формат: партнёрство или агентская программа? (партнёр/агент)",
    ),
    (
        "sphere",
        "2) В какой сфере интересует сотрудничество? (логистика/субсидии/транзакции/финансирование)",
    ),
    (
        "who",
        "3) Кто вы? (вебмастер/ВЭД-специалист/агентская сеть/сотрудник/другое)",
    ),
    (
        "value",
        "4) Опишите кратко: как приводите клиентов/какие задачи закрываете? (1–2 фразы)",
    ),
    (
        "volume",
        "5) Ожидаемый объём: сколько заявок/клиентов в месяц? (оценка)",
    ),
]


async def _render_club_step(
    *,
    bot,
    state: FSMContext,
    chat_id: int,
    title: str,
    step: int,
    total: int,
    question: str,
    back_cb: str,
    prefer_message_id: int | None = None,
    intro: str | None = None,
    persist: bool = False,
    session: AsyncSession | None = None,
    user_id: int | None = None,
    username: str | None = None,
) -> None:
    choices = extract_quick_choices(question)
    if choices:
        await state.update_data(qc_ctx="club", qc_choices=choices)
        kb = flow_nav_with_choices_keyboard(
            back_callback_data=back_cb,
            choices=choices,
            choice_callback_prefix="qc:club",
        )
    else:
        await state.update_data(qc_ctx="", qc_choices=[])
        kb = flow_nav_keyboard(back_cb)

    await ui_upsert(
        bot=bot,
        state=state,
        chat_id=chat_id,
        prefer_message_id=prefer_message_id,
        text=format_step(
            title=title, step=step, total=total, intro=intro, question=question
        ),
        reply_markup=kb,
        keep_at_bottom=True,
        persist=persist,
        session=session,
        user_id=user_id,
        username=username,
    )


async def _process_club_answer_text(
    *,
    text: str,
    bot,
    state: FSMContext,
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    username: str | None,
    user_message_id: int | None,
) -> None:
    t = (text or "").strip()
    if not t:
        return

    data = await state.get_data()
    step = int(data.get("club_step", 0))
    answers: Dict[str, str] = dict(data.get("club_answers") or {})
    service_key = (
        data.get("service_key")
        if isinstance(data.get("service_key"), str)
        else "club_partnership"
    )

    if step < 0 or step >= len(_CLUB_QUESTIONS):
        await state.clear()
        return

    key, q_text = _CLUB_QUESTIONS[step]
    answers[key] = t[:700]

    await UserMemory.add_message(session, user_id, "user", f"{q_text}\nОтвет: {t}")
    await DialogMessage.create(
        session,
        user_id=user_id,
        username=username,
        full_name=None,
        phone=None,
        message_text=t,
        role="user",
        chat_id=chat_id,
        message_id=user_message_id,
    )

    step += 1
    await state.update_data(club_step=step, club_answers=answers)

    if step < len(_CLUB_QUESTIONS):
        await _render_club_step(
            bot=bot,
            state=state,
            chat_id=chat_id,
            title="SRVT • Клуб / партнёрство",
            step=step + 1,
            total=len(_CLUB_QUESTIONS),
            question=_CLUB_QUESTIONS[step][1],
            back_cb="club:apply:back",
            persist=True,
            session=session,
            user_id=user_id,
            username=username,
        )
        return

    result = (
        "Готово ✅\n\n"
        "Дальше менеджер SRVT:\n"
        "- уточнит условия сотрудничества\n"
        "- закрепит куратора и формат работы через CRM\n"
        "- предложит офферы/материалы под вашу аудиторию\n\n"
        "Оставьте контакт + удобное время для созвона — передам заявку."
    )

    summary_lines = ["SRVT • Партнёрство / агентская программа"]
    for k, q in _CLUB_QUESTIONS:
        summary_lines.append(f"{q}\nОтвет: {answers.get(k, '')}")
    summary_lines.append(
        "SRVT обещание: персональный менеджер свяжется в ближайшее время (в рабочее время)."
    )
    summary_text = "\n\n".join(summary_lines)

    await log_event(
        session,
        user_id=user_id,
        chat_id=chat_id,
        username=username,
        event="club_apply_complete",
        service_key=service_key,
    )

    await UserMemory.add_message(session, user_id, "system", summary_text)
    await state.update_data(questionnaire_summary=summary_text)

    await ui_send_persistent(
        bot=bot,
        state=state,
        chat_id=chat_id,
        text=result,
        reply_markup=lead_actions_keyboard(service_key),
        parse_mode=None,
        persist=True,
        session=session,
        user_id=user_id,
        username=username,
    )


@router.callback_query(F.data == "club:apply:back")
async def club_apply_back(callback: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    if current != ClubApply.waiting_for_answer.state:
        await callback.answer()
        return

    data = await state.get_data()
    step = int(data.get("club_step", 0))
    answers: Dict[str, str] = dict(data.get("club_answers") or {})
    service_key = (
        data.get("service_key")
        if isinstance(data.get("service_key"), str)
        else "club_partnership"
    )

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
    key, _ = _CLUB_QUESTIONS[new_step]
    answers.pop(key, None)
    await state.update_data(club_step=new_step, club_answers=answers)

    await _render_club_step(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        title="SRVT • Клуб / партнёрство",
        step=new_step + 1,
        total=len(_CLUB_QUESTIONS),
        question=_CLUB_QUESTIONS[new_step][1],
        back_cb="club:apply:back",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("club:apply:start:"))
async def start_club_apply(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    service_key = (
        (callback.data or "").split("club:apply:start:", 1)[-1].strip()
    )
    if not service_key:
        service_key = "club_partnership"

    await state.set_state(ClubApply.waiting_for_answer)
    await state.update_data(
        service_key=service_key, club_step=0, club_answers={}
    )

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="club_apply_start",
        service_key=service_key,
    )

    await _render_club_step(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        title="SRVT • Клуб / партнёрство",
        step=1,
        total=len(_CLUB_QUESTIONS),
        intro="Ок, быстро уточню детали и передам менеджеру SRVT. Это займёт ~1 минуту.",
        question=_CLUB_QUESTIONS[0][1],
        back_cb="club:apply:back",
        persist=True,
        session=session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qc:club:"))
async def club_quick_choice(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    try:
        await callback.answer()
    except Exception:
        pass
    current = await state.get_state()
    if current != ClubApply.waiting_for_answer.state:
        return

    raw = (callback.data or "").split("qc:club:", 1)[-1].strip()
    try:
        idx = int(raw)
    except ValueError:
        return

    data = await state.get_data()
    if data.get("qc_ctx") != "club":
        return
    choices = data.get("qc_choices") or []
    if not isinstance(choices, list) or idx < 0 or idx >= len(choices):
        return
    answer = str(choices[idx])

    await _process_club_answer_text(
        text=answer,
        bot=callback.message.bot,
        state=state,
        session=session,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        user_message_id=None,
    )


@router.message(ClubApply.waiting_for_answer)
async def handle_club_apply_answer(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _process_club_answer_text(
        text=message.text or "",
        bot=message.bot,
        state=state,
        session=session,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        username=message.from_user.username,
        user_message_id=message.message_id,
    )

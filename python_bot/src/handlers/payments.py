from __future__ import annotations

from typing import Dict, List, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dialog_message import DialogMessage
from src.models.user_memory import UserMemory
from src.services.subsidy_calc import parse_money_rub
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


class PaymentsPrecheck(StatesGroup):
    waiting_for_answer = State()


_PAYMENTS_QUESTIONS: List[Tuple[str, str]] = [
    (
        "direction",
        "1) Направление: отправить из РФ или получить в РФ? (отправить/получить)",
    ),
    ("country", "2) Страна контрагента (куда/откуда)"),
    ("amount", "3) Сумма и валюта. Пример: «25 000 USD» или «1,2 млн ₽»"),
    (
        "purpose",
        "4) Назначение платежа (товар/услуги/ПО/роялти/другое) + кратко что за сделка",
    ),
    (
        "docs",
        "5) Есть контракт/инвойс и насколько срочно? (да/нет/в процессе + сегодня/1–3 дня/неделя+)",
    ),
]


def _has_any_amount(text: str) -> bool:
    # Accept any digits, not only rubles
    return any(ch.isdigit() for ch in (text or ""))


async def _render_payments_step(
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
        await state.update_data(qc_ctx="payments", qc_choices=choices)
        kb = flow_nav_with_choices_keyboard(
            back_callback_data=back_cb,
            choices=choices,
            choice_callback_prefix="qc:payments",
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


async def _process_payments_answer_text(
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
    step = int(data.get("pay_step", 0))
    answers: Dict[str, str] = dict(data.get("pay_answers") or {})
    service_key = (
        data.get("service_key")
        if isinstance(data.get("service_key"), str)
        else "international_payments"
    )

    if step < 0 or step >= len(_PAYMENTS_QUESTIONS):
        await state.clear()
        return

    key, q_text = _PAYMENTS_QUESTIONS[step]
    if key == "amount" and not _has_any_amount(t):
        await _render_payments_step(
            bot=bot,
            state=state,
            chat_id=chat_id,
            title="SRVT • Международные платежи",
            step=step + 1,
            total=len(_PAYMENTS_QUESTIONS),
            intro="Ошибка: не вижу сумму. Пример: «25 000 USD» или «1,2 млн ₽».",
            question=q_text,
            back_cb="payments:precheck:back",
            persist=True,
            session=session,
            user_id=user_id,
            username=username,
        )
        return

    answers[key] = t[:600]

    # Persist user answer
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
    await state.update_data(pay_step=step, pay_answers=answers)

    if step < len(_PAYMENTS_QUESTIONS):
        await _render_payments_step(
            bot=bot,
            state=state,
            chat_id=chat_id,
            title="SRVT • Международные платежи",
            step=step + 1,
            total=len(_PAYMENTS_QUESTIONS),
            question=_PAYMENTS_QUESTIONS[step][1],
            back_cb="payments:precheck:back",
            persist=True,
            session=session,
            user_id=user_id,
            username=username,
        )
        return

    # Complete: produce a short plan and move to lead
    plan = (
        "Готово ✅\n\n"
        "Что сделаем дальше:\n"
        "1) Проверим допустимость маршрута по вашей стране/назначению и комплект документов.\n"
        "2) Подберём оптимальный вариант проведения платежа и сроки.\n"
        "3) Зафиксируем условия и передадим на сопровождение.\n\n"
        "Чтобы менеджер SRVT связался с вами — оставьте контакт + удобное время для созвона."
    )

    summary_lines = ["SRVT • Оценка международного платежа (pre-check)"]
    for k, q in _PAYMENTS_QUESTIONS:
        summary_lines.append(f"{q}\nОтвет: {answers.get(k, '')}")

    # quick extra: if user provided rubles amount, mention it in summary for manager
    rub = None
    if answers.get("amount"):
        rub_values = parse_money_rub(answers["amount"])
        rub = max(rub_values) if rub_values else None
    if rub:
        summary_lines.append(f"(детект) Сумма в ₽: ~{rub:,}".replace(",", " "))

    summary_lines.append(
        "SRVT обещание: персональный менеджер свяжется в ближайшее время (в рабочее время)."
    )
    summary_text = "\n\n".join(summary_lines)

    await log_event(
        session,
        user_id=user_id,
        chat_id=chat_id,
        username=username,
        event="payments_precheck_complete",
        service_key=service_key,
    )

    await UserMemory.add_message(session, user_id, "system", summary_text)
    await state.update_data(questionnaire_summary=summary_text)

    await ui_send_persistent(
        bot=bot,
        state=state,
        chat_id=chat_id,
        text=plan,
        reply_markup=lead_actions_keyboard(service_key),
        parse_mode=None,
        persist=True,
        session=session,
        user_id=user_id,
        username=username,
    )


@router.callback_query(F.data == "payments:precheck:back")
async def payments_precheck_back(
    callback: CallbackQuery, state: FSMContext
) -> None:
    current = await state.get_state()
    if current != PaymentsPrecheck.waiting_for_answer.state:
        await callback.answer()
        return

    data = await state.get_data()
    step = int(data.get("pay_step", 0))
    answers: Dict[str, str] = dict(data.get("pay_answers") or {})
    service_key = (
        data.get("service_key")
        if isinstance(data.get("service_key"), str)
        else "international_payments"
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
    key, _ = _PAYMENTS_QUESTIONS[new_step]
    answers.pop(key, None)
    await state.update_data(pay_step=new_step, pay_answers=answers)

    await _render_payments_step(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        title="SRVT • Международные платежи",
        step=new_step + 1,
        total=len(_PAYMENTS_QUESTIONS),
        question=_PAYMENTS_QUESTIONS[new_step][1],
        back_cb="payments:precheck:back",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("payments:precheck:start:"))
async def start_payments_precheck(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    service_key = (
        (callback.data or "").split("payments:precheck:start:", 1)[-1].strip()
    )
    if not service_key:
        service_key = "international_payments"

    await state.set_state(PaymentsPrecheck.waiting_for_answer)
    await state.update_data(
        service_key=service_key, pay_step=0, pay_answers={}
    )

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="payments_precheck_start",
        service_key=service_key,
    )

    await _render_payments_step(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        title="SRVT • Международные платежи",
        step=1,
        total=len(_PAYMENTS_QUESTIONS),
        intro="Ок, быстро уточню детали и передам менеджеру SRVT. Это займёт ~1 минуту.",
        question=_PAYMENTS_QUESTIONS[0][1],
        back_cb="payments:precheck:back",
        persist=True,
        session=session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qc:payments:"))
async def payments_quick_choice(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    try:
        await callback.answer()
    except Exception:
        pass
    current = await state.get_state()
    if current != PaymentsPrecheck.waiting_for_answer.state:
        return

    raw = (callback.data or "").split("qc:payments:", 1)[-1].strip()
    try:
        idx = int(raw)
    except ValueError:
        return

    data = await state.get_data()
    if data.get("qc_ctx") != "payments":
        return
    choices = data.get("qc_choices") or []
    if not isinstance(choices, list) or idx < 0 or idx >= len(choices):
        return
    answer = str(choices[idx])

    await _process_payments_answer_text(
        text=answer,
        bot=callback.message.bot,
        state=state,
        session=session,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        user_message_id=None,
    )


@router.message(PaymentsPrecheck.waiting_for_answer)
async def handle_payments_precheck_answer(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _process_payments_answer_text(
        text=message.text or "",
        bot=message.bot,
        state=state,
        session=session,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        username=message.from_user.username,
        user_message_id=message.message_id,
    )

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dialog_message import DialogMessage
from src.models.user_memory import UserMemory
from src.services.finance_calc import (
    estimate_refinance,
    parse_percent,
    parse_term_months,
)
from src.services.subsidy_calc import parse_money_rub
from src.utils.funnel import log_event
from src.utils.keyboards import (
    flow_nav_keyboard,
    flow_nav_with_choices_keyboard,
    lead_actions_keyboard,
)
from src.utils.service_entry import entry_screen_for_service
from src.utils.ui_flow import format_step, ui_send_persistent, ui_upsert

router = Router()


class FinanceCalc(StatesGroup):
    waiting_for_answer = State()


_FIN_QUESTIONS: List[Tuple[str, str]] = [
    (
        "goal",
        "1) Что нужно: новый кредит или рефинанс? (напишите: новый / рефинанс)",
    ),
    ("amount", "2) Сумма (если рефинанс — остаток долга). Пример: «25 млн ₽»"),
    (
        "rate",
        "3) Текущая ставка (% годовых). Если не знаете — напишите «не знаю»",
    ),
    (
        "term",
        "4) Срок (если рефинанс — остаток; если новый — желаемый). Пример: «36 мес» или «3 года»",
    ),
    ("company", "5) Форма (ООО/ИП) + отрасль (1 фраза)"),
]


def _goal_is_refi(raw: str) -> bool:
    t = (raw or "").strip().lower()
    return "рефин" in t or "реф" in t


def _first_money(text: str) -> Optional[int]:
    values = parse_money_rub(text)
    return max(values) if values else None


async def _render_finance_step(
    *,
    bot,
    state: FSMContext,
    chat_id: int,
    title: str,
    step: int,
    total: int,
    question_key: str | None = None,
    question: str,
    back_cb: str,
    prefer_message_id: int | None = None,
    intro: str | None = None,
    persist: bool = False,
    session: AsyncSession | None = None,
    user_id: int | None = None,
    username: str | None = None,
) -> None:
    explicit: dict[str, list[str]] = {
        "goal": ["новый", "рефинанс"],
    }
    choices = explicit.get(question_key or "", [])
    if choices:
        await state.update_data(qc_ctx="finance", qc_choices=choices)
        kb = flow_nav_with_choices_keyboard(
            back_callback_data=back_cb,
            choices=choices,
            choice_callback_prefix="qc:finance",
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


async def _process_finance_answer_text(
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
    step = int(data.get("fin_step", 0))
    answers: Dict[str, str] = dict(data.get("fin_answers") or {})

    if step < 0 or step >= len(_FIN_QUESTIONS):
        await state.clear()
        return

    key, q_text = _FIN_QUESTIONS[step]

    # validation
    if key == "amount":
        if _first_money(t) is None:
            await _render_finance_step(
                bot=bot,
                state=state,
                chat_id=chat_id,
                title="SRVT • Финансирование / рефинанс",
                step=step + 1,
                total=len(_FIN_QUESTIONS),
                intro="Ошибка: не вижу сумму. Пример: «25 млн ₽» или «12 500 000».",
                question=q_text,
                back_cb="finance:calc:back",
                persist=True,
                session=session,
                user_id=user_id,
                username=username,
            )
            return
    if key == "rate" and t.lower() not in {
        "не знаю",
        "незнаю",
        "не знаю.",
        "нет",
    }:
        if parse_percent(t) is None:
            await _render_finance_step(
                bot=bot,
                state=state,
                chat_id=chat_id,
                title="SRVT • Финансирование / рефинанс",
                step=step + 1,
                total=len(_FIN_QUESTIONS),
                intro="Ошибка: не вижу % ставку. Пример: «18%» или «16.5».",
                question=q_text,
                back_cb="finance:calc:back",
                persist=True,
                session=session,
                user_id=user_id,
                username=username,
            )
            return
    if key == "term":
        if parse_term_months(t) is None:
            await _render_finance_step(
                bot=bot,
                state=state,
                chat_id=chat_id,
                title="SRVT • Финансирование / рефинанс",
                step=step + 1,
                total=len(_FIN_QUESTIONS),
                intro="Ошибка: не вижу срок. Пример: «36 мес» или «3 года».",
                question=q_text,
                back_cb="finance:calc:back",
                persist=True,
                session=session,
                user_id=user_id,
                username=username,
            )
            return

    answers[key] = t[:500]

    # Persist user answer for traceability
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
    await state.update_data(fin_step=step, fin_answers=answers)

    if step < len(_FIN_QUESTIONS):
        await _render_finance_step(
            bot=bot,
            state=state,
            chat_id=chat_id,
            title="SRVT • Финансирование / рефинанс",
            step=step + 1,
            total=len(_FIN_QUESTIONS),
            question_key=_FIN_QUESTIONS[step][0],
            question=_FIN_QUESTIONS[step][1],
            back_cb="finance:calc:back",
            persist=True,
            session=session,
            user_id=user_id,
            username=username,
        )
        return

    # Compute estimate (refi-focused, but still useful for new credit as "next steps")
    goal = answers.get("goal", "")
    principal = _first_money(answers.get("amount", "")) or 0
    rate = parse_percent(answers.get("rate", "")) if answers.get("rate") else None
    term = parse_term_months(answers.get("term", "")) if answers.get("term") else None

    is_refi = _goal_is_refi(goal)
    estimate_text = ""

    if is_refi:
        est = estimate_refinance(
            principal_rub=principal, current_rate=rate, term_months=term
        )
        if est.savings_range_rub_per_year:
            lo, hi = est.savings_range_rub_per_year
            estimate_text = (
                "📌 Предварительная оценка экономии при снижении ставки на 2–5 п.п.:\n"
                f"≈ {lo:,} – {hi:,} ₽/год\n\n{est.note}"
            ).replace(",", " ")
        else:
            estimate_text = f"📌 Предварительная оценка: {est.note}"
    else:
        estimate_text = (
            "📌 Предварительная оценка: по вашему запросу можно подобрать льготные программы и банки‑партнёры SRVT.\n"
            "Чтобы дать расчёт по сумме/ставке точнее — нужно уточнить 2–3 параметра на созвоне."
        )

    # Build summary for Bitrix/comments and reuse lead flow
    summary_lines = ["SRVT • Рассчитать финансирование/рефинанс"]
    for k, q in _FIN_QUESTIONS:
        summary_lines.append(f"{q}\nОтвет: {answers.get(k, '')}")
    summary_lines.append(estimate_text)
    summary_lines.append(
        "SRVT обещание: предварительное решение по заявке в течение дня (в рабочее время)."
    )
    summary_text = "\n\n".join(summary_lines)

    await log_event(
        session,
        user_id=user_id,
        chat_id=chat_id,
        username=username,
        event="finance_calc_complete",
        service_key="subsidies_financing",
    )

    await UserMemory.add_message(session, user_id, "system", summary_text)
    await state.update_data(questionnaire_summary=summary_text)

    estimate_text = (
        f"{estimate_text}\n\n"
        "Хотите подобрать программу/банк и посчитать точнее? Нажмите «📩 Оставить заявку» — "
        "персональный менеджер SRVT свяжется (в рабочее время)."
    )
    await ui_send_persistent(
        bot=bot,
        state=state,
        chat_id=chat_id,
        text=estimate_text,
        reply_markup=lead_actions_keyboard("subsidies_financing"),
        parse_mode=None,
        persist=True,
        session=session,
        user_id=user_id,
        username=username,
    )


@router.callback_query(F.data == "finance:calc:back")
async def finance_calc_back(
    callback: CallbackQuery, state: FSMContext
) -> None:
    # Back within finance calc flow
    current = await state.get_state()
    if current != FinanceCalc.waiting_for_answer.state:
        await callback.answer()
        return

    data = await state.get_data()
    step = int(data.get("fin_step", 0))
    answers: Dict[str, str] = dict(data.get("fin_answers") or {})
    service_key = (
        data.get("service_key")
        if isinstance(data.get("service_key"), str)
        else "subsidies_financing"
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
    key, _ = _FIN_QUESTIONS[new_step]
    answers.pop(key, None)
    await state.update_data(fin_step=new_step, fin_answers=answers)

    await _render_finance_step(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        title="SRVT • Финансирование / рефинанс",
        step=new_step + 1,
        total=len(_FIN_QUESTIONS),
        question_key=_FIN_QUESTIONS[new_step][0],
        question=_FIN_QUESTIONS[new_step][1],
        back_cb="finance:calc:back",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("finance:calc:start:"))
async def start_finance_calc(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    service_key = (
        (callback.data or "").split("finance:calc:start:", 1)[-1].strip()
    )
    if not service_key:
        service_key = "subsidies_financing"

    await state.set_state(FinanceCalc.waiting_for_answer)
    await state.update_data(
        service_key=service_key, fin_step=0, fin_answers={}
    )

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="finance_calc_start",
        service_key=service_key,
    )

    text = format_step(
        title="SRVT • Финансирование / рефинанс",
        step=1,
        total=len(_FIN_QUESTIONS),
        intro="Ок, сделаю предварительный расчёт. Это займёт ~2 минуты. Отвечайте коротко.",
        question=_FIN_QUESTIONS[0][1],
    )
    await _render_finance_step(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        title="SRVT • Финансирование / рефинанс",
        step=1,
        total=len(_FIN_QUESTIONS),
        intro="Ок, сделаю предварительный расчёт. Это займёт ~2 минуты. Отвечайте коротко.",
        question_key=_FIN_QUESTIONS[0][0],
        question=_FIN_QUESTIONS[0][1],
        back_cb="finance:calc:back",
        persist=True,
        session=session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qc:finance:"))
async def finance_quick_choice(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    try:
        await callback.answer()
    except Exception:
        pass
    current = await state.get_state()
    if current != FinanceCalc.waiting_for_answer.state:
        return

    raw = (callback.data or "").split("qc:finance:", 1)[-1].strip()
    try:
        idx = int(raw)
    except ValueError:
        return

    data = await state.get_data()
    if data.get("qc_ctx") != "finance":
        return
    choices = data.get("qc_choices") or []
    if not isinstance(choices, list) or idx < 0 or idx >= len(choices):
        return
    answer = str(choices[idx])

    await _process_finance_answer_text(
        text=answer,
        bot=callback.message.bot,
        state=state,
        session=session,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        user_message_id=None,
    )


@router.message(FinanceCalc.waiting_for_answer)
async def handle_finance_calc_answer(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _process_finance_answer_text(
        text=message.text or "",
        bot=message.bot,
        state=state,
        session=session,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        username=message.from_user.username,
        user_message_id=message.message_id,
    )

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dialog_message import DialogMessage
from src.models.user_memory import UserMemory
from src.services.subsidy_calc import parse_money_rub
from src.utils.funnel import log_event
from src.utils.keyboards import flow_nav_keyboard, lead_actions_keyboard, services_keyboard
from src.utils.messages import msg
from src.utils.ui_flow import format_step, ui_upsert

router = Router()


class PaymentsPrecheck(StatesGroup):
    waiting_for_answer = State()


_PAYMENTS_QUESTIONS: List[Tuple[str, str]] = [
    ("direction", "1) Направление: отправить из РФ или получить в РФ? (отправить/получить)"),
    ("country", "2) Страна контрагента (куда/откуда)"),
    ("amount", "3) Сумма и валюта. Пример: «25 000 USD» или «1,2 млн ₽»"),
    ("purpose", "4) Назначение платежа (товар/услуги/ПО/роялти/другое) + кратко что за сделка"),
    ("docs", "5) Есть контракт/инвойс? (да/нет/в процессе)"),
    ("urgency", "6) Срочность: сегодня / 1–3 дня / неделя+"),
]


def _has_any_amount(text: str) -> bool:
    # Accept any digits, not only rubles
    return any(ch.isdigit() for ch in (text or ""))


@router.callback_query(F.data == "payments:precheck:back")
async def payments_precheck_back(callback: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    if current != PaymentsPrecheck.waiting_for_answer.state:
        await callback.answer()
        return

    data = await state.get_data()
    step = int(data.get("pay_step", 0))
    answers: Dict[str, str] = dict(data.get("pay_answers") or {})

    if step <= 0:
        await state.clear()
        try:
            await callback.message.edit_text(msg("choose_service"), reply_markup=services_keyboard())
        except Exception:
            await callback.message.answer(msg("choose_service"), reply_markup=services_keyboard())
        await callback.answer()
        return

    new_step = step - 1
    key, _ = _PAYMENTS_QUESTIONS[new_step]
    answers.pop(key, None)
    await state.update_data(pay_step=new_step, pay_answers=answers)

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Международные платежи",
            step=new_step + 1,
            total=len(_PAYMENTS_QUESTIONS),
            question=_PAYMENTS_QUESTIONS[new_step][1],
        ),
        reply_markup=flow_nav_keyboard(None if new_step <= 0 else "payments:precheck:back"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("payments:precheck:start:"))
async def start_payments_precheck(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    service_key = (callback.data or "").split("payments:precheck:start:", 1)[-1].strip()
    if not service_key:
        service_key = "international_payments"

    await state.set_state(PaymentsPrecheck.waiting_for_answer)
    await state.update_data(service_key=service_key, pay_step=0, pay_answers={})

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="payments_precheck_start",
        service_key=service_key,
    )

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Международные платежи",
            step=1,
            total=len(_PAYMENTS_QUESTIONS),
            intro="Ок, быстро уточню детали и передам менеджеру SRVT. Это займёт ~1 минуту.",
            question=_PAYMENTS_QUESTIONS[0][1],
        ),
        reply_markup=flow_nav_keyboard(None),
    )
    await callback.answer()


@router.message(PaymentsPrecheck.waiting_for_answer)
async def handle_payments_precheck_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    step = int(data.get("pay_step", 0))
    answers: Dict[str, str] = dict(data.get("pay_answers") or {})
    service_key = data.get("service_key") if isinstance(data.get("service_key"), str) else "international_payments"

    if step < 0 or step >= len(_PAYMENTS_QUESTIONS):
        await state.clear()
        return

    key, q_text = _PAYMENTS_QUESTIONS[step]
    if key == "amount" and not _has_any_amount(text):
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Международные платежи",
                step=step + 1,
                total=len(_PAYMENTS_QUESTIONS),
                intro="Ошибка: не вижу сумму. Пример: «25 000 USD» или «1,2 млн ₽».",
                question=q_text,
            ),
            reply_markup=flow_nav_keyboard("payments:precheck:back" if step > 0 else None),
        )
        return

    answers[key] = text[:600]

    # Persist user answer
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
    await state.update_data(pay_step=step, pay_answers=answers)

    if step < len(_PAYMENTS_QUESTIONS):
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Международные платежи",
                step=step + 1,
                total=len(_PAYMENTS_QUESTIONS),
                question=_PAYMENTS_QUESTIONS[step][1],
            ),
            reply_markup=flow_nav_keyboard("payments:precheck:back" if step > 0 else None),
        )
        return

    # Complete: produce a short plan and move to lead
    plan = (
        "Готово ✅\n\n"
        "Что сделаем дальше:\n"
        "1) Проверим допустимость маршрута по вашей стране/назначению и комплект документов.\n"
        "2) Подберём оптимальный вариант проведения платежа и сроки.\n"
        "3) Зафиксируем условия и передадим на сопровождение.\n\n"
        "Чтобы менеджер SRVT связался с вами — оставьте контакт + удобное окно созвона."
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

    summary_lines.append("SRVT обещание: персональный менеджер свяжется в течение 15 минут (в рабочее время).")
    summary_text = "\n\n".join(summary_lines)

    await log_event(
        session,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        username=message.from_user.username,
        event="payments_precheck_complete",
        service_key=service_key,
    )

    await UserMemory.add_message(session, message.from_user.id, "system", summary_text)
    await state.update_data(questionnaire_summary=summary_text)

    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=plan,
        reply_markup=lead_actions_keyboard(service_key),
        parse_mode=None,
    )



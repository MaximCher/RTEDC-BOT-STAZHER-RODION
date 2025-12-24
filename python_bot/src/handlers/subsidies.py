from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai_agent import AIAgent
from src.models.dialog_message import DialogMessage
from src.models.user_memory import UserMemory
from src.services.subsidy_calc import (
    estimate_from_context,
    format_estimates,
    parse_money_rub,
    parse_spend_from_question,
)
from src.utils.messages import msg
from src.utils.funnel import log_event
from src.config import SERVICE_FLOWS
from src.utils.keyboards import (
    flow_nav_keyboard,
    lead_actions_keyboard,
    services_keyboard,
    subsidy_chat_keyboard,
    subsidies_entry_keyboard,
)
from src.utils.ui_flow import format_step, ui_upsert
from src.vector_store import VectorStore

router = Router()


class SubsidyChat(StatesGroup):
    waiting_for_question = State()


class SubsidyCalc(StatesGroup):
    waiting_for_answer = State()


_SUBSIDY_CALC_QUESTIONS: List[Tuple[str, str]] = [
    ("region", "1) Регион регистрации/реализации проекта (город/область)"),
    ("company_type", "2) Форма компании: ООО / ИП / самозанятый / пока нет"),
    ("industry", "3) Отрасль/вид деятельности (1–2 фразы)"),
    (
        "spend_type",
        "4) Что хотим компенсировать? (оборудование/логистика/сертификация/маркетинг/НИОКР/ФОТ/выставки/другое)",
    ),
    ("budget", "5) Бюджет расходов/проекта (диапазон или сумма в ₽)"),
    ("export", "6) Есть экспорт или план экспорта? (да/нет). Если да — страны"),
    ("timeline", "7) Срок: когда актуально? (сейчас/в течение месяца/позже)"),
]


def _first_money(text: str) -> Optional[int]:
    values = parse_money_rub(text)
    return max(values) if values else None


def _build_subsidy_query(answers: Dict[str, str]) -> str:
    parts = [
        "субсидия компенсация",
        answers.get("spend_type", "").strip(),
        answers.get("industry", "").strip(),
        answers.get("region", "").strip(),
        answers.get("export", "").strip(),
        "процент лимит",
    ]
    return " ".join([p for p in parts if p])


@router.callback_query(F.data == "subsidy:calc:back")
async def subsidy_calc_back(callback: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    if current != SubsidyCalc.waiting_for_answer.state:
        await callback.answer()
        return

    data = await state.get_data()
    step = int(data.get("calc_step", 0))
    answers: Dict[str, str] = dict(data.get("calc_answers") or {})

    if step <= 0:
        await state.clear()
        try:
            await callback.message.edit_text(msg("choose_service"), reply_markup=services_keyboard())
        except Exception:
            await callback.message.answer(msg("choose_service"), reply_markup=services_keyboard())
        await callback.answer()
        return

    new_step = step - 1
    key, _ = _SUBSIDY_CALC_QUESTIONS[new_step]
    answers.pop(key, None)
    await state.update_data(calc_step=new_step, calc_answers=answers)

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Расчёт субсидии",
            step=new_step + 1,
            total=len(_SUBSIDY_CALC_QUESTIONS),
            question=_SUBSIDY_CALC_QUESTIONS[new_step][1],
        ),
        reply_markup=flow_nav_keyboard("subsidy:calc:back"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("subsidy:calc:start:"))
async def start_subsidy_calc(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    service_key = (callback.data or "").split("subsidy:calc:start:", 1)[-1].strip()
    if not service_key:
        service_key = "subsidies_financing"

    await state.set_state(SubsidyCalc.waiting_for_answer)
    await state.update_data(service_key=service_key, calc_step=0, calc_answers={})

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="subsidy_calc_start",
        service_key=service_key,
    )

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Расчёт субсидии",
            step=1,
            total=len(_SUBSIDY_CALC_QUESTIONS),
            intro=msg("subsidy_calc_intro"),
            question=_SUBSIDY_CALC_QUESTIONS[0][1],
        ),
        reply_markup=flow_nav_keyboard("subsidy:calc:back"),
    )
    await callback.answer()


@router.message(SubsidyCalc.waiting_for_answer)
async def handle_subsidy_calc_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user_id = message.from_user.id
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    step = int(data.get("calc_step", 0))
    answers: Dict[str, str] = dict(data.get("calc_answers") or {})

    if step < 0 or step >= len(_SUBSIDY_CALC_QUESTIONS):
        await state.clear()
        return

    key, q_text = _SUBSIDY_CALC_QUESTIONS[step]

    # Basic validation: budget must contain a number
    if key == "budget":
        if _first_money(text) is None:
            await ui_upsert(
                bot=message.bot,
                state=state,
                chat_id=message.chat.id,
                text=format_step(
                    title="SRVT • Расчёт субсидии",
                    step=step + 1,
                    total=len(_SUBSIDY_CALC_QUESTIONS),
                    intro="Ошибка: не вижу сумму/диапазон в ₽. Пример: «3–5 млн ₽» или «2 500 000».",
                    question=q_text,
                ),
                reply_markup=flow_nav_keyboard("subsidy:calc:back"),
            )
            return

    answers[key] = text[:500]

    # Persist for traceability
    await UserMemory.add_message(session, user_id, "user", f"{q_text}\nОтвет: {text}")
    await DialogMessage.create(
        session,
        user_id=user_id,
        username=message.from_user.username,
        full_name=None,
        phone=None,
        message_text=text,
        role="user",
        chat_id=message.chat.id,
        message_id=message.message_id,
    )

    step += 1
    await state.update_data(calc_step=step, calc_answers=answers)

    if step < len(_SUBSIDY_CALC_QUESTIONS):
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Расчёт субсидии",
                step=step + 1,
                total=len(_SUBSIDY_CALC_QUESTIONS),
                question=_SUBSIDY_CALC_QUESTIONS[step][1],
            ),
            reply_markup=flow_nav_keyboard("subsidy:calc:back"),
        )
        return

    # Complete: compute estimate using RAG context where possible
    spend = _first_money(answers.get("budget", "")) or 0
    query = _build_subsidy_query(answers)
    vector_store = VectorStore(session)
    vector_context = await vector_store.get_context_for_query(query, limit=6, max_context_length=2200)

    calc_text = ""
    if vector_context and spend > 0:
        calc_text = format_estimates(estimate_from_context(vector_context, spend_rub=spend, top_k=3))

    # Build summary for Bitrix/comments and reuse lead flow
    summary_lines = ["SRVT • Рассчитать объём субсидии"]
    for k, q in _SUBSIDY_CALC_QUESTIONS:
        summary_lines.append(f"{q}\nОтвет: {answers.get(k, '')}")
    if calc_text:
        summary_lines.append(calc_text)
    else:
        summary_lines.append(msg("subsidy_calc_no_context"))
    summary_text = "\n\n".join(summary_lines)

    await log_event(
        session,
        user_id=user_id,
        chat_id=message.chat.id,
        username=message.from_user.username,
        event="subsidy_calc_complete",
        service_key="subsidies_financing",
    )
    await UserMemory.add_message(session, user_id, "system", summary_text)

    await state.update_data(questionnaire_summary=summary_text)

    # Result message
    if calc_text:
        result = f"{msg('subsidy_calc_result_header')}\n\n{calc_text}"
    else:
        result = f"{msg('subsidy_calc_result_header')}\n\n{msg('subsidy_calc_no_context')}"

    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=result,
        reply_markup=lead_actions_keyboard("subsidies_financing"),
        parse_mode=None,
    )


@router.callback_query(F.data.startswith("subsidy:chat:start:"))
async def start_subsidy_chat(callback: CallbackQuery, state: FSMContext) -> None:
    service_key = (callback.data or "").split("subsidy:chat:start:", 1)[-1].strip()
    await state.set_state(SubsidyChat.waiting_for_question)
    await state.update_data(service_key=service_key)
    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Вопрос по субсидиям",
            step=1,
            total=1,
            question=(
                "Напишите вопрос по субсидиям/мерам поддержки — я подберу релевантные фрагменты из базы знаний и отвечу.\n"
                "Если есть цифры (бюджет/расходы) — добавьте их в вопрос, тогда смогу прикинуть порядок суммы."
            ),
        ),
        reply_markup=flow_nav_keyboard("subsidy:chat:back"),
    )
    await callback.answer()


@router.callback_query(F.data == "subsidy:chat:back")
async def subsidy_chat_back(callback: CallbackQuery, state: FSMContext) -> None:
    # Return to subsidies entry screen (within the subsidies service)
    await state.clear()
    flow = SERVICE_FLOWS.get("subsidies_financing") or {}
    text = flow.get("description") or msg("choose_service")
    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=text,
        reply_markup=subsidies_entry_keyboard(),
        parse_mode=None,
    )
    await callback.answer()


@router.message(SubsidyChat.waiting_for_question)
async def handle_subsidy_question(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    user_id = message.from_user.id
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    service_key = data.get("service_key") if isinstance(data.get("service_key"), str) else None
    service_key = service_key or "subsidies_financing"

    await UserMemory.add_message(session, user_id, "user", text)
    await DialogMessage.create(
        session,
        user_id=user_id,
        username=message.from_user.username,
        full_name=None,
        phone=None,
        message_text=text,
        role="user",
        chat_id=message.chat.id,
        message_id=message.message_id,
    )

    vector_store = VectorStore(session)
    vector_context = await vector_store.get_context_for_query(text, limit=5, max_context_length=1800)
    history = await UserMemory.get_conversation_history(session, user_id, limit=10)

    calc_text = ""
    spend = parse_spend_from_question(text)
    if spend and vector_context:
        calc_text = format_estimates(estimate_from_context(vector_context, spend_rub=spend, top_k=3))

    agent = AIAgent()
    answer = await agent.generate_subsidy_answer(
        user_message=text,
        conversation_history=history,
        vector_context=vector_context,
        calc_estimates=calc_text or None,
    )
    if not vector_context:
        answer = f"{answer}\n\n(Примечание: в базе знаний нет точного совпадения — ответ общий.)"

    await UserMemory.add_message(session, user_id, "assistant", answer)
    await DialogMessage.create(
        session,
        user_id=user_id,
        username=message.from_user.username,
        full_name=None,
        phone=None,
        message_text=answer,
        role="assistant",
        chat_id=message.chat.id,
        message_id=None,
    )

    # Keep "one-screen" UX: render answer in the same editable message.
    safe_answer = answer.strip()
    if len(safe_answer) > 3800:
        safe_answer = safe_answer[:3800].rstrip() + "\n\n(…ответ сокращён)"
    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=(
            f"<b>SRVT • Вопрос по субсидиям</b>\n\n"
            f"<b>Вопрос:</b> {text}\n\n"
            f"<b>Ответ:</b>\n{safe_answer}\n\n"
            "Можно задать следующий вопрос — просто напишите его."
        ),
        reply_markup=subsidy_chat_keyboard(service_key),
        parse_mode="HTML",
    )

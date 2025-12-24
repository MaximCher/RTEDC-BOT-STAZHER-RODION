from __future__ import annotations

from typing import Any, Dict, List

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dialog_message import DialogMessage
from src.models.user_memory import UserMemory
from src.utils.keyboards import (
    analytics_entry_keyboard,
    back_to_menu_keyboard,
    club_entry_keyboard,
    lead_actions_keyboard,
    logistics_entry_keyboard,
    payments_entry_keyboard,
    quick_audit_entry_keyboard,
    subsidies_entry_keyboard,
)
from src.utils.messages import msg
from src.utils.funnel import log_event

from src.config import SERVICE_FLOWS, SERVICES
from src.utils.ui_flow import format_step, ui_upsert

router = Router()


class ServiceQuestionnaire(StatesGroup):
    waiting_for_answer = State()


@router.callback_query(F.data.startswith("service:questionnaire:"))
async def handle_service_questionnaire_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    raw = callback.data or ""
    service_key = raw.split("service:questionnaire:", 1)[-1].strip()

    flow = SERVICE_FLOWS.get(service_key)
    if not flow:
        await callback.answer(msg("unknown_service"), show_alert=True)
        return

    user_id = callback.from_user.id
    await UserMemory.update_user_data(session, user_id, selected_service=service_key)
    await UserMemory.add_message(
        session,
        user_id,
        "system",
        f"Клиент начал анкету по направлению: {SERVICES.get(service_key, service_key)}",
    )

    await state.set_state(ServiceQuestionnaire.waiting_for_answer)
    await state.update_data(
        selected_service=service_key,
        questionnaire_index=0,
        questionnaire_answers=[],
    )

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="questionnaire_start",
        service_key=service_key,
    )

    questions: List[str] = flow["questions"]
    text = format_step(
        title=f"SRVT • {SERVICES.get(service_key, service_key)}",
        step=1,
        total=len(questions),
        intro=flow["description"],
        question=questions[0],
    )
    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=text,
        reply_markup=back_to_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("service:"))
async def handle_service_selection(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    raw = callback.data or ""
    service_key = raw.split("service:", 1)[-1].strip()

    flow = SERVICE_FLOWS.get(service_key)
    if not flow:
        await callback.answer(msg("unknown_service"), show_alert=True)
        return

    user_id = callback.from_user.id

    await UserMemory.update_user_data(session, user_id, selected_service=service_key)
    await UserMemory.add_message(
        session,
        user_id,
        "system",
        f"Клиент выбрал направление: {SERVICES.get(service_key, service_key)}",
    )

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="entry_service",
        service_key=service_key,
    )

    # Special SRVT-style entry for subsidies/financing: calculators and quick actions first.
    if service_key == "subsidies_financing":
        await state.clear()
        try:
            await callback.message.edit_text(flow["description"], reply_markup=subsidies_entry_keyboard())
        except Exception:
            await callback.message.answer(flow["description"], reply_markup=subsidies_entry_keyboard())
        await callback.answer()
        return

    if service_key == "international_payments":
        await state.clear()
        try:
            await callback.message.edit_text(flow["description"], reply_markup=payments_entry_keyboard())
        except Exception:
            await callback.message.answer(flow["description"], reply_markup=payments_entry_keyboard())
        await callback.answer()
        return

    if service_key == "logistics_ved":
        await state.clear()
        try:
            await callback.message.edit_text(flow["description"], reply_markup=logistics_entry_keyboard())
        except Exception:
            await callback.message.answer(flow["description"], reply_markup=logistics_entry_keyboard())
        await callback.answer()
        return

    if service_key == "analytics_tnved":
        await state.clear()
        try:
            await callback.message.edit_text(flow["description"], reply_markup=analytics_entry_keyboard())
        except Exception:
            await callback.message.answer(flow["description"], reply_markup=analytics_entry_keyboard())
        await callback.answer()
        return

    if service_key == "quick_audit_inn":
        await state.clear()
        try:
            await callback.message.edit_text(flow["description"], reply_markup=quick_audit_entry_keyboard())
        except Exception:
            await callback.message.answer(flow["description"], reply_markup=quick_audit_entry_keyboard())
        await callback.answer()
        return

    if service_key == "club_partnership":
        await state.clear()
        try:
            await callback.message.edit_text(flow["description"], reply_markup=club_entry_keyboard())
        except Exception:
            await callback.message.answer(flow["description"], reply_markup=club_entry_keyboard())
        await callback.answer()
        return

    await state.set_state(ServiceQuestionnaire.waiting_for_answer)
    await state.update_data(
        selected_service=service_key,
        questionnaire_index=0,
        questionnaire_answers=[],
    )

    questions: List[str] = flow["questions"]
    text = format_step(
        title=f"SRVT • {SERVICES.get(service_key, service_key)}",
        step=1,
        total=len(questions),
        intro=flow["description"],
        question=questions[0],
    )
    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=text,
        reply_markup=back_to_menu_keyboard(),
    )
    await callback.answer()


@router.message(ServiceQuestionnaire.waiting_for_answer)
async def handle_questionnaire_answer(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    user_id = message.from_user.id
    user_answer = (message.text or "").strip()
    if not user_answer:
        return

    data = await state.get_data()
    service_key = data.get("selected_service")
    if not isinstance(service_key, str) or service_key not in SERVICE_FLOWS:
        await message.answer(msg("unknown_service"))
        await state.clear()
        return

    flow = SERVICE_FLOWS[service_key]
    questions: List[str] = flow["questions"]
    index = int(data.get("questionnaire_index", 0))
    answers: List[Dict[str, Any]] = list(data.get("questionnaire_answers", []))

    question_text = questions[index]
    answers.append({"question": question_text, "answer": user_answer})

    # Persist message history
    await UserMemory.add_message(
        session, user_id, "user", f"{question_text}\nОтвет: {user_answer}"
    )
    await DialogMessage.create(
        session,
        user_id=user_id,
        username=message.from_user.username,
        full_name=None,
        phone=None,
        message_text=user_answer,
        role="user",
        chat_id=message.chat.id,
        message_id=message.message_id,
    )

    index += 1

    if index >= len(questions):
        # Build summary for Bitrix/comments
        summary_lines = [f"Анкета: {flow['direction_label']}"]
        for item in answers:
            summary_lines.append(f"{item['question']}\nОтвет: {item['answer']}")
        summary_text = "\n\n".join(summary_lines)

        # Persist summary to user memory for future lead generation
        await UserMemory.add_message(session, user_id, "system", summary_text)

        await state.update_data(
            questionnaire_index=index,
            questionnaire_answers=answers,
            questionnaire_summary=summary_text,
        )
        await log_event(
            session,
            user_id=user_id,
            chat_id=message.chat.id,
            username=message.from_user.username,
            event="questionnaire_complete",
            service_key=service_key,
        )
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=flow["final_text"],
            reply_markup=lead_actions_keyboard(service_key),
            parse_mode=None,
        )
        return

    await state.update_data(questionnaire_index=index, questionnaire_answers=answers)
    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=format_step(
            title=f"SRVT • {SERVICES.get(service_key, service_key)}",
            step=index + 1,
            total=len(questions),
            question=questions[index],
        ),
        reply_markup=back_to_menu_keyboard(),
    )



from __future__ import annotations

from typing import Any, Dict, List

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dialog_message import DialogMessage
from src.models.user_memory import UserMemory
from src.utils.keyboards import back_to_menu_keyboard, lead_actions_keyboard
from src.utils.messages import msg

from src.config import SERVICE_FLOWS, SERVICES

router = Router()


class ServiceQuestionnaire(StatesGroup):
    waiting_for_answer = State()


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

    await state.set_state(ServiceQuestionnaire.waiting_for_answer)
    await state.update_data(
        selected_service=service_key,
        questionnaire_index=0,
        questionnaire_answers=[],
    )

    text = f"{flow['description']}\n\n{flow['questions'][0]}"
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard())
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

        # Persist summary to user memory for future RAG / lead generation
        await UserMemory.add_message(session, user_id, "system", summary_text)

        await state.update_data(
            questionnaire_index=index,
            questionnaire_answers=answers,
            questionnaire_summary=summary_text,
        )
        await message.answer(flow["final_text"], reply_markup=lead_actions_keyboard(service_key))
        return

    await state.update_data(questionnaire_index=index, questionnaire_answers=answers)
    await message.answer(questions[index], reply_markup=back_to_menu_keyboard())



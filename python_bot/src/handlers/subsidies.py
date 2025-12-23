from __future__ import annotations

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
    parse_spend_from_question,
)
from src.utils.keyboards import lead_actions_keyboard
from src.vector_store import VectorStore

router = Router()


class SubsidyChat(StatesGroup):
    waiting_for_question = State()


@router.callback_query(F.data.startswith("subsidy:chat:start:"))
async def start_subsidy_chat(callback: CallbackQuery, state: FSMContext) -> None:
    service_key = (callback.data or "").split("subsidy:chat:start:", 1)[-1].strip()
    await state.set_state(SubsidyChat.waiting_for_question)
    await state.update_data(service_key=service_key)
    await callback.message.answer(
        "Ок. Напишите вопрос по субсидиям/мерам поддержки — я подберу релевантные фрагменты из базы знаний и отвечу."
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
        answer = f"{answer}\n\n(Примечание: релевантный контекст в базе знаний не найден — ответ общий.)"

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

    await message.answer(answer, reply_markup=lead_actions_keyboard(service_key))

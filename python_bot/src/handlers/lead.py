from __future__ import annotations

import re
from typing import Optional, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bitrix import BitrixClient
from src.models.bitrix_lead import BitrixLead
from src.models.dialog_message import DialogMessage
from src.models.user_memory import UserMemory
from src.utils.keyboards import services_keyboard
from src.utils.messages import msg
from src.utils.rate_limit import FixedWindowRateLimiter


router = Router()

_lead_rate_limiter = FixedWindowRateLimiter(limit=3, window_sec=60)  # 3 leads/min per user


class LeadForm(StatesGroup):
    waiting_for_contact_data = State()
    waiting_for_meeting_window = State()


@router.callback_query(F.data.startswith("lead:start:"))
async def lead_start(callback: CallbackQuery, state: FSMContext) -> None:
    service_key = (callback.data or "").split("lead:start:", 1)[-1].strip()
    await state.set_state(LeadForm.waiting_for_contact_data)
    await state.update_data(service_key=service_key)
    await callback.message.answer(msg("lead_contact_request"))
    await callback.answer()


@router.message(LeadForm.waiting_for_contact_data)
async def lead_process_contact(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await message.answer(msg("unknown_service"), reply_markup=services_keyboard())
        await state.clear()
        return

    full_name, phone = parse_contact_data(text)
    if not phone:
        await message.answer("Не вижу телефон. Пришлите, пожалуйста, в формате: Иванов Иван +79991234567")
        return

    user_id = message.from_user.id
    if not _lead_rate_limiter.allow(str(user_id)):
        await message.answer("Слишком много заявок за минуту. Пожалуйста, попробуйте чуть позже.")
        return
    username = message.from_user.username

    # Pull questionnaire summary if exists
    questionnaire_summary = data.get("questionnaire_summary")
    summary_text = questionnaire_summary if isinstance(questionnaire_summary, str) else ""

    # Persist contact
    await UserMemory.update_user_data(session, user_id, full_name=full_name, phone=phone)

    await DialogMessage.create(
        session,
        user_id=user_id,
        username=username,
        full_name=full_name,
        phone=phone,
        message_text=text,
        role="user",
        chat_id=message.chat.id,
        message_id=message.message_id,
    )

    # Ask preferred meeting window as next step
    await state.update_data(full_name=full_name, phone=phone, username=username, questionnaire_summary=summary_text)
    await state.set_state(LeadForm.waiting_for_meeting_window)
    await message.answer(msg("lead_meeting_window_request"))


@router.message(LeadForm.waiting_for_meeting_window)
async def lead_process_meeting_window(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await message.answer(msg("unknown_service"), reply_markup=services_keyboard())
        await state.clear()
        return

    user_id = message.from_user.id
    full_name = data.get("full_name") if isinstance(data.get("full_name"), str) else None
    phone = data.get("phone") if isinstance(data.get("phone"), str) else None
    username = data.get("username") if isinstance(data.get("username"), str) else message.from_user.username

    summary_text = data.get("questionnaire_summary") if isinstance(data.get("questionnaire_summary"), str) else ""
    meeting_window = text[:300]
    if meeting_window.lower().strip() in {"не важно", "неважно", "any", "нет"}:
        meeting_window = "Не важно"

    comment_parts = []
    if summary_text.strip():
        comment_parts.append(summary_text.strip())
    comment_parts.append(f"Окно для встречи/созвона (МСК): {meeting_window}")
    comment = "\n\n".join(comment_parts)

    bitrix = BitrixClient()
    result = await bitrix.create_lead(
        full_name=full_name or f"Telegram {user_id}",
        phone=phone or "",
        service_key=service_key,
        comment=comment,
        user_id=user_id,
        username=username,
    )

    if result.get("success"):
        lead_id = int(result["lead_id"])
        await BitrixLead.create(
            session,
            lead_id=lead_id,
            user_id=user_id,
            full_name=full_name,
            phone=phone,
            service=service_key,
        )

    await message.answer(msg("lead_received"), reply_markup=services_keyboard())
    await state.clear()


PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{7,}\d)")


def parse_contact_data(text: str) -> Tuple[str, Optional[str]]:
    phone_match = PHONE_RE.search(text)
    if not phone_match:
        return text.strip()[:200], None
    phone_raw = phone_match.group(1)
    phone = re.sub(r"[^\d+]", "", phone_raw)
    name = (text.replace(phone_raw, "")).strip()
    if not name:
        name = "Не указано"
    return name[:200], phone[:32]



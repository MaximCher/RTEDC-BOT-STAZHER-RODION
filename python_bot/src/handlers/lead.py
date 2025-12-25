from __future__ import annotations

import re
from typing import Optional, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bitrix import BitrixClient
from src.models.bitrix_lead import BitrixLead
from src.models.dialog_message import DialogMessage
from src.models.lead_ticket import LeadTicket
from src.models.staff import StaffMember
from src.models.user_memory import UserMemory
from src.config import SERVICES
from src.utils.keyboards import (
    flow_nav_keyboard,
    meeting_window_keyboard,
    services_keyboard,
    staff_ticket_keyboard,
)
from src.utils.messages import msg
from src.utils.rate_limit import FixedWindowRateLimiter
from src.utils.funnel import log_event
from src.utils.ui_flow import format_step, ui_upsert, ui_send_persistent
from src.utils.service_entry import entry_screen_for_service


router = Router()

_lead_rate_limiter = FixedWindowRateLimiter(limit=3, window_sec=60)  # 3 leads/min per user


class LeadForm(StatesGroup):
    waiting_for_contact_data = State()
    waiting_for_meeting_window = State()


@router.callback_query(F.data == "lead:back")
async def lead_back(callback: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    if current == LeadForm.waiting_for_contact_data.state:
        data = await state.get_data()
        service_key = data.get("service_key") if isinstance(data.get("service_key"), str) else ""
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

    if current != LeadForm.waiting_for_meeting_window.state:
        await callback.answer()
        return

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await state.clear()
        try:
            await callback.message.edit_text(msg("choose_service"), reply_markup=services_keyboard())
        except Exception:
            await callback.message.answer(msg("choose_service"), reply_markup=services_keyboard())
        await callback.answer()
        return

    # Go back to contact step (allow user to fix name/phone)
    await state.set_state(LeadForm.waiting_for_contact_data)
    await state.update_data(full_name=None, phone=None, username=None)

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(title="SRVT • Заявка", step=1, total=2, question=msg("lead_contact_request")),
        reply_markup=flow_nav_keyboard("lead:back"),
        keep_at_bottom=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lead:start:"))
async def lead_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    service_key = (callback.data or "").split("lead:start:", 1)[-1].strip()
    await state.set_state(LeadForm.waiting_for_contact_data)
    await state.update_data(service_key=service_key)
    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="cta_lead_start",
        service_key=service_key,
    )
    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Заявка",
            step=1,
            total=2,
            question=msg("lead_contact_request"),
        ),
        reply_markup=flow_nav_keyboard("lead:back"),
        keep_at_bottom=True,
    )
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
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Заявка",
                step=1,
                total=2,
                intro="Ошибка: не вижу телефон. Пример: Иванов Иван +79991234567",
                question=msg("lead_contact_request"),
            ),
            reply_markup=flow_nav_keyboard("lead:back"),
            keep_at_bottom=True,
        )
        return

    user_id = message.from_user.id
    if not _lead_rate_limiter.allow(str(user_id)):
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text="Слишком много заявок за минуту. Пожалуйста, попробуйте чуть позже.",
            reply_markup=services_keyboard(),
            parse_mode=None,
            keep_at_bottom=True,
        )
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
    await log_event(
        session,
        user_id=user_id,
        chat_id=message.chat.id,
        username=username,
        event="contact_submitted",
        service_key=service_key,
    )
    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=format_step(
            title="SRVT • Заявка",
            step=2,
            total=2,
            question=msg("lead_meeting_window_request"),
        ),
        reply_markup=meeting_window_keyboard(include_back=True),
        keep_at_bottom=True,
    )


def _meeting_window_from_code(code: str) -> str:
    mapping = {
        "today_am": "Сегодня 10:00–13:00",
        "today_pm": "Сегодня 14:00–18:00",
        "tomorrow_am": "Завтра 10:00–13:00",
        "tomorrow_pm": "Завтра 14:00–18:00",
        "weekdays_19": "Будни после 19:00",
        "any": "Не важно",
    }
    return mapping.get(code, "Не важно")


async def _submit_lead(
    *,
    session: AsyncSession,
    bot,
    user_id: int,
    chat_id: int,
    service_key: str,
    full_name: str | None,
    phone: str | None,
    username: str | None,
    summary_text: str,
    meeting_window: str,
) -> None:
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
        await log_event(
            session,
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            event="lead_created",
            service_key=service_key,
            meta={"lead_id": lead_id},
        )

        # Create ticket for staff work
        ticket = LeadTicket(
            lead_user_id=user_id,
            lead_chat_id=chat_id,
            bitrix_lead_id=lead_id,
            service_key=service_key,
            lead_full_name=full_name,
            lead_phone=phone,
            lead_username=username,
            meeting_window=meeting_window,
            summary_text=summary_text,
            status="new",
            assigned_to_tg_user_id=None,
            chat_enabled=0,
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)

        # Notify staff (admins + managers)
        try:
            res = await session.execute(
                select(StaffMember).where(StaffMember.role.in_(["admin", "manager"]))
            )
            staff = list(res.scalars().all())
        except Exception:
            staff = []
        if staff:
            service_label = SERVICES.get(service_key, service_key)
            lead_label = full_name or f"Telegram {user_id}"
            phone_line = f"Телефон: {phone}" if phone else "Телефон: —"
            mw_line = f"Окно (МСК): {meeting_window}" if meeting_window else "Окно (МСК): —"
            staff_text = (
                "Новый лид SRVT\n"
                f"Услуга: {service_label}\n"
                f"Лид: {lead_label}\n"
                f"{phone_line}\n"
                f"{mw_line}\n"
                f"Bitrix lead_id: {lead_id}\n"
                f"Тикет: #{ticket.id}"
            )
            for m in staff:
                try:
                    await bot.send_message(
                        chat_id=int(m.tg_user_id),
                        text=staff_text,
                        reply_markup=staff_ticket_keyboard(ticket.id),
                    )
                except Exception:
                    continue


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
    await log_event(
        session,
        user_id=user_id,
        chat_id=message.chat.id,
        username=username,
        event="meeting_window_submitted",
        service_key=service_key,
        meta={"value": meeting_window},
    )
    await _submit_lead(
        session=session,
        bot=message.bot,
        user_id=user_id,
        chat_id=message.chat.id,
        service_key=service_key,
        full_name=full_name,
        phone=phone,
        username=username,
        summary_text=summary_text,
        meeting_window=meeting_window,
    )
    await ui_send_persistent(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=msg("lead_received"),
        reply_markup=services_keyboard(),
        parse_mode=None,
        delete_transient=False,
    )
    await state.clear()


@router.callback_query(F.data.startswith("lead:mw:"))
async def lead_meeting_window_pick(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    # Works only when user is in lead meeting window step
    current_state = await state.get_state()
    if current_state != LeadForm.waiting_for_meeting_window.state:
        await callback.answer("Окно созвона можно выбрать после отправки контакта.", show_alert=True)
        return

    code = (callback.data or "").split("lead:mw:", 1)[-1].strip()
    meeting_window = _meeting_window_from_code(code)

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await callback.message.answer(msg("unknown_service"), reply_markup=services_keyboard())
        await state.clear()
        await callback.answer()
        return

    user_id = callback.from_user.id
    full_name = data.get("full_name") if isinstance(data.get("full_name"), str) else None
    phone = data.get("phone") if isinstance(data.get("phone"), str) else None
    username = data.get("username") if isinstance(data.get("username"), str) else callback.from_user.username
    summary_text = data.get("questionnaire_summary") if isinstance(data.get("questionnaire_summary"), str) else ""

    await log_event(
        session,
        user_id=user_id,
        chat_id=callback.message.chat.id,
        username=username,
        event="meeting_window_selected",
        service_key=service_key,
        meta={"value": meeting_window},
    )

    await _submit_lead(
        session=session,
        bot=callback.message.bot,
        user_id=user_id,
        chat_id=callback.message.chat.id,
        service_key=service_key,
        full_name=full_name,
        phone=phone,
        username=username,
        summary_text=summary_text,
        meeting_window=meeting_window,
    )

    await ui_send_persistent(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        text=msg("lead_received"),
        reply_markup=services_keyboard(),
        parse_mode=None,
        delete_transient=False,
    )
    await state.clear()
    await callback.answer()


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



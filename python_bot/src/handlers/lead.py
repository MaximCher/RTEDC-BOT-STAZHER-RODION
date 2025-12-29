from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.bitrix import BitrixClient
from src.config import SERVICES
from src.models.bitrix_lead import BitrixLead
from src.models.dialog_message import DialogMessage
from src.models.lead_ticket import LeadTicket
from src.models.staff import StaffMember
from src.models.user_memory import UserMemory
from src.utils.funnel import log_event
from src.utils.keyboards import (
    flow_nav_keyboard,
    meeting_window_keyboard,
    services_keyboard,
    staff_ticket_keyboard,
)
from src.utils.messages import msg
from src.utils.rate_limit import FixedWindowRateLimiter
from src.utils.service_entry import entry_screen_for_service
from src.utils.ui_flow import format_step, ui_send_persistent, ui_upsert

router = Router()

_lead_rate_limiter = FixedWindowRateLimiter(
    limit=3, window_sec=60
)  # 3 leads/min per user

_INN_RE = re.compile(r"(?<!\d)(\d{10}|\d{12})(?!\d)")


class LeadForm(StatesGroup):
    waiting_for_inn = State()
    waiting_for_contact_data = State()
    waiting_for_meeting_window = State()


@router.callback_query(F.data == "lead:back")
async def lead_back(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    # UX: acknowledge click immediately to stop Telegram "loading" spinner
    try:
        await callback.answer()
    except Exception:
        pass
    current = await state.get_state()
    if current in {
        LeadForm.waiting_for_inn.state,
        LeadForm.waiting_for_contact_data.state,
    }:
        data = await state.get_data()
        service_key = (
            data.get("service_key")
            if isinstance(data.get("service_key"), str)
            else ""
        )
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
        return

    if current != LeadForm.waiting_for_meeting_window.state:
        return

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await state.clear()
        try:
            await callback.message.edit_text(
                msg("welcome"), reply_markup=services_keyboard()
            )
        except Exception:
            await callback.message.answer(
                msg("welcome"), reply_markup=services_keyboard()
            )
        return

    # Go back to contact step (allow user to fix name/phone)
    await state.set_state(LeadForm.waiting_for_contact_data)
    await state.update_data(full_name=None, phone=None, username=None)

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Заявка на консультацию",
            step=2,
            total=3,
            question=msg("lead_contact_request"),
        ),
        reply_markup=flow_nav_keyboard("lead:back"),
        keep_at_bottom=True,
        persist=True,
        session=session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )


@router.callback_query(F.data.startswith("lead:start:"))
async def lead_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    # UX: acknowledge click immediately to stop Telegram "loading" spinner
    try:
        await callback.answer()
    except Exception:
        pass
    service_key = (callback.data or "").split("lead:start:", 1)[-1].strip()
    await state.set_state(LeadForm.waiting_for_inn)
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
            title="SRVT • Заявка на консультацию",
            step=1,
            total=3,
            question=msg("lead_inn_request"),
        ),
        reply_markup=flow_nav_keyboard("lead:back"),
        keep_at_bottom=True,
        persist=True,
        session=session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )


@router.message(LeadForm.waiting_for_inn)
async def lead_process_inn(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await message.answer(
            msg("unknown_service"), reply_markup=services_keyboard()
        )
        await state.clear()
        return

    m = _INN_RE.search(text)
    if not m:
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Заявка на консультацию",
                step=1,
                total=3,
                intro="Ошибка: не вижу ИНН. Пришлите 10 или 12 цифр (без пробелов).",
                question=msg("lead_inn_request"),
            ),
            reply_markup=flow_nav_keyboard("lead:back"),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=message.from_user.id,
            username=message.from_user.username,
        )
        return

    inn = m.group(1)
    user_id = message.from_user.id
    await UserMemory.update_user_data(session, user_id, inn=inn)
    await log_event(
        session,
        user_id=user_id,
        chat_id=message.chat.id,
        username=message.from_user.username,
        event="inn_submitted",
        service_key=service_key,
        meta={"inn": inn},
    )
    await state.update_data(inn=inn)
    await state.set_state(LeadForm.waiting_for_contact_data)
    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=format_step(
            title="SRVT • Заявка на консультацию",
            step=2,
            total=3,
            question=msg("lead_contact_request"),
        ),
        reply_markup=flow_nav_keyboard("lead:back"),
        keep_at_bottom=True,
        persist=True,
        session=session,
        user_id=message.from_user.id,
        username=message.from_user.username,
    )


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
        await message.answer(
            msg("unknown_service"), reply_markup=services_keyboard()
        )
        await state.clear()
        return

    full_name, phone = parse_contact_data(text)
    if not phone:
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Заявка на консультацию",
                step=2,
                total=3,
                intro="Ошибка: не вижу телефон. Пример: Иванов Иван +79991234567",
                question=msg("lead_contact_request"),
            ),
            reply_markup=flow_nav_keyboard("lead:back"),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=message.from_user.id,
            username=message.from_user.username,
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
            persist=True,
            session=session,
            user_id=message.from_user.id,
            username=message.from_user.username,
        )
        return
    username = message.from_user.username

    # Pull questionnaire summary if exists
    questionnaire_summary = data.get("questionnaire_summary")
    summary_text = (
        questionnaire_summary if isinstance(questionnaire_summary, str) else ""
    )
    inn = data.get("inn") if isinstance(data.get("inn"), str) else None

    # Persist contact
    await UserMemory.update_user_data(
        session, user_id, full_name=full_name, phone=phone, inn=inn
    )

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
    await state.update_data(
        full_name=full_name,
        phone=phone,
        username=username,
        questionnaire_summary=summary_text,
    )
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
            title="SRVT • Заявка на консультацию",
            step=3,
            total=3,
            question=msg("lead_meeting_window_request"),
        ),
        reply_markup=meeting_window_keyboard(include_back=True),
        keep_at_bottom=True,
        persist=True,
        session=session,
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=full_name,
        phone=phone,
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
    inn: str | None,
    summary_text: str,
    meeting_window: str,
) -> bool:
    # Dedupe: prevent duplicate Bitrix leads and staff spam on repeated submissions.
    # Key is stable for the same lead payload.
    norm = "|".join(
        [
            str(user_id),
            (service_key or "").strip(),
            (phone or "").strip(),
            (inn or "").strip(),
            (meeting_window or "").strip(),
            (summary_text or "").strip(),
        ]
    )
    dedupe_key = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:64]
    try:
        cutoff = datetime.utcnow() - timedelta(hours=12)
        existing = (
            await session.execute(
                select(LeadTicket).where(
                    LeadTicket.dedupe_key == dedupe_key,
                    LeadTicket.created_at >= cutoff,
                )
            )
        ).scalar_one_or_none()
    except Exception:
        existing = None
    if existing:
        await log_event(
            session,
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            event="lead_deduped",
            service_key=service_key,
            meta={"ticket_id": int(existing.id)},
        )
        return False

    comment_parts = []
    if inn:
        comment_parts.append(f"ИНН: {inn}")
    if summary_text.strip():
        comment_parts.append(summary_text.strip())
    comment_parts.append(f"Время для встречи/созвона (МСК): {meeting_window}")
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

    bitrix_lead_id: Optional[int] = None
    if result.get("success") and result.get("lead_id"):
        bitrix_lead_id = int(result["lead_id"])
        try:
            await BitrixLead.create(
                session,
                lead_id=bitrix_lead_id,
                user_id=user_id,
                full_name=full_name,
                phone=phone,
                service=service_key,
            )
        except Exception:
            pass
        await log_event(
            session,
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            event="lead_created",
            service_key=service_key,
            meta={"lead_id": bitrix_lead_id},
        )
    else:
        # Important: Bitrix may be unconfigured during staging — still create internal ticket.
        await log_event(
            session,
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            event="lead_created_bitrix_skipped",
            service_key=service_key,
            meta={
                "error": (
                    result.get("error")
                    if isinstance(result, dict)
                    else "unknown"
                )
            },
        )

    # Always create ticket for staff work (Bitrix is optional)
    ticket = LeadTicket(
        lead_user_id=user_id,
        lead_chat_id=chat_id,
        bitrix_lead_id=bitrix_lead_id,
        service_key=service_key,
        lead_full_name=full_name,
        lead_phone=phone,
        lead_username=username,
        lead_inn=inn,
        meeting_window=meeting_window,
        summary_text=summary_text,
        dedupe_key=dedupe_key,
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
            select(StaffMember).where(
                StaffMember.role.in_(["admin", "manager"])
            )
        )
        staff = list(res.scalars().all())
    except Exception:
        staff = []
    if staff:
        service_label = SERVICES.get(service_key, service_key)
        lead_label = full_name or f"Telegram {user_id}"
        inn_line = f"ИНН: {inn}" if inn else "ИНН: —"
        phone_line = f"Телефон: {phone}" if phone else "Телефон: —"
        mw_line = (
            f"Время (МСК): {meeting_window}"
            if meeting_window
            else "Время (МСК): —"
        )
        if username:
            tg_line = f"Telegram: @{username} (https://t.me/{username})"
        else:
            tg_line = f"Telegram: tg://user?id={user_id}"
        bitrix_line = (
            f"Bitrix lead_id: {bitrix_lead_id}"
            if bitrix_lead_id
            else "Bitrix lead_id: —"
        )
        staff_text = (
            "Новый лид SRVT\n"
            f"Услуга: {service_label}\n"
            f"Лид: {lead_label}\n"
            f"{tg_line}\n"
            f"{inn_line}\n"
            f"{phone_line}\n"
            f"{mw_line}\n"
            f"{bitrix_line}\n"
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
    return True


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
        await message.answer(
            msg("unknown_service"), reply_markup=services_keyboard()
        )
        await state.clear()
        return

    user_id = message.from_user.id
    full_name = (
        data.get("full_name")
        if isinstance(data.get("full_name"), str)
        else None
    )
    phone = data.get("phone") if isinstance(data.get("phone"), str) else None
    username = (
        data.get("username")
        if isinstance(data.get("username"), str)
        else message.from_user.username
    )
    inn = data.get("inn") if isinstance(data.get("inn"), str) else None

    summary_text = (
        data.get("questionnaire_summary")
        if isinstance(data.get("questionnaire_summary"), str)
        else ""
    )
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
    created = await _submit_lead(
        session=session,
        bot=message.bot,
        user_id=user_id,
        chat_id=message.chat.id,
        service_key=service_key,
        full_name=full_name,
        phone=phone,
        username=username,
        inn=inn,
        summary_text=summary_text,
        meeting_window=meeting_window,
    )
    await ui_send_persistent(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=msg("lead_received") if created else "Заявка уже принята ✅\n\nМенеджер свяжется с вами в рабочее время.",
        reply_markup=services_keyboard(),
        parse_mode=None,
        delete_transient=False,
        persist=True,
        session=session,
        user_id=user_id,
        username=username,
        full_name=full_name,
        phone=phone,
    )
    await state.clear()


@router.callback_query(F.data.startswith("lead:mw:"))
async def lead_meeting_window_pick(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    # Works only when user is in lead meeting window step
    current_state = await state.get_state()
    if current_state != LeadForm.waiting_for_meeting_window.state:
        await callback.answer(
            "Время для созвона можно выбрать после отправки контакта.",
            show_alert=True,
        )
        return

    code = (callback.data or "").split("lead:mw:", 1)[-1].strip()
    meeting_window = _meeting_window_from_code(code)

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await callback.message.answer(
            msg("unknown_service"), reply_markup=services_keyboard()
        )
        await state.clear()
        await callback.answer()
        return

    user_id = callback.from_user.id
    full_name = (
        data.get("full_name")
        if isinstance(data.get("full_name"), str)
        else None
    )
    phone = data.get("phone") if isinstance(data.get("phone"), str) else None
    username = (
        data.get("username")
        if isinstance(data.get("username"), str)
        else callback.from_user.username
    )
    inn = data.get("inn") if isinstance(data.get("inn"), str) else None
    summary_text = (
        data.get("questionnaire_summary")
        if isinstance(data.get("questionnaire_summary"), str)
        else ""
    )

    await log_event(
        session,
        user_id=user_id,
        chat_id=callback.message.chat.id,
        username=username,
        event="meeting_window_selected",
        service_key=service_key,
        meta={"value": meeting_window},
    )

    created = await _submit_lead(
        session=session,
        bot=callback.message.bot,
        user_id=user_id,
        chat_id=callback.message.chat.id,
        service_key=service_key,
        full_name=full_name,
        phone=phone,
        username=username,
        inn=inn,
        summary_text=summary_text,
        meeting_window=meeting_window,
    )

    await ui_send_persistent(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        text=msg("lead_received") if created else "Заявка уже принята ✅\n\nМенеджер свяжется с вами в рабочее время.",
        reply_markup=services_keyboard(),
        parse_mode=None,
        delete_transient=False,
        persist=True,
        session=session,
        user_id=user_id,
        username=username,
        full_name=full_name,
        phone=phone,
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

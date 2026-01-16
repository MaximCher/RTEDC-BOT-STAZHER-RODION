from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bitrix import BitrixClient
from src.config import SERVICES
from src.models.bitrix_lead import BitrixLead
from src.models.lead_ticket import LeadTicket
from src.models.staff import StaffMember
from src.utils.funnel import log_event
from src.utils.keyboards import staff_ticket_keyboard


async def submit_consultation(
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
                    result.get("error") if isinstance(result, dict) else "unknown"
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
            select(StaffMember).where(StaffMember.role.in_(["admin", "manager"]))
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
            f"Время (МСК): {meeting_window}" if meeting_window else "Время (МСК): —"
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


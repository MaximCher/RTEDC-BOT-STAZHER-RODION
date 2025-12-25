from __future__ import annotations

from datetime import date, datetime, timedelta
import csv
import io
import json
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.models.bitrix_lead import BitrixLead
from src.models.dialog_message import DialogMessage
from src.models.user_memory import UserMemory
from src.models.staff import StaffMember
from src.web.auth import (
    SESSION_KEY,
    require_auth,
    validate_password,
)


class LoginRequest(BaseModel):
    password: str


class StaffUpsertRequest(BaseModel):
    tg_user_id: int
    role: str  # admin | manager


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _range_bounds(
    start_raw: Optional[str], end_raw: Optional[str]
) -> tuple[Optional[datetime], Optional[datetime]]:
    start_date = _parse_date(start_raw)
    end_date = _parse_date(end_raw)
    start_dt = datetime.combine(start_date, datetime.min.time()) if start_date else None
    end_dt = (
        datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        if end_date
        else None
    )
    return start_dt, end_dt


async def _get_session() -> AsyncSession:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


def register_api(app: FastAPI) -> None:
    @app.post("/api/login")
    async def login(request: Request, payload: LoginRequest) -> JSONResponse:
        validate_password(payload.password)
        request.session[SESSION_KEY] = True
        return JSONResponse({"success": True})

    @app.post("/api/logout")
    async def logout(request: Request) -> JSONResponse:
        request.session.clear()
        return JSONResponse({"success": True})

    @app.get("/api/users")
    async def get_users(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        start_dt, end_dt = _range_bounds(start_date, end_date)
        q = select(
            DialogMessage.user_id.label("user_id"),
            func.max(DialogMessage.username).label("username"),
            func.max(DialogMessage.full_name).label("full_name"),
            func.max(DialogMessage.phone).label("phone"),
            func.count(DialogMessage.id).label("message_count"),
            func.max(DialogMessage.created_at).label("last_message_at"),
        ).group_by(DialogMessage.user_id)

        if start_dt is not None:
            q = q.where(DialogMessage.created_at >= start_dt)
        if end_dt is not None:
            q = q.where(DialogMessage.created_at < end_dt)
        q = q.order_by(func.max(DialogMessage.created_at).desc())

        res = await session.execute(q)
        rows = res.mappings().all()
        users = [
            {
                "user_id": int(r["user_id"]),
                "username": r["username"],
                "full_name": r["full_name"],
                "phone": r["phone"],
                "message_count": int(r["message_count"] or 0),
                "last_message_at": r["last_message_at"].isoformat()
                if r["last_message_at"]
                else None,
            }
            for r in rows
        ]
        return {"users": users, "total": len(users)}

    @app.get("/api/conversation/{user_id}")
    async def get_conversation(
        user_id: int,
        request: Request,
        limit: int = 200,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        if limit <= 0 or limit > 1000:
            raise HTTPException(status_code=400, detail="Invalid limit")

        # Return last N messages, but in chronological order for UI rendering.
        q = (
            select(DialogMessage)
            .where(DialogMessage.user_id == user_id)
            .order_by(DialogMessage.created_at.desc())
            .limit(limit)
        )
        res = await session.execute(q)
        messages = res.scalars().all()
        messages.reverse()
        payload = [
            {
                "id": m.id,
                "user_id": int(m.user_id),
                "username": m.username,
                "full_name": m.full_name,
                "phone": m.phone,
                "message_text": m.message_text,
                "role": m.role,
                "chat_id": int(m.chat_id),
                "message_id": int(m.message_id) if m.message_id is not None else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]
        return {"messages": payload, "total": len(payload)}

    @app.get("/api/statistics")
    async def get_statistics(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        start_dt, end_dt = _range_bounds(start_date, end_date)

        dialogs_q = select(func.count(func.distinct(DialogMessage.user_id)))
        messages_q = select(func.count(DialogMessage.id))
        leads_q = select(func.count(BitrixLead.id))
        leads_by_service_q = select(BitrixLead.service, func.count(BitrixLead.id)).group_by(
            BitrixLead.service
        )
        # IMPORTANT: Use the same bind parameter instance for SELECT and GROUP BY.
        # Otherwise Postgres sees `$1` vs `$2` and throws GroupingError.
        unknown = literal("unknown")
        service_expr = func.coalesce(UserMemory.selected_service, unknown)
        users_by_service_q = (
            select(
                service_expr.label("service"),
                func.count(func.distinct(DialogMessage.user_id)).label("users"),
            )
            .select_from(DialogMessage)
            .join(UserMemory, UserMemory.user_id == DialogMessage.user_id, isouter=True)
            .group_by(service_expr)
        )

        if start_dt is not None:
            dialogs_q = dialogs_q.where(DialogMessage.created_at >= start_dt)
            messages_q = messages_q.where(DialogMessage.created_at >= start_dt)
            leads_q = leads_q.where(BitrixLead.created_at >= start_dt)
            leads_by_service_q = leads_by_service_q.where(BitrixLead.created_at >= start_dt)
            users_by_service_q = users_by_service_q.where(DialogMessage.created_at >= start_dt)
        if end_dt is not None:
            dialogs_q = dialogs_q.where(DialogMessage.created_at < end_dt)
            messages_q = messages_q.where(DialogMessage.created_at < end_dt)
            leads_q = leads_q.where(BitrixLead.created_at < end_dt)
            leads_by_service_q = leads_by_service_q.where(BitrixLead.created_at < end_dt)
            users_by_service_q = users_by_service_q.where(DialogMessage.created_at < end_dt)

        dialogs_total_res = await session.execute(dialogs_q)
        messages_total_res = await session.execute(messages_q)
        leads_total_res = await session.execute(leads_q)
        leads_by_service_res = await session.execute(leads_by_service_q)
        users_by_service_res = await session.execute(users_by_service_q)

        dialogs_total = int(dialogs_total_res.scalar() or 0)
        leads_total = int(leads_total_res.scalar() or 0)
        conversion = (float(leads_total) / float(dialogs_total)) if dialogs_total else 0.0

        leads_by_service = {
            str(service or "unknown"): int(cnt or 0) for service, cnt in leads_by_service_res.all()
        }
        users_by_service = {
            str(service or "unknown"): int(cnt or 0) for service, cnt in users_by_service_res.all()
        }

        return {
            "dialogs_total": dialogs_total,
            "messages_total": int(messages_total_res.scalar() or 0),
            "leads_total": leads_total,
            "conversion_rate": round(conversion, 4),
            "leads_by_service": leads_by_service,
            "users_by_service": users_by_service,
        }

    def _parse_event(message_text: str) -> Optional[Dict[str, Any]]:
        if not message_text or not message_text.startswith("event:"):
            return None
        raw = message_text.split("event:", 1)[-1].strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _pct(n: int, d: int) -> float:
        if d <= 0:
            return 0.0
        return round(float(n) / float(d), 4)

    @app.get("/api/funnel")
    async def get_funnel(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        """
        Funnel metrics based on role='event' rows in dialog_messages.
        Counts are UNIQUE USERS per step (user_id distinct).
        """
        start_dt, end_dt = _range_bounds(start_date, end_date)

        q = select(DialogMessage.user_id, DialogMessage.message_text).where(DialogMessage.role == "event")
        if start_dt is not None:
            q = q.where(DialogMessage.created_at >= start_dt)
        if end_dt is not None:
            q = q.where(DialogMessage.created_at < end_dt)

        res = await session.execute(q)
        rows = res.all()

        # Normalized steps for all services
        steps = [
            "entry_service",
            "engagement_start",
            "engagement_complete",
            "cta_lead_start",
            "contact_submitted",
            "meeting_window",
            "lead_created",
        ]

        # Map raw events to normalized steps
        engagement_start_events = {
            "subsidy_calc_start",
            "finance_calc_start",
            "payments_precheck_start",
            "logistics_quote_start",
            "analytics_report_start",
            "quick_audit_start",
            "club_apply_start",
            "questionnaire_start",
        }
        engagement_complete_events = {
            "subsidy_calc_complete",
            "finance_calc_complete",
            "payments_precheck_complete",
            "logistics_quote_complete",
            "analytics_report_complete",
            "quick_audit_complete",
            "club_apply_complete",
            "questionnaire_complete",
        }
        meeting_window_events = {"meeting_window_selected", "meeting_window_submitted"}

        # service -> step -> set(user_id)
        by_service: Dict[str, Dict[str, set[int]]] = {}
        overall: Dict[str, set[int]] = {s: set() for s in steps}

        for user_id, message_text in rows:
            ev = _parse_event(message_text)
            if not ev:
                continue
            name = str(ev.get("event") or "")
            service = str(ev.get("service") or "unknown")
            uid = int(user_id)

            step: Optional[str] = None
            if name == "entry_service":
                step = "entry_service"
            elif name in engagement_start_events:
                step = "engagement_start"
            elif name in engagement_complete_events:
                step = "engagement_complete"
            elif name == "cta_lead_start":
                step = "cta_lead_start"
            elif name == "contact_submitted":
                step = "contact_submitted"
            elif name in meeting_window_events:
                step = "meeting_window"
            elif name == "lead_created":
                step = "lead_created"

            if not step:
                continue

            svc_map = by_service.setdefault(service, {s: set() for s in steps})
            svc_map[step].add(uid)
            overall[step].add(uid)

        def pack(step_sets: Dict[str, set[int]]) -> Dict[str, Any]:
            counts = {s: len(step_sets[s]) for s in steps}
            # Sequential conversion (unique users)
            conv = {
                "entry_to_start": _pct(counts["engagement_start"], counts["entry_service"]),
                "start_to_complete": _pct(counts["engagement_complete"], counts["engagement_start"]),
                "complete_to_cta": _pct(counts["cta_lead_start"], counts["engagement_complete"]),
                "cta_to_contact": _pct(counts["contact_submitted"], counts["cta_lead_start"]),
                "contact_to_meeting": _pct(counts["meeting_window"], counts["contact_submitted"]),
                "meeting_to_lead": _pct(counts["lead_created"], counts["meeting_window"]),
                "entry_to_lead": _pct(counts["lead_created"], counts["entry_service"]),
            }
            drops = {
                "drop_entry": max(0, counts["entry_service"] - counts["engagement_start"]),
                "drop_start": max(0, counts["engagement_start"] - counts["engagement_complete"]),
                "drop_complete": max(0, counts["engagement_complete"] - counts["cta_lead_start"]),
                "drop_cta": max(0, counts["cta_lead_start"] - counts["contact_submitted"]),
                "drop_contact": max(0, counts["contact_submitted"] - counts["meeting_window"]),
                "drop_meeting": max(0, counts["meeting_window"] - counts["lead_created"]),
            }
            return {"counts": counts, "conversion": conv, "drops": drops}

        return {
            "steps": steps,
            "overall": pack(overall),
            "by_service": {svc: pack(step_sets) for svc, step_sets in by_service.items()},
        }

    @app.get("/api/export.csv")
    async def export_csv(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[int] = None,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Response:
        start_dt, end_dt = _range_bounds(start_date, end_date)
        # Select only required columns (cheaper than loading full ORM entities).
        q = (
            select(
                DialogMessage.created_at,
                DialogMessage.user_id,
                DialogMessage.role,
                DialogMessage.message_text,
                DialogMessage.chat_id,
                DialogMessage.message_id,
                DialogMessage.username,
                DialogMessage.full_name,
                DialogMessage.phone,
            )
            .order_by(DialogMessage.created_at.asc())
        )
        if user_id is not None:
            q = q.where(DialogMessage.user_id == user_id)
        if start_dt is not None:
            q = q.where(DialogMessage.created_at >= start_dt)
        if end_dt is not None:
            q = q.where(DialogMessage.created_at < end_dt)

        res = await session.execute(q)
        rows = res.all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "created_at",
                "user_id",
                "role",
                "message_text",
                "chat_id",
                "message_id",
                "username",
                "full_name",
                "phone",
            ]
        )
        for (
            created_at,
            r_user_id,
            role,
            message_text,
            chat_id,
            message_id,
            username,
            full_name,
            phone,
        ) in rows:
            writer.writerow(
                [
                    created_at.isoformat(),
                    int(r_user_id),
                    role,
                    message_text,
                    int(chat_id),
                    int(message_id) if message_id is not None else "",
                    username or "",
                    full_name or "",
                    phone or "",
                ]
            )

        filename = "dialogs.csv" if user_id is None else f"dialogs-{user_id}.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/staff")
    async def get_staff(
        request: Request,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        q = select(StaffMember).order_by(StaffMember.created_at.desc())
        res = await session.execute(q)
        rows = res.scalars().all()
        items = [
            {
                "tg_user_id": int(m.tg_user_id),
                "role": m.role,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ]
        return {"items": items, "total": len(items)}

    @app.post("/api/staff")
    async def add_staff_member(
        payload: StaffUpsertRequest,
        request: Request,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        role = payload.role.strip().lower()
        if role not in {"admin", "manager"}:
            raise HTTPException(status_code=400, detail="Invalid role")
        # Upsert by tg_user_id (tg_user_id is UNIQUE).
        existing = (
            await session.execute(select(StaffMember).where(StaffMember.tg_user_id == payload.tg_user_id))
        ).scalar_one_or_none()
        if existing:
            existing.role = role
        else:
            session.add(StaffMember(tg_user_id=payload.tg_user_id, role=role))
        await session.commit()
        return {"success": True}

    @app.delete("/api/staff/{tg_user_id}")
    async def remove_staff_member(
        tg_user_id: int,
        request: Request,
        role: Optional[str] = None,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        stmt = select(StaffMember).where(StaffMember.tg_user_id == tg_user_id)
        if role:
            stmt = stmt.where(StaffMember.role == role)
        res = await session.execute(stmt)
        rows = res.scalars().all()
        for r in rows:
            await session.delete(r)
        await session.commit()
        return {"deleted": len(rows)}



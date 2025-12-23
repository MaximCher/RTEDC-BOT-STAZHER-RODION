from __future__ import annotations

from datetime import date, datetime, timedelta
import csv
import io
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.models.bitrix_lead import BitrixLead
from src.models.dialog_message import DialogMessage
from src.models.staff import StaffMember
from src.web.auth import (
    SESSION_COOKIE,
    create_session,
    destroy_session,
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
    async def login(payload: LoginRequest) -> JSONResponse:
        validate_password(payload.password)
        session_id = create_session()
        response = JSONResponse({"success": True})
        response.set_cookie(
            key=SESSION_COOKIE,
            value=session_id,
            httponly=True,
            max_age=86400,
            samesite="lax",
        )
        return response

    @app.post("/api/logout")
    async def logout(request: Request) -> JSONResponse:
        session_id = request.cookies.get(SESSION_COOKIE)
        if session_id:
            destroy_session(session_id)
        response = JSONResponse({"success": True})
        response.delete_cookie(SESSION_COOKIE)
        return response

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

        if start_dt is not None:
            dialogs_q = dialogs_q.where(DialogMessage.created_at >= start_dt)
            messages_q = messages_q.where(DialogMessage.created_at >= start_dt)
            leads_q = leads_q.where(BitrixLead.created_at >= start_dt)
        if end_dt is not None:
            dialogs_q = dialogs_q.where(DialogMessage.created_at < end_dt)
            messages_q = messages_q.where(DialogMessage.created_at < end_dt)
            leads_q = leads_q.where(BitrixLead.created_at < end_dt)

        dialogs_total_res = await session.execute(dialogs_q)
        messages_total_res = await session.execute(messages_q)
        leads_total_res = await session.execute(leads_q)

        return {
            "dialogs_total": int(dialogs_total_res.scalar() or 0),
            "messages_total": int(messages_total_res.scalar() or 0),
            "leads_total": int(leads_total_res.scalar() or 0),
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



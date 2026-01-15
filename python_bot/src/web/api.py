from __future__ import annotations

from datetime import date, datetime, timedelta
import csv
import io
import json
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import func, literal, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_session_factory
from src.models.bitrix_lead import BitrixLead
from src.models.dialog_message import DialogMessage
from src.models.user_memory import UserMemory
from src.models.staff import StaffMember
from src.models.staff_invite import StaffInvite
from src.models.bot_heartbeat import BotHeartbeat
from src.models.required_subscription import RequiredSubscription
from src.models.app_setting import AppSetting
from src.models.broadcast_message import BroadcastMessage
from src.utils.webapp_url import get_webapp_public_url
from src.utils.telegram_links import parse_tme_url
from src.utils.dashboard_humanize import humanize_event
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


class StaffInviteCreateRequest(BaseModel):
    role: str  # admin | manager
    ttl_hours: int = 168  # 7 days


class RequiredSubscriptionCreateRequest(BaseModel):
    kind: str = "channel"  # channel|group|other
    chat_ref: str
    title: Optional[str] = None
    url: Optional[str] = None


class ToggleRequest(BaseModel):
    enabled: bool


class BroadcastCreateRequest(BaseModel):
    text: str
    # ISO string from <input type="datetime-local"> (no timezone)
    send_at: str


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
    async def _resolve_bot_username(session: AsyncSession) -> Optional[str]:
        # Prefer DB heartbeat (no extra network calls).
        try:
            hb = (
                await session.execute(
                    select(BotHeartbeat).order_by(BotHeartbeat.updated_at.desc()).limit(1)
                )
            ).scalar_one_or_none()
            if hb and hb.bot_username:
                return str(hb.bot_username).lstrip("@")
        except Exception:
            pass
        # Fallback to explicit env var
        if settings.telegram_bot_username:
            return settings.telegram_bot_username.lstrip("@")
        # Last resort: call Telegram API (bot token is already in env for bot)
        try:
            import httpx

            token = settings.telegram_bot_token
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                data = resp.json()
            if resp.status_code == 200 and data.get("ok") and data.get("result", {}).get("username"):
                return str(data["result"]["username"]).lstrip("@")
        except Exception:
            pass
        return None
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
        ).where(DialogMessage.role != "event").group_by(DialogMessage.user_id)

        if start_dt is not None:
            q = q.where(DialogMessage.created_at >= start_dt)
        if end_dt is not None:
            q = q.where(DialogMessage.created_at < end_dt)
        q = q.order_by(func.max(DialogMessage.created_at).desc())

        res = await session.execute(q)
        rows = res.mappings().all()
        users = []
        for r in rows:
            users.append(
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
            )
        if not users:
            where = []
            params: Dict[str, Any] = {}
            if start_dt is not None:
                where.append("u.last_active >= :start_dt")
                params["start_dt"] = start_dt
            if end_dt is not None:
                where.append("u.last_active < :end_dt")
                params["end_dt"] = end_dt
            where_sql = ("WHERE " + " AND ".join(where)) if where else ""
            fallback_res = await session.execute(
                text(
                    f"""
                    SELECT u.user_id, u.username, u.full_name, u.last_active
                    FROM users u
                    {where_sql}
                    ORDER BY u.last_active DESC NULLS LAST
                    LIMIT 5000
                    """
                ),
                params,
            )
            users = [
                {
                    "user_id": int(uid),
                    "username": username,
                    "full_name": full_name,
                    "phone": None,
                    "message_count": 0,
                    "last_message_at": last_active.isoformat()
                    if last_active
                    else None,
                }
                for (uid, username, full_name, last_active) in fallback_res.all()
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
            .where(DialogMessage.role != "event")
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

    @app.get("/api/webapp-url")
    async def get_webapp_url(
        request: Request,
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        return {"url": get_webapp_public_url(settings.webapp_public_url)}

    # ============================================================
    # Virality / access gate settings
    # ============================================================

    @app.get("/api/virality")
    async def get_virality(
        request: Request,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        items = await RequiredSubscription.list_all(session)
        ask_contact_raw = await AppSetting.get(session, "ask_contact_on_start")
        ask_contact = (ask_contact_raw or "").strip().lower() in {"1", "true", "yes", "on"}
        return {
            "items": [
                {
                    "id": int(i.id),
                    "kind": i.kind,
                    "chat_ref": i.chat_ref,
                    "title": i.title,
                    "url": i.url,
                }
                for i in items
            ],
            "ask_contact_on_start": ask_contact,
            "enabled": bool(items),
        }

    @app.post("/api/virality/subscriptions")
    async def add_required_subscription(
        payload: RequiredSubscriptionCreateRequest,
        request: Request,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        raw_chat_ref = (payload.chat_ref or "").strip()
        kind = (payload.kind or "channel").strip().lower()
        if kind not in {"channel", "group", "other"}:
            kind = "other"
        title = (payload.title or "").strip() or None
        url = (payload.url or "").strip() or None

        # Allow pasting https://t.me/... into chat_ref (or url) and normalize.
        # If it's a public @username link, we can verify via getChatMember.
        # If it's an invite link, we can only show the URL (verification is skipped on bot side).
        chat_ref = raw_chat_ref
        tme = parse_tme_url(raw_chat_ref) or (parse_tme_url(url or "") if url else None)
        if tme:
            if not url:
                url = tme.url
            if tme.username:
                chat_ref = f"@{tme.username}"
            else:
                # unverifiable; store the URL in chat_ref as well (bot will treat as "open-only")
                chat_ref = tme.url

        if not chat_ref:
            raise HTTPException(status_code=400, detail="chat_ref is required")

        # Deduplicate: same kind + same chat_ref
        try:
            existing = (
                await session.execute(
                    select(RequiredSubscription).where(
                        RequiredSubscription.kind == kind,
                        RequiredSubscription.chat_ref == chat_ref,
                    )
                )
            ).scalar_one_or_none()
        except Exception:
            existing = None
        if existing:
            return {"success": True, "id": int(existing.id), "deduped": True}

        item = RequiredSubscription(kind=kind, chat_ref=chat_ref, title=title, url=url)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return {"success": True, "id": int(item.id)}

    @app.delete("/api/virality/subscriptions/{item_id}")
    async def delete_required_subscription(
        item_id: int,
        request: Request,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        ok = await RequiredSubscription.delete_by_id(session, int(item_id))
        await session.commit()
        return {"success": bool(ok)}

    @app.post("/api/virality/ask-contact")
    async def set_ask_contact(
        payload: ToggleRequest,
        request: Request,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        await AppSetting.set(session, "ask_contact_on_start", "1" if payload.enabled else "0")
        await session.commit()
        return {"success": True, "enabled": bool(payload.enabled)}

    # ============================================================
    # Broadcasts (schedule)
    # ============================================================

    @app.get("/api/broadcast")
    async def list_broadcasts(
        request: Request,
        limit: int = 200,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        if limit <= 0 or limit > 1000:
            raise HTTPException(status_code=400, detail="Invalid limit")
        items = await BroadcastMessage.list_pending(session, limit=limit)
        return {
            "items": [
                {
                    "id": int(b.id),
                    "text": b.text,
                    "sent": int(b.sent or 0),
                    "created_at": b.created_at.isoformat() if b.created_at else None,
                    "send_at": b.send_at.isoformat() if b.send_at else None,
                }
                for b in items
            ],
            "total": len(items),
        }

    @app.post("/api/broadcast")
    async def create_broadcast(
        payload: BroadcastCreateRequest,
        request: Request,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        text_raw = (payload.text or "").strip()
        if not text_raw:
            raise HTTPException(status_code=400, detail="text is required")
        send_at_raw = (payload.send_at or "").strip()
        if not send_at_raw:
            raise HTTPException(status_code=400, detail="send_at is required")
        try:
            # datetime-local gives "YYYY-MM-DDTHH:MM"
            send_at_dt = datetime.fromisoformat(send_at_raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid send_at format")

        msg = BroadcastMessage(text=text_raw, sent=0, send_at=send_at_dt)
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return {"success": True, "id": int(msg.id)}

    @app.delete("/api/broadcast/{msg_id}")
    async def delete_broadcast(
        msg_id: int,
        request: Request,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        ok = await BroadcastMessage.delete_by_id(session, int(msg_id))
        await session.commit()
        return {"success": bool(ok)}

    # ============================================================
    # Legacy dashboard parity: events / user journey / actions
    # ============================================================

    @app.get("/api/events")
    async def list_events(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 200,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        if limit <= 0 or limit > 1000:
            raise HTTPException(status_code=400, detail="Invalid limit")
        start_dt, end_dt = _range_bounds(start_date, end_date)

        where = []
        params: Dict[str, Any] = {}
        if start_dt is not None:
            where.append("e.timestamp >= :start_dt")
            params["start_dt"] = start_dt
        if end_dt is not None:
            where.append("e.timestamp < :end_dt")
            params["end_dt"] = end_dt
        if user_id is not None:
            where.append("e.user_id = :user_id")
            params["user_id"] = int(user_id)
        if action:
            where.append("e.action = :action")
            params["action"] = str(action)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        params["limit"] = int(limit)

        res = await session.execute(
            text(
                f"""
                SELECT e.id, e.user_id, u.username, u.full_name, e.action, e.params, e.timestamp
                FROM events e
                LEFT JOIN users u ON e.user_id = u.user_id
                {where_sql}
                ORDER BY e.timestamp DESC
                LIMIT :limit
                """
            ),
            params,
        )
        items = []
        for (e_id, e_user_id, username, full_name, e_action, e_params, ts) in res.all():
            items.append(
                {
                    "id": int(e_id),
                    "user_id": int(e_user_id) if e_user_id is not None else 0,
                    "username": username,
                    "full_name": full_name,
                    "action": str(e_action or ""),
                    "params": e_params,
                    "timestamp": ts.isoformat() if ts else None,
                    "desc": humanize_event(str(e_action or ""), e_params),
                }
            )
        return {"items": items, "total": len(items)}

    @app.get("/api/user-journey/{user_id}")
    async def user_journey(
        user_id: int,
        request: Request,
        limit: int = 1000,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        if limit <= 0 or limit > 5000:
            raise HTTPException(status_code=400, detail="Invalid limit")

        ures = await session.execute(
            text(
                """
                SELECT user_id, username, full_name, first_seen, last_active
                FROM users WHERE user_id = :user_id
                """
            ),
            {"user_id": int(user_id)},
        )
        u = ures.first()
        user_payload = None
        if u:
            (uid, username, full_name, first_seen, last_active) = u
            user_payload = {
                "user_id": int(uid),
                "username": username,
                "full_name": full_name,
                "first_seen": first_seen.isoformat() if first_seen else None,
                "last_active": last_active.isoformat() if last_active else None,
            }

        eres = await session.execute(
            text(
                """
                SELECT id, action, params, timestamp
                FROM events
                WHERE user_id = :user_id
                ORDER BY timestamp ASC
                LIMIT :limit
                """
            ),
            {"user_id": int(user_id), "limit": int(limit)},
        )
        events = [
            {
                "id": int(eid),
                "action": str(act or ""),
                "params": params,
                "timestamp": ts.isoformat() if ts else None,
                "desc": humanize_event(str(act or ""), params),
            }
            for (eid, act, params, ts) in eres.all()
        ]
        return {"user": user_payload, "events": events, "total": len(events)}

    @app.get("/api/actions")
    async def actions(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        sample_limit: int = 5000,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        """
        Returns top actions and top humanized actions.

        We use a bounded sample window (sample_limit) for humanized grouping to keep it cheap.
        """
        if limit <= 0 or limit > 200:
            raise HTTPException(status_code=400, detail="Invalid limit")
        if sample_limit <= 0 or sample_limit > 50000:
            raise HTTPException(status_code=400, detail="Invalid sample_limit")
        start_dt, end_dt = _range_bounds(start_date, end_date)

        where = []
        params: Dict[str, Any] = {}
        if start_dt is not None:
            where.append("timestamp >= :start_dt")
            params["start_dt"] = start_dt
        if end_dt is not None:
            where.append("timestamp < :end_dt")
            params["end_dt"] = end_dt
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        # Top raw actions
        params_top = dict(params)
        params_top["limit"] = int(limit)
        raw_res = await session.execute(
            text(
                f"""
                SELECT action, COUNT(*) AS cnt
                FROM events
                {where_sql}
                GROUP BY action
                ORDER BY cnt DESC
                LIMIT :limit
                """
            ),
            params_top,
        )
        top_actions = [
            {
                "action": str(a or ""),
                "desc": humanize_event(str(a or ""), None),
                "count": int(c or 0),
            }
            for (a, c) in raw_res.all()
        ]

        # Humanized top actions from a sample window (most recent).
        params_sample = dict(params)
        params_sample["sample_limit"] = int(sample_limit)
        sample_res = await session.execute(
            text(
                f"""
                SELECT action, params
                FROM events
                {where_sql}
                ORDER BY timestamp DESC
                LIMIT :sample_limit
                """
            ),
            params_sample,
        )
        counts: Dict[str, int] = {}
        for (a, p) in sample_res.all():
            desc = humanize_event(str(a or ""), p)
            counts[desc] = counts.get(desc, 0) + 1
        top_human = [
            {"desc": k, "count": v}
            for (k, v) in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        ]

        return {"top_actions": top_actions, "top_human": top_human}

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
                "tg_username": m.tg_username,
                "tg_full_name": m.tg_full_name,
                "last_seen_at": m.last_seen_at.isoformat() if m.last_seen_at else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ]
        return {"items": items, "total": len(items)}

    @app.post("/api/staff/invites")
    async def create_staff_invite(
        payload: StaffInviteCreateRequest,
        request: Request,
        session: AsyncSession = Depends(_get_session),
        _: None = Depends(require_auth),
    ) -> Dict[str, Any]:
        role = (payload.role or "").strip().lower()
        if role not in {"admin", "manager"}:
            raise HTTPException(status_code=400, detail="Invalid role")
        ttl_hours = int(payload.ttl_hours or 0)
        if ttl_hours <= 0 or ttl_hours > 24 * 30:
            raise HTTPException(status_code=400, detail="Invalid ttl_hours")

        import secrets

        token = secrets.token_urlsafe(18)[:48]
        inv = StaffInvite(
            token=token,
            role=role,
            created_by_tg_user_id=0,
            expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
        )
        session.add(inv)
        await session.commit()
        await session.refresh(inv)

        bot_username = await _resolve_bot_username(session)
        if bot_username:
            url = f"https://t.me/{bot_username}?start=invite_{token}"
        else:
            # Extremely unlikely (bot heartbeat not written yet), but still return something.
            url = f"invite_{token}"
        return {
            "success": True,
            "token": token,
            "role": role,
            "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "url": url,
        }

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



from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dialog_message import DialogMessage


async def log_event(
    session: AsyncSession,
    *,
    user_id: int,
    chat_id: int,
    username: Optional[str],
    event: str,
    service_key: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Store funnel events in dialog_messages so admin stats can query them easily.
    (No new tables/migrations required.)
    """
    # Keep payload flat for dashboard compatibility
    # which expects keys like "label", "service", "step", etc. at top level.
    payload: Dict[str, Any] = {"event": event}
    if service_key:
        payload["service"] = service_key
    if meta:
        try:
            payload.update(dict(meta))
        except Exception:
            pass

    await DialogMessage.create(
        session,
        user_id=user_id,
        username=username,
        full_name=None,
        phone=None,
        message_text="event:" + json.dumps(payload, ensure_ascii=False),
        role="event",
        chat_id=chat_id,
        message_id=None,
    )

    # Also write into dashboard tables (users/events) for analytics compatibility.
    try:
        now = datetime.now(timezone.utc)
        await session.execute(
            text(
                """
                INSERT INTO users (user_id, username, full_name, first_seen, last_active)
                VALUES (:user_id, :username, :full_name, :now, :now)
                ON CONFLICT (user_id) DO UPDATE
                SET username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name,
                    last_active = EXCLUDED.last_active
                """
            ),
            {
                "user_id": int(user_id),
                "username": username,
                "full_name": None,
                "now": now,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO events (user_id, action, params, timestamp)
                VALUES (:user_id, :action, :params, :now)
                """
            ),
            {
                "user_id": int(user_id),
                "action": str(event),
                "params": json.dumps(payload, ensure_ascii=False),
                "now": now,
            },
        )
    except Exception:
        # Non-blocking: dashboard tables are optional.
        pass



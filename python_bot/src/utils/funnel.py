from __future__ import annotations

import json
from typing import Any, Dict, Optional

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
    payload = {"event": event}
    if service_key:
        payload["service"] = service_key
    if meta:
        payload["meta"] = meta

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



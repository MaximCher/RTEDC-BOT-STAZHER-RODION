from __future__ import annotations

from datetime import datetime, timedelta

_TTL = timedelta(minutes=30)
_CACHE: dict[int, tuple[int, list[int], datetime]] = {}


def set_event_media(
    *, user_id: int, chat_id: int, message_ids: list[int]
) -> None:
    if not message_ids:
        return
    _CACHE[user_id] = (chat_id, message_ids, datetime.utcnow())


def pop_event_media(
    *, user_id: int
) -> tuple[int, list[int]] | None:
    data = _CACHE.pop(user_id, None)
    if not data:
        return None
    chat_id, message_ids, ts = data
    if datetime.utcnow() - ts > _TTL:
        return None
    return chat_id, message_ids

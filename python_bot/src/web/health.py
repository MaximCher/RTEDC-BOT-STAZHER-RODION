from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.bot_heartbeat import BotHeartbeat


async def check_db(session: AsyncSession) -> bool:
    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_bot_heartbeat(session: AsyncSession, max_age_sec: int = 90) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": False, "age_sec": None}
    try:
        row = await session.get(BotHeartbeat, 1)
        if not row:
            return payload
        now = datetime.utcnow()
        age = (now - row.updated_at).total_seconds()
        payload.update(
            {
                "ok": age <= max_age_sec,
                "age_sec": int(age),
                "bot_username": row.bot_username,
                "bot_id": row.bot_id,
                "updated_at": row.updated_at.isoformat(),
            }
        )
        return payload
    except Exception:
        return payload


async def check_openai(timeout_sec: float = 3.0) -> Dict[str, Any]:
    if not settings.openai_api_key:
        return {"configured": False, "ok": False}
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout_sec)
    try:
        # Lightweight call: list models (still hits network)
        await client.models.list()
        return {"configured": True, "ok": True}
    except Exception as e:
        return {"configured": True, "ok": False, "error": str(e)}



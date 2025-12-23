from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.logger import logger
from src.models.bot_heartbeat import BotHeartbeat


async def upsert_heartbeat(
    session: AsyncSession,
    *,
    bot_username: Optional[str],
    bot_id: Optional[int],
) -> None:
    row = await session.get(BotHeartbeat, 1)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row is None:
        row = BotHeartbeat(
            id=1,
            bot_username=bot_username,
            bot_id=bot_id,
            started_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.bot_username = bot_username
        row.bot_id = bot_id
        row.updated_at = now
    await session.commit()


async def heartbeat_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    bot_username: Optional[str],
    bot_id: Optional[int],
    interval_sec: int = 30,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    interval = max(5, int(interval_sec))
    while True:
        if stop_event and stop_event.is_set():
            return
        try:
            async with session_factory() as session:
                await upsert_heartbeat(session, bot_username=bot_username, bot_id=bot_id)
        except Exception as e:
            logger.error("heartbeat_failed", error=str(e))
        # wait with stop support
        if stop_event:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
        else:
            await asyncio.sleep(interval)



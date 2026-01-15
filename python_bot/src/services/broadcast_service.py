from __future__ import annotations

import asyncio
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.logger import logger


async def broadcast_loop(
    *,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    interval_sec: int = 30,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """
    Legacy-compatible broadcast worker.

    Mirrors RTEDC-BOT/main.py broadcast_worker():
    - every 30s checks broadcast where sent=0 and send_at <= NOW()
    - sends text to all users from legacy `users` table
    - marks broadcast row as sent=1
    """
    while True:
        if stop_event and stop_event.is_set():
            return
        await asyncio.sleep(interval_sec)
        if stop_event and stop_event.is_set():
            return

        try:
            async with session_factory() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT id, text FROM broadcast "
                            "WHERE sent=0 AND send_at <= NOW()"
                        )
                    )
                ).all()
                if not rows:
                    continue

                user_rows = (await session.execute(text("SELECT user_id FROM users"))).all()
                user_ids = [int(r[0]) for r in user_rows if r and r[0] is not None]
                if not user_ids:
                    continue

                for b_id, text_msg in rows:
                    for uid in user_ids:
                        try:
                            await bot.send_message(uid, str(text_msg))
                            await asyncio.sleep(0.05)
                        except TelegramAPIError:
                            continue
                        except Exception:
                            continue
                    try:
                        await session.execute(
                            text("UPDATE broadcast SET sent=1 WHERE id=:id"),
                            {"id": int(b_id)},
                        )
                        await session.commit()
                    except Exception:
                        try:
                            await session.rollback()
                        except Exception:
                            pass
        except Exception as e:
            logger.error("broadcast_worker_failed", error=str(e))


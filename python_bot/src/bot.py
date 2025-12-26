from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict

from aiogram import Bot, Dispatcher
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.handlers import get_routers
from src.logger import logger
from src.middlewares.callback_serial import CallbackSerialMiddleware
from src.services.heartbeat_service import heartbeat_loop
from src.services.webapp_menu_service import webapp_menu_button_sync_loop


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session_factory = get_session_factory()
        async with session_factory() as session:  # type: AsyncSession
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    # Must be first: prevent concurrent callback_query races (double clicks).
    dp.update.middleware(CallbackSerialMiddleware())
    dp.update.middleware(DbSessionMiddleware())
    for r in get_routers():
        dp.include_router(r)
    return dp


async def run_bot(token: str) -> None:
    bot = Bot(token=token)
    dp = create_dispatcher()
    session_factory = get_session_factory()
    stop_event = asyncio.Event()

    try:
        me = await bot.get_me()
        hb_task = asyncio.create_task(
            heartbeat_loop(
                session_factory,
                bot_username=getattr(me, "username", None),
                bot_id=getattr(me, "id", None),
                interval_sec=30,
                stop_event=stop_event,
            )
        )
        webapp_task = asyncio.create_task(
            webapp_menu_button_sync_loop(
                bot=bot,
                session_factory=session_factory,
                stop_event=stop_event,
                interval_sec=20,
            )
        )
        await dp.start_polling(bot)
    except Exception as e:
        logger.error("bot_polling_failed", error=str(e))
        raise
    finally:
        stop_event.set()
        try:
            hb_task.cancel()
        except Exception:
            pass
        try:
            webapp_task.cancel()
        except Exception:
            pass
        await bot.session.close()



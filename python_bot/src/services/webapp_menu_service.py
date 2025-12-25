from __future__ import annotations

import asyncio
from typing import Callable

from aiogram.types import MenuButtonWebApp, WebAppInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import settings
from src.logger import logger
from src.models.staff import StaffMember
from src.utils.webapp_url import get_webapp_public_url


async def _list_admin_chat_ids(session: AsyncSession) -> list[int]:
    """
    In private chats: chat_id == user_id.
    We only show the Mini App to admins.
    """

    res = await session.execute(
        select(StaffMember.tg_user_id).where(StaffMember.role == "admin")
    )
    return [int(x) for x in res.scalars().all()]


async def webapp_menu_button_sync_loop(
    *,
    bot,
    session_factory: async_sessionmaker[AsyncSession],
    stop_event: asyncio.Event,
    interval_sec: int = 20,
) -> None:
    """
    Keep Telegram chat menu button (Mini App URL) up-to-date.

    This prevents situations where Tuna rotates the public URL and admins still have
    an old WebApp link in Telegram UI.
    """

    last_url: str | None = None
    while not stop_event.is_set():
        try:
            url = get_webapp_public_url(settings.webapp_public_url).strip()
            if url.startswith("https://") and url != last_url:
                async with session_factory() as session:
                    admin_ids = await _list_admin_chat_ids(session)
                for chat_id in admin_ids:
                    try:
                        await bot.set_chat_menu_button(
                            chat_id=chat_id,
                            menu_button=MenuButtonWebApp(
                                text="Админка SRVT", web_app=WebAppInfo(url=url)
                            ),
                        )
                    except Exception as e:
                        logger.warning(
                            "webapp_menu_button_update_failed",
                            chat_id=chat_id,
                            error=str(e),
                        )
                last_url = url
                logger.info(
                    "webapp_menu_button_updated",
                    url=url,
                    admins=len(admin_ids),
                )
        except Exception as e:
            logger.warning("webapp_menu_button_sync_failed", error=str(e))

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_sec)
        except asyncio.TimeoutError:
            pass



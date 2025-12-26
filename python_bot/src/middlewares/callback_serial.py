from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject


class CallbackSerialMiddleware(BaseMiddleware):
    """
    Serializes callback_query handling per chat.

    Why: users can tap multiple inline buttons quickly. If we ack callbacks immediately,
    Telegram stops showing a spinner and user can send more clicks. Without serialization,
    concurrent handlers may race and produce duplicated / out-of-order UI messages.
    """

    def __init__(self) -> None:
        self._locks: Dict[int, asyncio.Lock] = {}

    def _chat_id(self, cq: CallbackQuery) -> Optional[int]:
        try:
            if cq.message and cq.message.chat:
                return int(cq.message.chat.id)
        except Exception:
            pass
        try:
            return int(cq.from_user.id)
        except Exception:
            return None

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)

        chat_id = self._chat_id(event)
        if chat_id is None:
            return await handler(event, data)

        lock = self._locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[chat_id] = lock

        if lock.locked():
            # Best-effort: tell the user we're processing the previous click.
            try:
                await event.answer("Подождите…", cache_time=1)
            except Exception:
                pass
            return None

        async with lock:
            return await handler(event, data)



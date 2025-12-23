from __future__ import annotations

import asyncio

from src.bot import run_bot
from src.config import settings
from src.database import close_db, init_db
from src.logger import setup_logging


async def main() -> None:
    setup_logging(settings.log_level, settings.debug_mode)
    await init_db()
    try:
        await run_bot(settings.telegram_bot_token)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())



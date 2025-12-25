from __future__ import annotations

from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from src.config import settings
from src.logger import logger

Base = declarative_base()

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError(
            "Database engine is not initialized. Call init_db() first."
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError(
            "DB session factory not initialized. Call init_db() first."
        )
    return _session_factory


async def init_db() -> None:
    """Initialize engine and create tables."""
    global _engine, _session_factory

    connect_args = {}
    # Supabase managed Postgres typically requires SSL. asyncpg supports ssl as a string:
    # 'disable'|'prefer'|'allow'|'require'|'verify-ca'|'verify-full' (default: 'prefer').
    sslmode = (settings.postgres_sslmode or "").strip().lower()
    if sslmode:
        connect_args["ssl"] = sslmode

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug_mode,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Import models so metadata is populated
    from src import models  # noqa: F401

    async with _engine.begin() as conn:
        # tables
        await conn.run_sync(Base.metadata.create_all)
        # Hotfix: bot_id for bot_heartbeat must be bigint (Telegram IDs can exceed int32)
        try:
            await conn.execute(
                text(
                    "ALTER TABLE bot_heartbeat ALTER COLUMN bot_id TYPE BIGINT"
                )
            )
        except Exception:
            # table may not exist yet or already correct; ignore
            pass

    logger.info(
        "database_initialized",
        host=settings.postgres_host,
        db=settings.postgres_db,
    )

    # Seed staff (admins) from env for first run
    try:
        from src.services.staff_service import bootstrap_staff

        async with _session_factory() as session:  # type: ignore[misc]
            await bootstrap_staff(session)
    except Exception as e:
        logger.error("staff_bootstrap_failed", error=str(e))


async def close_db() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError(
            "DB session factory not initialized. Call init_db() first."
        )

    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

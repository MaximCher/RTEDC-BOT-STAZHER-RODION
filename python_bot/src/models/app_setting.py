from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @classmethod
    async def get(cls, session: AsyncSession, key: str) -> Optional[str]:
        res = await session.execute(select(cls).where(cls.key == key))
        row = res.scalar_one_or_none()
        return row.value if row else None

    @classmethod
    async def set(
        cls, session: AsyncSession, key: str, value: Optional[str]
    ) -> None:
        res = await session.execute(select(cls).where(cls.key == key))
        row = res.scalar_one_or_none()
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
            session.add(row)
            return
        session.add(cls(key=key, value=value))

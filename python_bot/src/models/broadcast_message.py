from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Integer, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class BroadcastMessage(Base):
    """
    Scheduled broadcast messages.

    Compatible with the existing `broadcast` table used by the broadcast worker.
    """

    __tablename__ = "broadcast"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    send_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    @classmethod
    async def list_pending(cls, session: AsyncSession, limit: int = 200) -> List["BroadcastMessage"]:
        q = (
            select(cls)
            .where(cls.sent == 0)
            .order_by(cls.send_at.asc().nulls_last(), cls.id.desc())
            .limit(limit)
        )
        res = await session.execute(q)
        return list(res.scalars().all())

    @classmethod
    async def delete_by_id(cls, session: AsyncSession, msg_id: int) -> bool:
        res = await session.execute(select(cls).where(cls.id == msg_id))
        row = res.scalar_one_or_none()
        if not row:
            return False
        await session.delete(row)
        return True


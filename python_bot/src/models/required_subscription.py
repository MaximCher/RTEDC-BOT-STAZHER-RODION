from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Integer, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class RequiredSubscription(Base):
    """
    A list of channels/groups a user must join before using the bot.

    chat_ref: either numeric chat id (-100...) or @username
    url: optional invite/public link for opening from InlineKeyboard
    """

    __tablename__ = "required_subscriptions"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    # channel|group|other
    kind: Mapped[str] = mapped_column(Text, default="channel")
    chat_ref: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    @classmethod
    async def list_all(
        cls, session: AsyncSession
    ) -> List["RequiredSubscription"]:
        res = await session.execute(select(cls).order_by(cls.id.asc()))
        return list(res.scalars().all())

    @classmethod
    async def delete_by_id(cls, session: AsyncSession, item_id: int) -> bool:
        res = await session.execute(select(cls).where(cls.id == item_id))
        row = res.scalar_one_or_none()
        if not row:
            return False
        await session.delete(row)
        return True

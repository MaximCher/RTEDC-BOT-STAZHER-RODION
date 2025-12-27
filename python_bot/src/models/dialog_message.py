from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class DialogMessage(Base):
    __tablename__ = "dialog_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user/assistant/system
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        *,
        user_id: int,
        message_text: str,
        role: str,
        chat_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
        message_id: Optional[int] = None,
    ) -> "DialogMessage":
        msg = cls(
            user_id=user_id,
            username=username,
            full_name=full_name,
            phone=phone,
            message_text=message_text,
            role=role,
            chat_id=chat_id,
            message_id=message_id,
        )
        session.add(msg)
        # NOTE: do not commit here. Transaction boundary is managed by caller (UoW).
        # We intentionally don't flush/refresh to keep logging cheap; ID assignment is
        # rarely needed for dialog/event logs.
        return msg

    @classmethod
    async def get_unique_users_count(cls, session: AsyncSession) -> int:
        q = select(func.count(func.distinct(cls.user_id)))
        res = await session.execute(q)
        return int(res.scalar() or 0)



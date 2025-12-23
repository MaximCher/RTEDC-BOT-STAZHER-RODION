from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import BigInteger, DateTime, Text, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class UserMemory(Base):
    __tablename__ = "user_memory"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selected_service: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conversation_history: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @classmethod
    async def get_or_create(cls, session: AsyncSession, user_id: int) -> "UserMemory":
        result = await session.execute(select(cls).where(cls.user_id == user_id))
        user = result.scalar_one_or_none()
        if user:
            return user
        user = cls(user_id=user_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    @classmethod
    async def update_user_data(
        cls,
        session: AsyncSession,
        user_id: int,
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
        selected_service: Optional[str] = None,
    ) -> "UserMemory":
        user = await cls.get_or_create(session, user_id)
        if full_name is not None:
            user.full_name = full_name
        if phone is not None:
            user.phone = phone
        if selected_service is not None:
            user.selected_service = selected_service
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    @classmethod
    async def add_message(
        cls,
        session: AsyncSession,
        user_id: int,
        role: str,
        content: str,
        max_messages: int = 50,
    ) -> None:
        user = await cls.get_or_create(session, user_id)
        history = list(user.conversation_history or [])
        history.append(
            {
                "role": role,
                "content": content,
                "ts": datetime.utcnow().isoformat(),
            }
        )
        if len(history) > max_messages:
            history = history[-max_messages:]
        user.conversation_history = history
        session.add(user)
        await session.commit()

    @classmethod
    async def get_conversation_history(
        cls, session: AsyncSession, user_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        user = await cls.get_or_create(session, user_id)
        history = list(user.conversation_history or [])
        return history[-limit:]



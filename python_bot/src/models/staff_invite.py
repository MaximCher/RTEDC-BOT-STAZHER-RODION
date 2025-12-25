from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class StaffInvite(Base):
    __tablename__ = "staff_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # admin|manager
    created_by_tg_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    used_by_tg_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    @classmethod
    async def get_by_token(cls, session: AsyncSession, token: str) -> Optional["StaffInvite"]:
        res = await session.execute(select(cls).where(cls.token == token))
        return res.scalar_one_or_none()




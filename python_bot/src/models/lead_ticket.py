from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class LeadTicket(Base):
    __tablename__ = "lead_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Lead (end-user) identifiers
    lead_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    lead_chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    # Bitrix
    bitrix_lead_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    service_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lead_full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lead_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lead_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lead_inn: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    meeting_window: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="new", index=True)  # new|open|closed
    assigned_to_tg_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    chat_enabled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0/1

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    @classmethod
    async def get_by_id(cls, session: AsyncSession, ticket_id: int) -> Optional["LeadTicket"]:
        res = await session.execute(select(cls).where(cls.id == ticket_id))
        return res.scalar_one_or_none()




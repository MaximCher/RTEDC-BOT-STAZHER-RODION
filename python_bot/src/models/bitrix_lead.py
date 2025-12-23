from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class BitrixLead(Base):
    __tablename__ = "bitrix_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    service: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        *,
        lead_id: int,
        user_id: int,
        full_name: Optional[str],
        phone: Optional[str],
        service: Optional[str],
    ) -> "BitrixLead":
        row = cls(
            lead_id=lead_id,
            user_id=user_id,
            full_name=full_name,
            phone=phone,
            service=service,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row



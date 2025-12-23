from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


StaffRole = Literal["admin", "manager"]


class StaffMember(Base):
    __tablename__ = "staff"
    __table_args__ = (UniqueConstraint("tg_user_id", name="uq_staff_tg_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # admin | manager
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)



from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class BotHeartbeat(Base):
    __tablename__ = "bot_heartbeat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bot_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)



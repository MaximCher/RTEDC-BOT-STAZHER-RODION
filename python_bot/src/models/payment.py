from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    provider: Mapped[str] = mapped_column(
        String(32), default="uniteller", index=True
    )

    order_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    upid: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")

    status: Mapped[str] = mapped_column(
        String(32), default="pending", index=True
    )
    payment_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    response_code: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True
    )
    response_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    prompt_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )

    consultation_request_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("consultation_requests.id"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

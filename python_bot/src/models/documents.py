from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Sequence, Tuple

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @classmethod
    async def create_document(
        cls,
        session: AsyncSession,
        *,
        filename: str,
        content_text: str,
        embedding: Optional[List[float]] = None,
        file_type: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> "Document":
        doc = cls(
            filename=filename,
            content_text=content_text,
            embedding=embedding,
            file_type=file_type,
            file_size=file_size,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        return doc

    @classmethod
    async def search_similar(
        cls,
        session: AsyncSession,
        *,
        query_embedding: List[float],
        limit: int = 5,
    ) -> Sequence[Tuple["Document", float]]:
        # cosine distance: smaller is better; similarity = 1 - distance
        distance = cls.embedding.cosine_distance(query_embedding)  # type: ignore[attr-defined]
        q = (
            select(cls, (1 - distance).label("similarity"))
            .where(cls.embedding.is_not(None))
            .order_by(distance.asc())
            .limit(limit)
        )
        res = await session.execute(q)
        return res.all()



from __future__ import annotations

from typing import List, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.logger import logger
from src.models.documents import Document


class VectorStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def create_embedding(self, text: str) -> Optional[List[float]]:
        if not self.client:
            return None
        trimmed = (text or "").strip()
        if not trimmed:
            return None
        if len(trimmed) > 32000:
            trimmed = trimmed[:32000]
        try:
            resp = await self.client.embeddings.create(
                model=settings.embedding_model,
                input=trimmed,
            )
            emb = resp.data[0].embedding
            return list(emb)
        except Exception as e:
            logger.error("openai_embedding_failed", error=str(e))
            return None

    async def add_document_chunk(
        self,
        *,
        filename: str,
        content: str,
        file_type: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> Document:
        embedding = await self.create_embedding(content)
        return await Document.create_document(
            self.session,
            filename=filename,
            content_text=content,
            embedding=embedding,
            file_type=file_type,
            file_size=file_size,
        )

    async def get_context_for_query(
        self,
        query: str,
        *,
        limit: int = 5,
        max_context_length: int = 2000,
    ) -> Optional[str]:
        embedding = await self.create_embedding(query)
        if not embedding:
            return None

        results = await Document.search_similar(
            self.session, query_embedding=embedding, limit=limit
        )
        if not results:
            return None

        context_parts: List[str] = []
        current = 0
        for doc, similarity in results:
            snippet = doc.content_text.strip()
            if not snippet:
                continue
            snippet = snippet[:1200]
            block = f"📄 {doc.filename} (sim={similarity:.2f})\n{snippet}"
            if current + len(block) > max_context_length:
                break
            context_parts.append(block)
            current += len(block)

        return "\n\n".join(context_parts) if context_parts else None



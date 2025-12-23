from __future__ import annotations

import argparse
import asyncio
import os
from typing import Iterable, List

import pdfplumber

from src.database import init_db, close_db, get_session_factory
from src.logger import setup_logging, logger
from src.vector_store import VectorStore


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    chunks: List[str] = []
    i = 0
    while i < len(cleaned):
        chunks.append(cleaned[i : i + chunk_size])
        i += max(1, chunk_size - overlap)
    return chunks


def extract_pdf_text(path: str) -> Iterable[str]:
    with pdfplumber.open(path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if not text:
                continue
            yield f"[PDF page {idx}]\n{text}"


async def ingest(pdf_path: str, filename: str) -> None:
    await init_db()
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            store = VectorStore(session)
            page_count = 0
            chunk_count = 0
            for page_text in extract_pdf_text(pdf_path):
                page_count += 1
                for chunk in chunk_text(page_text):
                    await store.add_document_chunk(
                        filename=filename,
                        content=chunk,
                        file_type="application/pdf",
                        file_size=os.path.getsize(pdf_path),
                    )
                    chunk_count += 1
                    if chunk_count % 25 == 0:
                        logger.info("pdf_ingest_progress", pages=page_count, chunks=chunk_count)

            logger.info("pdf_ingest_done", pages=page_count, chunks=chunk_count, pdf=pdf_path)
    finally:
        await close_db()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Ingest subsidies PDF into pgvector documents table.")
    p.add_argument(
        "--pdf",
        default="data/subsidies.pdf",
        help="Path to PDF file (default: data/subsidies.pdf)",
    )
    p.add_argument(
        "--name",
        default="subsidies.pdf",
        help="Filename label stored in DB (default: subsidies.pdf)",
    )
    return p


if __name__ == "__main__":
    setup_logging(os.getenv("LOG_LEVEL", "INFO"), os.getenv("DEBUG_MODE", "false") == "true")
    args = build_parser().parse_args()
    asyncio.run(ingest(args.pdf, args.name))



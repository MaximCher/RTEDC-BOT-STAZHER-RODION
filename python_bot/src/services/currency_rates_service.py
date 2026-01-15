from __future__ import annotations

import asyncio
import html
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.menu.currency_parser import get_cbr_rates, get_investing_rates
from src.menu.rates import get_all_rates_table
from src.menu.table_image import draw_simple_table


@dataclass(frozen=True)
class CurrencySnapshot:
    table: list[list[str]]
    created_at: datetime
    is_full: bool
    image_path: Optional[str] = None


_TTL = timedelta(seconds=120)
_lock = asyncio.Lock()
_fast_cache: CurrencySnapshot | None = None
_full_cache: CurrencySnapshot | None = None
_full_refresh_task: asyncio.Task[CurrencySnapshot] | None = None


def _is_fresh(s: CurrencySnapshot | None) -> bool:
    return bool(s and (datetime.utcnow() - s.created_at) <= _TTL)


def _build_fast_table() -> list[list[str]]:
    """
    Fast snapshot: no Selenium. Always quick enough to respond instantly.
    Full snapshot (with Selenium sources) is available via get_full_snapshot().
    """
    # Parallelize network calls to avoid "sum of timeouts" delays.
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_cbr = ex.submit(get_cbr_rates)
        f_inv = ex.submit(get_investing_rates)
        cbr = f_cbr.result()
        investing = f_inv.result()
    return [
        ["Источник", "USD", "EUR", "CNY", "USDT"],
        [
            "ЦБ РФ",
            str(cbr.get("USD", "-")),
            str(cbr.get("EUR", "-")),
            str(cbr.get("CNY", "-")),
            "-",
        ],
        [
            "Investing.com",
            "-",  # USD comes from Profinance (Selenium) in full snapshot
            str(investing.get("EUR", "-")),
            str(investing.get("CNY", "-")),
            "-",
        ],
        ["USDT", "-", "-", "-", "-"],
    ]


def _render_pre_table(table: list[list[str]]) -> str:
    if not table:
        return ""
    widths = [0] * len(table[0])
    for row in table:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    lines: list[str] = []
    for row in table:
        parts = []
        for i, cell in enumerate(row):
            s = str(cell)
            parts.append(s.ljust(widths[i]))
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def format_rates_text(table: list[list[str]], *, header: str = "Курсы валют") -> str:
    """
    HTML-safe formatted text with monospaced table.
    """
    pre = _render_pre_table(table)
    return f"<b>{html.escape(header)}</b>\n\n<pre>{html.escape(pre)}</pre>"


async def get_fast_snapshot() -> CurrencySnapshot:
    global _fast_cache
    async with _lock:
        if _is_fresh(_fast_cache):
            return _fast_cache  # type: ignore[return-value]

    table = await asyncio.to_thread(_build_fast_table)
    snap = CurrencySnapshot(table=table, created_at=datetime.utcnow(), is_full=False)
    async with _lock:
        _fast_cache = snap
    return snap


async def get_full_snapshot(*, image_path: str = "/tmp/currency_table.png") -> CurrencySnapshot:
    global _full_cache
    async with _lock:
        if _is_fresh(_full_cache):
            return _full_cache  # type: ignore[return-value]

    def _compute() -> CurrencySnapshot:
        table = get_all_rates_table()
        img_path = draw_simple_table(table, image_path)
        return CurrencySnapshot(
            table=table,
            created_at=datetime.utcnow(),
            is_full=True,
            image_path=img_path,
        )

    snap = await asyncio.to_thread(_compute)
    async with _lock:
        _full_cache = snap
    return snap


async def ensure_full_refresh(*, image_path: str = "/tmp/currency_table.png") -> None:
    """
    Start a full refresh in background (best-effort). Doesn't raise to callers.
    """
    global _full_refresh_task
    async with _lock:
        if _full_refresh_task and not _full_refresh_task.done():
            return
        _full_refresh_task = asyncio.create_task(get_full_snapshot(image_path=image_path))


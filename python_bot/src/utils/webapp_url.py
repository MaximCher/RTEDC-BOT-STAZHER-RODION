from __future__ import annotations

from pathlib import Path
from typing import Optional


def _read_first_line(path: Path) -> Optional[str]:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not raw:
        return None
    return raw.splitlines()[0].strip()


def get_webapp_public_url(fallback: str) -> str:
    """
    Resolve current Telegram Mini App URL.

    Priority:
    1) /app/.tuna_url (bind-mounted from host by docker-compose.prod.yml)
    2) fallback value from settings (WEBAPP_PUBLIC_URL)
    """

    tuna_url = _read_first_line(Path("/app/.tuna_url"))
    if tuna_url and tuna_url.startswith("https://"):
        return tuna_url
    return fallback



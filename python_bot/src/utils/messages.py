from __future__ import annotations

from src.config import MESSAGES


def msg(key: str) -> str:
    return MESSAGES.get(key, key)



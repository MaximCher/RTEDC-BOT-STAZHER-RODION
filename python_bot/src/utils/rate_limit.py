from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict


@dataclass
class Counter:
    window_start: float
    count: int


class FixedWindowRateLimiter:
    def __init__(self, limit: int, window_sec: int) -> None:
        self.limit = limit
        self.window_sec = window_sec
        self._counters: Dict[str, Counter] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        c = self._counters.get(key)
        if c is None:
            self._counters[key] = Counter(window_start=now, count=1)
            return True
        if now - c.window_start > self.window_sec:
            self._counters[key] = Counter(window_start=now, count=1)
            return True
        if c.count >= self.limit:
            return False
        c.count += 1
        return True


# Backwards-compatible alias for web code.
FixedWindowLimiter = FixedWindowRateLimiter



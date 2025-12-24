from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict


@dataclass
class Counter:
    window_start: float
    count: int


class FixedWindowRateLimiter:
    def __init__(self, limit: int, window_sec: int, *, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window_sec = window_sec
        self.max_keys = max_keys
        self._counters: Dict[str, Counter] = {}
        self._ops: int = 0

    def allow(self, key: str) -> bool:
        now = time.time()
        self._ops += 1
        # Prevent unbounded growth: occasionally prune expired keys, and hard-cap size.
        if self._ops % 256 == 0 or len(self._counters) > self.max_keys:
            self._prune(now)

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

    def _prune(self, now: float) -> None:
        # Drop expired counters.
        expired = [k for k, c in self._counters.items() if now - c.window_start > self.window_sec]
        for k in expired:
            self._counters.pop(k, None)

        # If still too big, evict oldest windows first (best-effort).
        if len(self._counters) > self.max_keys:
            overflow = len(self._counters) - self.max_keys
            oldest = sorted(self._counters.items(), key=lambda kv: kv[1].window_start)[:overflow]
            for k, _ in oldest:
                self._counters.pop(k, None)


# Backwards-compatible alias for web code.
FixedWindowLimiter = FixedWindowRateLimiter



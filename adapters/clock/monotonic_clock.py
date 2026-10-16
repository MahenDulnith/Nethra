"""Single source of monotonic timestamps across Nethra (L1)."""

from __future__ import annotations

import time


class MonotonicClock:
    """Provides monotonic nanosecond and millisecond timestamps for latency measurement."""

    @staticmethod
    def now_ns() -> int:
        return time.monotonic_ns()

    @staticmethod
    def now_ms() -> int:
        return time.monotonic_ns() // 1_000_000

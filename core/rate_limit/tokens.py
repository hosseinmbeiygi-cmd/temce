from __future__ import annotations

import asyncio
import time

from core.logging import get_logger

logger = get_logger(__name__)


class TokenBucket:
    """Classic token-bucket rate limiter (refill = rate tokens/second).

    Both async and sync acquisition paths share the same refill state so a
    tier limiter can use whichever fits its call site. A monotonic clock
    offset (``_clock_offset``) lets tests advance time deterministically
    without patching ``time.monotonic`` globally.
    """

    def __init__(self, rate: float, burst: int | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        if burst is not None and burst < 1:
            raise ValueError("burst must be >= 1")
        self.rate = rate
        self.burst = burst or int(rate)
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()
        self._clock_offset = 0.0
        self._lock = asyncio.Lock()

    # ── clock helpers (test determinism) ────────────────────────────
    def _now(self) -> float:
        return time.monotonic() + self._clock_offset

    def advance_time(self, seconds: float) -> None:
        """Shift the bucket's clock forward (refills tokens accordingly)."""
        self._refill()
        self._clock_offset += seconds

    # ── refill math (shared by sync/async) ──────────────────────────
    def _refill(self) -> None:
        now = self._now()
        elapsed = now - self.last_refill
        self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate)
        self.last_refill = now

    # ── sync API ────────────────────────────────────────────────────
    def acquire_sync(self) -> float:
        """Consume one token; return the seconds to wait when exhausted (0 = admitted)."""
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return 0.0
        wait = (1.0 - self.tokens) / self.rate
        self.tokens = 0.0
        return wait

    def try_acquire_sync(self) -> bool:
        """Consume one token; return False immediately when the bucket is empty."""
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    @property
    def available_sync(self) -> float:
        self._refill()
        return self.tokens

    @property
    def available(self) -> float:
        return self.available_sync

    # ── async API (unchanged contract) ──────────────────────────────
    async def acquire(self) -> float:
        async with self._lock:
            return self.acquire_sync()

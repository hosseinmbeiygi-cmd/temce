from __future__ import annotations

import time

from ingestion.http_client import RateLimiter


class TestRateLimiter:
    async def test_allows_initial_calls(self) -> None:
        limiter = RateLimiter(max_calls=5, period=1.0)
        for _ in range(5):
            start = time.monotonic()
            await limiter.acquire()
            elapsed = time.monotonic() - start
            assert elapsed < 0.1

    async def test_throttles_excess_calls(self) -> None:
        limiter = RateLimiter(max_calls=2, period=10.0)
        for _ in range(2):
            await limiter.acquire()
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 2.5


from __future__ import annotations

import asyncio
import secrets
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class RateLimiter:
    """Sliding-window rate limiter.

    Each key has a window_seconds (default 60s) and a burst (max requests per window).
    Tokens older than the window are pruned on each check.
    """

    def __init__(self) -> None:
        self._limits: dict[str, tuple[float, int, float, float, list[float]]] = {}
        # ``allow`` is synchronous and can also be called from thread-pool
        # workers (auth helpers and legacy jobs). Protect state updates so two
        # threads cannot both observe the same free burst slot.
        self._lock = threading.RLock()

    def set_limit(self, key: str, rate: float, burst: int = 1, window_seconds: float = 60.0) -> None:
        """Register a rate limit for a key.

        Args:
            key: Unique identifier (e.g. "api:127.0.0.1:/api/v1/signals").
            rate: Requests per second (used for acquire/wait calculations).
            burst: Maximum requests allowed in the window.
            window_seconds: Sliding window duration in seconds.
        """
        if burst < 1 or window_seconds <= 0 or rate < 0:
            raise ValueError("rate must be non-negative, burst >= 1, and window_seconds > 0")
        with self._lock:
            self._limits[key] = (rate, burst, window_seconds, time.monotonic(), [])

    def has_limit(self, key: str) -> bool:
        """Check if a rate limit is registered for the given key."""
        with self._lock:
            return key in self._limits

    def allow(self, key: str) -> bool:
        """Check whether a request is allowed under the sliding window."""
        with self._lock:
            config = self._limits.get(key)
            if config is None:
                return True
            rate, burst, window_seconds, _, tokens = config
            now = time.monotonic()
            cutoff = now - window_seconds
            active = [t for t in tokens if t > cutoff]
            if len(active) >= burst:
                return False
            active.append(now)
            self._limits[key] = (rate, burst, window_seconds, now, active)
            return True

    def remaining(self, key: str) -> int:
        """Return the number of remaining allowed requests in the current window."""
        with self._lock:
            config = self._limits.get(key)
            if config is None:
                return 999
            _, burst, window_seconds, _, tokens = config
            cutoff = time.monotonic() - window_seconds
            active = sum(1 for t in tokens if t > cutoff)
            return max(0, burst - active)

    async def allow_async(self, key: str, max_calls: int, window_seconds: float = 60.0) -> tuple[bool, int]:
        """Atomically apply a Redis sliding window when Redis is available.

        The synchronous in-memory API remains available for unit tests and
        single-process fallback. API middleware uses this method so multiple
        workers/replicas share one bucket instead of each keeping a private
        counter.
        """
        try:
            from core.cache import get_cache

            client = get_cache().client
            if client is not None:
                now_ms = int(time.time() * 1000)
                window_ms = max(1, int(window_seconds * 1000))
                member = f"{now_ms}:{secrets.token_hex(8)}"
                script = """
                local now = tonumber(ARGV[1])
                local window = tonumber(ARGV[2])
                local limit = tonumber(ARGV[3])
                local member = ARGV[4]
                redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now - window)
                local count = redis.call('ZCARD', KEYS[1])
                if count >= limit then
                    return {0, count}
                end
                redis.call('ZADD', KEYS[1], now, member)
                redis.call('PEXPIRE', KEYS[1], window)
                return {1, count + 1}
                """
                result = await client.eval(
                    script,
                    1,
                    f"ratelimit:{key}",
                    now_ms,
                    window_ms,
                    max_calls,
                    member,
                )
                allowed = bool(int(result[0]))
                count = int(result[1])
                return allowed, max(0, max_calls - count)
        except Exception as exc:  # noqa: BLE001 — use local safety fallback
            logger.debug("Redis rate limit unavailable; using local bucket: %s", exc)

        if not self.has_limit(key):
            self.set_limit(
                key,
                rate=max_calls / max(window_seconds, 0.001),
                burst=max_calls,
                window_seconds=window_seconds,
            )
        allowed = self.allow(key)
        return allowed, self.remaining(key)

    async def acquire(self, key: str) -> float:
        """Wait until a sliding-window slot is available, then reserve it.

        The previous implementation slept once and wrote a timestamp based on
        stale state, which could over-admit requests after concurrent callers.
        Re-checking after every sleep keeps the reservation atomic and honors
        the configured window even when several coroutines wait together.
        """
        total_wait = 0.0
        while True:
            with self._lock:
                config = self._limits.get(key)
                if config is None:
                    return total_wait
                rate, burst, window_seconds, _, tokens = config
                now = time.monotonic()
                active = [t for t in tokens if t > now - window_seconds]
                if len(active) < burst:
                    active.append(now)
                    self._limits[key] = (rate, burst, window_seconds, now, active)
                    return total_wait
                wait = max(0.001, active[0] + window_seconds - now)
            await asyncio.sleep(wait)
            total_wait += wait

    async def limit(self, key: str, coro: Callable[[], Coroutine[Any, Any, T]]) -> T:
        await self.acquire(key)
        return await coro()

    def wrap(self, key: str, rate: float, burst: int | None = None) -> Callable[..., Any]:
        """Decorator that rate-limits a callable.

        ``rate`` is interpreted as *requests per minute* (matching the
        ``*_rate_limit_per_minute`` settings). ``burst`` defaults to the
        per-minute rate rounded up so a freshly registered key doesn't
        accidentally lock itself out immediately.

        Note: this is a minute-based convenience wrapper; the underlying
        ``set_limit`` treats ``rate`` as requests-per-second for
        ``acquire()`` wait-time calculations, so the effective smoothing
        here is 1s/rate. For precise sub-minute throttling use
        ``set_limit``/``acquire`` directly.
        """
        burst = burst or max(1, int(rate))
        self.set_limit(key, rate=rate / 60.0, burst=burst, window_seconds=60.0)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                await self.acquire(key)
                return await func(*args, **kwargs)

            return wrapper

        return decorator


_global_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _global_limiter


async def throttle(key: str, rate: float) -> None:
    await _global_limiter.acquire(key)

"""
Token-bucket rate limiter for BrsApi endpoints.

Implements per-endpoint-category rate limiting with:
- Token bucket algorithm
- Configurable rates (requests per minute)
- Burst support
- Thread-safe async implementation
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from logging import getLogger
from typing import Any

logger = getLogger(__name__)


@dataclass
class Bucket:
    """A single token bucket."""
    key: str
    max_tokens: float
    refill_rate: float            # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.max_tokens)
        self.last_refill = asyncio.get_event_loop().time()

    def _refill(self, now: float) -> None:
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


class RateLimiter:
    """
    Async token-bucket rate limiter.

    Usage::

        limiter = RateLimiter()
        async with limiter.acquire("tsetmc"):
            data = await fetch(...)
    """

    def __init__(self) -> None:
        self._buckets: dict[str, Bucket] = {}
        self._lock = asyncio.Lock()
        self._default_max_tokens = 30.0
        self._default_refill_rate = 0.5   # 30 rpm → 0.5 tps

    # ── Public API ──────────────────────────────

    def configure(self, key: str, requests_per_minute: int) -> None:
        """
        Set the rate limit for a given category / endpoint key.

        Args:
            key: Category name (e.g. ``"tsetmc"``, ``"codal"``, ``"ime"``).
            requests_per_minute: Max requests per minute (0 = unlimited).
        """
        if key in self._buckets:
            bucket = self._buckets[key]
            now = asyncio.get_event_loop().time()
            bucket._refill(now)
            bucket.max_tokens = float(requests_per_minute)
            bucket.refill_rate = requests_per_minute / 60.0
        else:
            self._buckets[key] = Bucket(
                key=key,
                max_tokens=float(requests_per_minute),
                refill_rate=requests_per_minute / 60.0,
            )

    async def acquire(self, key: str, tokens: int = 1) -> None:
        """
        Acquire *tokens* from the bucket identified by *key*.

        Blocks (async) until sufficient tokens are available.
        """
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                # Auto-create with default rate
                self.configure(key, int(self._default_refill_rate * 60))
                bucket = self._buckets[key]

            now = asyncio.get_event_loop().time()
            bucket._refill(now)

            if bucket.max_tokens <= 0:
                # Unlimited – no wait
                return

            if bucket.tokens >= tokens:
                bucket.tokens -= tokens
                return

            # Not enough tokens — calculate wait
            deficit = tokens - bucket.tokens
            wait_seconds = deficit / bucket.refill_rate
            logger.debug("Rate limited %s: waiting %.2fs", key, wait_seconds)

        # Release the lock before sleeping so other tasks can refill
        await asyncio.sleep(wait_seconds)

        # Re-acquire
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket:
                now = asyncio.get_event_loop().time()
                bucket._refill(now)
                bucket.tokens = max(0.0, bucket.tokens - tokens)

    # ── Status ─────────────────────────────────

    def get_bucket_status(self, key: str) -> dict[str, Any] | None:
        """Return current token bucket status for a given key."""
        bucket = self._buckets.get(key)
        if bucket is None:
            return None
        return {
            "key": bucket.key,
            "max_tokens": bucket.max_tokens,
            "current_tokens": round(bucket.tokens, 1),
            "refill_rate": round(bucket.refill_rate, 3),
        }

    def all_bucket_status(self) -> dict[str, dict[str, Any]]:
        """Return status for all tracked buckets."""
        return {
            key: self.get_bucket_status(key) or {}
            for key in self._buckets
        }

    # ── Context-manager sugar ──────────────────

    def limit(self, key: str, tokens: int = 1) -> "RateLimitContext":
        """Return an async context manager that acquires tokens on enter."""
        return RateLimitContext(limiter=self, key=key, tokens=tokens)


class RateLimitContext:
    """Async context manager returned by ``RateLimiter.limit()``."""

    def __init__(self, limiter: RateLimiter, key: str, tokens: int = 1) -> None:
        self._limiter = limiter
        self._key = key
        self._tokens = tokens

    async def __aenter__(self) -> None:
        await self._limiter.acquire(self._key, self._tokens)

    async def __aexit__(self, *args: Any) -> None:
        pass


# Global singleton
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

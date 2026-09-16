"""کلاس‌های پایه Adapter."""

from __future__ import annotations

import contextlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from core.time import now_utc, utc_now_naive

from ..constants import CACHE_TTL_SECONDS, STALE_THRESHOLD_HOURS


class AdapterError(RuntimeError):
    """خطای عمومی Adapter."""


class AdapterRateLimitError(AdapterError):
    """خطای Rate Limit — باید backoff شدید اعمال شود."""


class AdapterParseError(AdapterError):
    """خطای پارس کردن پاسخ (تغییر ساختار HTML/JSON)."""


@dataclass
class SourceData:
    """خروجی استاندارد هر Adapter."""

    source: str
    symbol: str
    fetched_at: datetime = field(default_factory=utc_now_naive)
    is_stale: bool = False
    last_successful_fetch: datetime | None = None
    data: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0  # 0..1


class BaseAdapter(ABC):
    """کلاس پایه برای همه Adapterها.

    زیرکلاس‌ها باید source_name() و fetch() را پیاده کنند.
    """

    name: str = "base"
    cache_ttl_seconds: int = 3600
    stale_threshold_hours: int = 24

    def __init__(self, cache: Any | None = None, redis_client: Any | None = None):
        self.cache = cache  # می‌تواند Redis باشد یا in-memory dict
        self.redis = redis_client
        self.last_success: datetime | None = None
        self.consecutive_failures = 0
        self.total_calls = 0
        self.total_errors = 0
        self.latency_samples: list[int] = []

    @classmethod
    def source_name(cls) -> str:
        return cls.name

    @abstractmethod
    async def fetch(self, symbol: str) -> SourceData:
        """دریافت داده خام برای یک نماد."""

    def _check_stale(self) -> bool:
        if self.last_success is None:
            return True
        threshold = timedelta(hours=self.stale_threshold_hours)
        return utc_now_naive() - self.last_success > threshold

    async def _cache_get(self, key: str) -> SourceData | None:
        if self.cache is None:
            return None
        try:
            cached = await self.cache.get(key)
        except Exception:
            return None
        if cached is None:
            return None
        return cached

    async def _cache_set(self, key: str, value: SourceData, ttl: int | None = None) -> None:
        if self.cache is None:
            return
        with contextlib.suppress(Exception):
            await self.cache.set(key, value, ttl or self.cache_ttl_seconds)

    async def get(self, symbol: str) -> SourceData:
        """دریافت با کش + stale flag + circuit breaker."""
        from ..resilience import get_circuit_breaker

        cache_key = f"adapter:{self.name}:{symbol}"
        cached = await self._cache_get(cache_key)
        if cached is not None:
            cached.is_stale = self._check_stale()
            cached.last_successful_fetch = self.last_success
            return cached

        cb = get_circuit_breaker(self.name, self.redis)
        self.total_calls += 1
        try:
            start = now_utc()
            data = await cb.call(self.fetch, symbol)
            elapsed_ms = int((now_utc() - start).total_seconds() * 1000)
            self.latency_samples.append(elapsed_ms)
            if len(self.latency_samples) > 100:
                self.latency_samples = self.latency_samples[-100:]
            self.last_success = utc_now_naive()
            self.consecutive_failures = 0
            await self._cache_set(cache_key, data)
            data.last_successful_fetch = self.last_success
            return data
        except Exception:
            self.total_errors += 1
            self.consecutive_failures += 1
            raise

    @property
    def avg_latency_ms(self) -> int:
        if not self.latency_samples:
            return 0
        return int(sum(self.latency_samples) / len(self.latency_samples))

    def health_snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "last_success_at": self.last_success,
            "last_failure_at": None,
            "consecutive_failures": self.consecutive_failures,
            "circuit_state": "closed",
            "total_calls": self.total_calls,
            "total_errors": self.total_errors,
            "avg_latency_ms": self.avg_latency_ms,
            "is_stale": self._check_stale(),
        }


def build_tsetmc_adapter():
    """ساخت TSETMCAdapter با TTL از constants."""
    from .tsetmc import TSETMCAdapter

    return TSETMCAdapter()


def build_fipiran_adapter():
    from .fipiran import FipiranAdapter

    return FipiranAdapter()


def build_codal_adapter():
    from .codal import CodalAdapter

    return CodalAdapter()


def get_default_ttl(source: str) -> int:
    return CACHE_TTL_SECONDS.get(source, 3600)


def get_default_stale_threshold(source: str) -> int:
    return STALE_THRESHOLD_HOURS.get(source, 24)

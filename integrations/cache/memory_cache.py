"""LEGACY process-local TTL cache (deprecated).

Not a cache *system*: values live in this worker only and vanish on restart.
Shared state must go through :mod:`core.cache` (Redis). Kept for backwards
compatibility of ``integrations.cache`` imports only.
"""

from __future__ import annotations

import contextlib
import time
import warnings
from collections import OrderedDict
from collections.abc import Callable
from threading import Lock
from typing import Any


class TTLEntry:
    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class MemoryCache:
    """DEPRECATED worker-local TTL store. Use :func:`core.cache.get_cache`."""

    def __init__(self, default_ttl: float = 300.0, max_size: int = 10000):
        warnings.warn(
            "integrations.cache.MemoryCache is deprecated; use core.cache.get_cache()",
            DeprecationWarning,
            stacklevel=2,
        )
        self._store: dict[str, TTLEntry] = OrderedDict()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expired:
            self._delete(key)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            if len(self._store) >= self._max_size:
                self._evict()
            self._store[key] = TTLEntry(value, ttl)

    def delete(self, key: str) -> bool:
        return self._delete(key)

    def _delete(self, key: str) -> bool:
        try:
            del self._store[key]
            return True
        except KeyError:
            return False

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _evict(self) -> None:
        with contextlib.suppress(KeyError):
            self._store.popitem(last=False)

    def purge_expired(self) -> int:
        expired = [k for k, v in self._store.items() if v.expired]
        for k in expired:
            self._delete(k)
        return len(expired)

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: float | None = None) -> Any:
        existing = self.get(key)
        if existing is not None:
            return existing
        value = factory()
        self.set(key, value, ttl)
        return value

    @property
    def size(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return self.exists(key)

    def __getitem__(self, key: str) -> Any | None:
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

"""DEPRECATED compatibility layer for the platform's single cache.

There is exactly one cache implementation: :mod:`core.cache`
(``get_cache()``) — one Redis client per process, JSON payloads, circuit
breaker and event-loop safety. This package predates that unification and is
kept only so existing imports keep resolving; constructing any of its classes
raises ``DeprecationWarning`` (the import itself stays silent so a strict
``-W error`` build can still resolve the names).

New code must use ``core.cache`` directly. The only implementation living
here is :class:`~integrations.cache.memory_cache.MemoryCache`, a process-local
TTL store that is never shared across workers — do not use it for anything
another worker or replica needs to observe.
"""

from __future__ import annotations

from integrations.cache.key_builder import KeyBuilder
from integrations.cache.memory_cache import MemoryCache
from integrations.cache.redis_client import RedisClient
from integrations.cache.ttl_manager import TTLManager

__all__ = ["KeyBuilder", "MemoryCache", "RedisClient", "TTLManager"]

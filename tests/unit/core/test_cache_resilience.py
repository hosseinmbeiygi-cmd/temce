"""The cache must never hang a request on a dead Redis client.

Two failure modes are covered:

* a client created on an event loop that has since closed — pytest creates one
  loop per session/test, and awaiting a transport bound to a closed loop stalls
  in ``_wait_for_data`` and then raises ``RuntimeError: Event loop is closed``;
* a client that exists but whose commands fail — one broken connection used to
  cost every caller the full socket timeout, so a breaker now stops calls.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from core.cache import CacheService, reset_cache


class _FakeClient:
    """Minimal redis stand-in that records calls and can fail."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls = 0
        self.error = error

    async def get(self, key: str) -> Any:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return '{"ok": true}'

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.calls += 1
        if self.error is not None:
            raise self.error

    async def aclose(self) -> None:
        pass


def _attach(cache: CacheService, client: _FakeClient, loop: asyncio.AbstractEventLoop) -> None:
    cache._redis = client  # noqa: SLF001 — deliberately simulating a live client
    cache._loop = loop  # noqa: SLF001


@pytest.mark.asyncio
async def test_client_from_a_closed_loop_is_detached() -> None:
    cache = CacheService(redis_url="redis://example.invalid:6379/0")
    old_loop = asyncio.new_event_loop()
    client = _FakeClient()
    _attach(cache, client, old_loop)
    old_loop.close()

    # Different (running) loop than the one the client was built on.
    assert cache.client is None
    assert await cache.get("k") is None  # null-cache fallback, no exception
    assert client.calls == 0

    # The stale reference is dropped so a later initialize() can reconnect.
    assert cache._redis is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_failed_command_opens_the_breaker() -> None:
    cache = CacheService(redis_url="redis://example.invalid:6379/0")
    cache.breaker_seconds = 30.0
    client = _FakeClient(error=ConnectionResetError("boom"))
    _attach(cache, client, asyncio.get_running_loop())

    assert await cache.get("k") is None
    assert client.calls == 1

    # Breaker open: further calls are skipped entirely instead of retrying the
    # dead socket on every request.
    assert cache.client is None
    assert await cache.get("k") is None
    await cache.set("k", "v")
    assert client.calls == 1


@pytest.mark.asyncio
async def test_breaker_expires() -> None:
    cache = CacheService(redis_url="redis://example.invalid:6379/0")
    client = _FakeClient()
    _attach(cache, client, asyncio.get_running_loop())
    cache._unavailable_until = time.monotonic() - 1  # noqa: SLF001 — breaker already expired

    assert await cache.get("k") == {"ok": True}
    assert client.calls == 1


@pytest.mark.asyncio
async def test_is_connected_reflects_the_breaker() -> None:
    cache = CacheService(redis_url="redis://example.invalid:6379/0")
    assert cache.is_connected is False  # no client at all

    _attach(cache, _FakeClient(), asyncio.get_running_loop())
    assert cache.is_connected is True

    cache._unavailable_until = time.monotonic() + 60  # noqa: SLF001 — breaker open
    assert cache.is_connected is False


@pytest.mark.asyncio
async def test_pop_survives_a_failing_client() -> None:
    cache = CacheService(redis_url="redis://example.invalid:6379/0")
    client = _FakeClient(error=ConnectionError("down"))
    _attach(cache, client, asyncio.get_running_loop())

    assert await cache.pop("k") is None
    assert cache.client is None


def test_reset_cache_drops_the_singleton() -> None:
    from core import cache as cache_module

    first = cache_module.get_cache()
    reset_cache()
    assert cache_module.get_cache() is not first

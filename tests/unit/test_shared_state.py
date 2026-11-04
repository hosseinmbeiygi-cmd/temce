"""Tests for core.shared_state — Redis-backed state shared across workers.

Covers:
  - load() overlays the persisted document, keeps schema defaults for absent
    keys, ignores unknown keys and trims the bounded history.
  - load()/save() degrade gracefully when Redis is unavailable.
  - state_transaction() serialises read-modify-write cycles across two
    "workers" (two mirrors sharing one Redis) so no update is lost.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from unittest.mock import patch

import pytest

from core.shared_state import RedisStateDocument, reset_state_locker, state_transaction

# ── Fakes ────────────────────────────────────────────────────────────


class FakeRedis:
    """Minimal redis.asyncio surface: SET NX PX, GET, EVAL (lock release)."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}

    async def set(self, key: str, value: str, nx: bool = False, px: int | None = None) -> bool | None:
        now = time.monotonic()
        entry = self._data.get(key)
        if entry is not None:
            _, expires_at = entry
            if expires_at is not None and now >= expires_at:
                del self._data[key]
            elif nx:
                return None
        self._data[key] = (value, (now + px / 1000.0) if px else None)
        return True

    async def get(self, key: str) -> str | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.monotonic() >= expires_at:
            del self._data[key]
            return None
        return value

    async def eval(self, script: str, numkeys: int, *args) -> int:
        key, owner = args[0], args[1]
        if await self.get(key) != owner:
            return 0
        if "del" in script:
            del self._data[key]
            return 1
        return 0


class FakeCache:
    """CacheService stand-in: JSON documents plus the raw client for locks."""

    def __init__(self, client: FakeRedis | None, docs: dict[str, str] | None = None) -> None:
        self._client = client
        # Shared between workers of the same "Redis" in the concurrency test.
        self._docs: dict[str, str] = docs if docs is not None else {}

    @property
    def client(self):
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    async def get(self, key: str):
        raw = self._docs.get(key)
        return None if raw is None else json.loads(raw)

    async def set_persistent(self, key: str, value) -> bool:
        if not self.is_connected:
            return False
        self._docs[key] = json.dumps(value)
        return True

    def seed(self, key: str, value) -> None:
        self._docs[key] = json.dumps(value)

    def payload(self, key: str):
        return json.loads(self._docs[key])


DEFAULTS = {
    "run_count": 0,
    "enabled": True,
    "last_accuracy": {},
}


def _mirror() -> dict:
    return {**DEFAULTS, "history": deque(maxlen=100)}


def _document(cache: FakeCache, mirror: dict, key: str = "test:doc") -> RedisStateDocument:
    return RedisStateDocument(
        mirror,
        key=key,
        defaults=DEFAULTS,
        history_key="history",
        history_limit=100,
        cache=cache,
    )


@pytest.fixture(autouse=True)
def _clean_locker():
    reset_state_locker()
    yield
    reset_state_locker()


# ── load / save ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_overlays_persisted_document():
    cache = FakeCache(FakeRedis())
    cache.seed(
        "test:doc",
        {"run_count": 7, "history": [{"run": i} for i in range(1, 5)], "legacy_key": "ignored"},
    )
    mirror = _mirror()

    assert await _document(cache, mirror).load() is True

    assert mirror["run_count"] == 7
    assert mirror["enabled"] is True  # absent from payload → default kept
    assert list(mirror["history"]) == [{"run": 1}, {"run": 2}, {"run": 3}, {"run": 4}]
    assert "legacy_key" not in mirror


@pytest.mark.asyncio
async def test_load_trims_history_to_limit():
    cache = FakeCache(FakeRedis())
    cache.seed("test:doc", {"history": [{"run": i} for i in range(150)]})
    mirror = _mirror()
    history_ref = mirror["history"]

    await _document(cache, mirror).load()

    assert len(mirror["history"]) == 100
    assert mirror["history"][-1] == {"run": 149}
    # The deque object is preserved so holders of the reference see the update.
    assert mirror["history"] is history_ref


@pytest.mark.asyncio
async def test_load_keeps_mirror_when_redis_unavailable():
    cache = FakeCache(None)
    mirror = _mirror()
    mirror["run_count"] = 3

    assert await _document(cache, mirror).load() is False
    assert mirror["run_count"] == 3


@pytest.mark.asyncio
async def test_save_is_json_safe_and_reports_success():
    cache = FakeCache(FakeRedis())
    mirror = _mirror()
    mirror["run_count"] = 2
    mirror["history"].append({"run": 2})
    doc = _document(cache, mirror)

    assert await doc.save() is True
    assert cache.payload("test:doc") == {
        "run_count": 2,
        "enabled": True,
        "last_accuracy": {},
        "history": [{"run": 2}],
    }


@pytest.mark.asyncio
async def test_save_returns_false_without_redis():
    cache = FakeCache(None)
    assert await _document(cache, _mirror()).save() is False


# ── transaction ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transaction_serialises_concurrent_updates():
    """Two workers incrementing run_count must both land (no lost update)."""
    shared = FakeRedis()
    cache_a = FakeCache(shared)
    mirror_a = _mirror()
    cache_b = FakeCache(shared, docs=cache_a._docs)
    mirror_b = _mirror()
    mirror_b = _mirror()

    async def increment(cache: FakeCache, mirror: dict) -> None:
        async with state_transaction([_document(cache, mirror)], lock_key="test:lock", wait_seconds=5.0):
            mirror["run_count"] += 1
            await asyncio.sleep(0.02)

    with patch("jobs.locking.get_cache", return_value=cache_a):
        await asyncio.gather(
            increment(cache_a, mirror_a),
            increment(cache_b, mirror_b),
        )

    # Both increments reached Redis: neither writer overwrote the other.
    assert cache_a.payload("test:doc")["run_count"] == 2
    # The first writer saw 0, the second reloaded and saw 1 — order-independent.
    assert sorted([mirror_a["run_count"], mirror_b["run_count"]]) == [1, 2]


@pytest.mark.asyncio
async def test_transaction_applies_mutations_without_redis():
    cache = FakeCache(None)
    mirror = _mirror()

    async with state_transaction([_document(cache, mirror)], lock_key="test:lock", wait_seconds=0.1):
        mirror["run_count"] += 1

    assert mirror["run_count"] == 1


@pytest.mark.asyncio
async def test_transaction_releases_lock_for_next_holder():
    shared = FakeRedis()
    cache = FakeCache(shared)
    doc_mirror = _mirror()

    async with state_transaction([_document(cache, doc_mirror)], lock_key="test:lock"):
        pass

    assert await shared.get("test:lock") is None

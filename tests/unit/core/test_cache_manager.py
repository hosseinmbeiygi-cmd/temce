"""Unit tests for core/cache_manager.CacheManager (3-layer cache)."""

from __future__ import annotations

import pytest

from core.cache_manager import CacheManager, LRUCache

# ── LRUCache ────────────────────────────────────────────────────────────


class TestLRUCache:
    def test_get_put_roundtrip(self) -> None:
        c = LRUCache(maxsize=3)
        c.put("a", 1)
        c.put("b", 2)
        assert c.get("a") == 1
        assert c.get("b") == 2
        assert len(c) == 2

    def test_evicts_lru_when_full(self) -> None:
        c = LRUCache(maxsize=3)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        # touch "a" so "b" becomes LRU
        assert c.get("a") == 1
        c.put("d", 4)  # evicts "b"
        assert c.get("b") is None
        assert c.get("a") == 1
        assert c.get("c") == 3
        assert c.get("d") == 4

    def test_delete_and_clear(self) -> None:
        c = LRUCache(maxsize=2)
        c.put("a", 1)
        c.put("b", 2)
        c.delete("a")
        assert "a" not in c
        c.clear()
        assert len(c) == 0

    def test_update_moves_to_mru(self) -> None:
        c = LRUCache(maxsize=2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("a", 10)  # refresh "a" -> evicts "b" on next insert
        c.put("c", 3)
        assert c.get("a") == 10
        assert c.get("b") is None


# ── CacheManager (Redis-less) ───────────────────────────────────────────


class FakeRedis:
    """Minimal in-memory stand-in for redis.asyncio (get/setex/delete/ping)."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: bytes) -> None:
        self.store[key] = value
        self.ttls[key] = ttl

    async def delete(self, *keys: str) -> int:
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                self.ttls.pop(k, None)
                n += 1
        return n


def make_manager() -> CacheManager:
    return CacheManager(redis_url="redis://localhost:6379/0", max_memory_items=3, default_ttl=60, namespace="test")


class TestCacheManagerL1Only:
    def _make_isolated(self, monkeypatch: pytest.MonkeyPatch) -> CacheManager:
        cm = make_manager()

        async def fake_ensure_redis() -> bool:
            cm._redis = None
            cm._redis_connected = False
            return False

        monkeypatch.setattr(cm, "_ensure_redis", fake_ensure_redis)
        return cm

    async def test_computes_and_caches_in_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cm = self._make_isolated(monkeypatch)
        calls = 0

        async def compute() -> int:
            nonlocal calls
            calls += 1
            return 42

        assert await cm.get_or_compute("k", func=compute) == 42
        assert await cm.get_or_compute("k", func=compute) == 42
        assert calls == 1  # second hit came from L1

    async def test_sync_func_supported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cm = self._make_isolated(monkeypatch)

        def compute() -> str:
            return "value"

        assert await cm.get_or_compute("k", func=compute) == "value"
        assert await cm.get_or_compute("k", func=compute) == "value"

    async def test_memory_lru_eviction(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cm = self._make_isolated(monkeypatch)  # max_memory_items=3
        await cm.get_or_compute("a", func=lambda: 1)
        await cm.get_or_compute("b", func=lambda: 2)
        await cm.get_or_compute("c", func=lambda: 3)
        await cm.get_or_compute("a", func=lambda: 1)  # refresh a
        await cm.get_or_compute("d", func=lambda: 4)  # evicts b
        assert await cm.get("b") is None
        assert await cm.get("a") == 1

    async def test_invalidate_removes_from_all_layers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cm = self._make_isolated(monkeypatch)
        await cm.get_or_compute("k", func=lambda: 5)
        assert await cm.get("k") == 5
        await cm.invalidate("k")
        assert await cm.get("k") is None

    async def test_clear_all_empties_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cm = self._make_isolated(monkeypatch)
        await cm.get_or_compute("a", func=lambda: 1)
        await cm.get_or_compute("b", func=lambda: 2)
        await cm.clear_all()
        assert await cm.get("a") is None
        assert await cm.get("b") is None
        assert cm.memory_size == 0

    async def test_no_func_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cm = self._make_isolated(monkeypatch)
        assert await cm.get("missing") is None


class TestCacheManagerWithRedis:
    async def test_redis_is_written_and_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeRedis()
        cm = make_manager()

        async def fake_ensure_redis() -> bool:
            cm._redis = fake
            cm._redis_connected = True
            return True

        monkeypatch.setattr(cm, "_ensure_redis", fake_ensure_redis)

        await cm.get_or_compute("k", func=lambda: {"x": 1})
        assert "test:k" in fake.store  # persisted to L2

        # New manager instance with same fake redis -> L2 hit (no L1 warmup)
        cm2 = make_manager()
        async def fake_ensure_redis2() -> bool:
            cm2._redis = fake
            cm2._redis_connected = True
            return True

        monkeypatch.setattr(cm2, "_ensure_redis", fake_ensure_redis2)
        value = await cm2.get_or_compute("k", func=lambda: "SHOULD_NOT_RUN")
        assert value == {"x": 1}

    async def test_invalidate_removes_from_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeRedis()
        cm = make_manager()

        async def fake_ensure_redis() -> bool:
            cm._redis = fake
            cm._redis_connected = True
            return True

        monkeypatch.setattr(cm, "_ensure_redis", fake_ensure_redis)
        await cm.get_or_compute("k", func=lambda: 1)
        await cm.invalidate("k")
        assert "test:k" not in fake.store

    async def test_clear_all_flushes_redis_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeRedis()
        cm = make_manager()

        async def fake_ensure_redis() -> bool:
            cm._redis = fake
            cm._redis_connected = True
            return True

        monkeypatch.setattr(cm, "_ensure_redis", fake_ensure_redis)
        await cm.get_or_compute("a", func=lambda: 1)
        await cm.get_or_compute("b", func=lambda: 2)
        await cm.clear_all()
        assert "test:a" not in fake.store
        assert "test:b" not in fake.store


class TestCacheManagerRedisDown:
    async def test_falls_back_to_l1_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cm = make_manager()

        async def fake_ensure_redis() -> bool:
            cm._redis = None
            cm._redis_connected = False
            return False

        monkeypatch.setattr(cm, "_ensure_redis", fake_ensure_redis)
        calls = 0

        async def compute() -> int:
            nonlocal calls
            calls += 1
            return 7

        assert await cm.get_or_compute("k", func=compute) == 7
        assert await cm.get_or_compute("k", func=compute) == 7
        assert calls == 1  # L1 still caches even without Redis

    async def test_set_without_redis_does_not_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cm = make_manager()

        async def fake_ensure_redis() -> bool:
            cm._redis = None
            cm._redis_connected = False
            return False

        monkeypatch.setattr(cm, "_ensure_redis", fake_ensure_redis)
        await cm.set("k", 1)  # must not raise
        assert await cm.get("k") == 1

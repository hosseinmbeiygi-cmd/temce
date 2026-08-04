"""Tests for the _CacheManager class in services/screener_service.py.

Covers:
  1. Basic get/put operations
  2. TTL expiry (entries expire after ttl seconds)
  3. Hard eviction (oldest entry evicted when max_size exceeded)
  4. LRU refresh (accessing entry refreshes its timestamp and position)
  5. Periodic purge (expired entries cleaned on put when purge_interval elapsed)
  6. Stats tracking (hits, misses, evictions, hit_rate_pct)
  7. Clear method
  8. Size property
  9. Update existing key (put on existing key refreshes value)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.screener_service import _CacheManager

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def small_cache():
    """A tiny cache (max_size=5, ttl=2s, purge_interval=0.1s) for fast tests."""
    return _CacheManager(max_size=5, ttl=2.0, purge_interval=0.1)


@pytest.fixture
def fast_purge_cache():
    """Cache with very short purge interval for testing periodic purge."""
    return _CacheManager(max_size=10, ttl=1.0, purge_interval=0.05)


# ===========================================================================
# 1. Basic get/put
# ===========================================================================


class TestBasicOperations:
    def test_put_and_get(self, small_cache):
        small_cache.put("a", 42)
        assert small_cache.get("a") == 42

    def test_get_missing_key_returns_none(self, small_cache):
        assert small_cache.get("nonexistent") is None

    def test_put_multiple_keys(self, small_cache):
        small_cache.put("a", 1)
        small_cache.put("b", 2)
        small_cache.put("c", 3)
        assert small_cache.get("a") == 1
        assert small_cache.get("b") == 2
        assert small_cache.get("c") == 3

    def test_update_existing_key(self, small_cache):
        small_cache.put("a", 1)
        small_cache.put("a", 99)
        assert small_cache.get("a") == 99
        assert small_cache.size == 1

    def test_put_with_complex_value(self, small_cache):
        data = {"key": [1, 2, 3]}
        small_cache.put("complex", data)
        assert small_cache.get("complex") == data


# ===========================================================================
# 2. TTL expiry
# ===========================================================================


class TestTTLExpiry:
    def test_entry_expires_after_ttl(self, fast_purge_cache):
        fast_purge_cache.put("a", 42)
        # Immediately should be available
        assert fast_purge_cache.get("a") == 42

        # Wait for TTL to expire (ttl=1.0)
        time.sleep(1.1)
        assert fast_purge_cache.get("a") is None

    def test_expired_entry_counted_as_miss(self, fast_purge_cache):
        fast_purge_cache.put("a", 42)
        time.sleep(1.1)
        fast_purge_cache.get("a")
        stats = fast_purge_cache.stats
        assert stats["misses"] >= 1
        assert stats["hits"] == 0

    def test_non_expired_entry_still_available(self, fast_purge_cache):
        fast_purge_cache.put("a", 42)
        fast_purge_cache.put("b", 99)
        time.sleep(0.3)  # well within 1s TTL
        assert fast_purge_cache.get("a") == 42
        assert fast_purge_cache.get("b") == 99

    def test_different_keys_expire_independently(self, fast_purge_cache):
        fast_purge_cache.put("early", "val1")
        time.sleep(0.6)
        fast_purge_cache.put("late", "val2")
        time.sleep(0.5)  # total 1.1s for early, 0.5s for late

        assert fast_purge_cache.get("early") is None  # expired
        assert fast_purge_cache.get("late") == "val2"  # still fresh


# ===========================================================================
# 3. Hard eviction
# ===========================================================================


class TestHardEviction:
    def test_evicts_oldest_when_full(self, small_cache):
        """max_size=5, inserting 6th item should evict the oldest."""
        for i in range(5):
            small_cache.put(f"k{i}", i)
        assert small_cache.size == 5

        small_cache.put("k_new", 999)
        assert small_cache.size == 5
        # The oldest key (k0) should have been evicted
        assert small_cache.get("k0") is None
        assert small_cache.get("k_new") == 999

    def test_eviction_counted_in_stats(self, small_cache):
        for i in range(5):
            small_cache.put(f"k{i}", i)
        small_cache.put("overflow", 999)
        assert small_cache.stats["evictions"] == 1

    def test_multiple_overflows(self, small_cache):
        for i in range(10):
            small_cache.put(f"k{i}", i)
        # After 10 inserts with max_size=5, we should have evicted 5
        assert small_cache.size == 5
        assert small_cache.stats["evictions"] == 5


# ===========================================================================
# 4. LRU refresh
# ===========================================================================


class TestLRURefresh:
    def test_get_refreshes_lru_position(self, small_cache):
        """Accessing an entry moves it to the end (most-recently used)."""
        for i in range(5):
            small_cache.put(f"k{i}", i)
        # Access k0 to refresh it
        small_cache.get("k0")
        # Now insert a 6th item — should evict k1 (oldest), not k0
        small_cache.put("k_new", 999)
        assert small_cache.get("k0") == 0  # k0 was refreshed, should survive
        assert small_cache.get("k1") is None  # k1 should be evicted

    def test_put_refreshes_lru_position(self, small_cache):
        """Updating an existing key also refreshes its LRU position."""
        for i in range(5):
            small_cache.put(f"k{i}", i)
        # Update k0 to refresh it
        small_cache.put("k0", 42)
        small_cache.put("k_new", 999)
        assert small_cache.get("k0") == 42
        assert small_cache.get("k1") is None  # k1 evicted

    def test_lru_order_preserved(self, small_cache):
        """Insert a, b, c, d, e. Access a. Insert f should evict b."""
        for ch in "abcde":
            small_cache.put(ch, ord(ch))
        small_cache.get("a")  # refresh a
        small_cache.put("f", ord("f"))
        # a should survive, b should be evicted
        assert small_cache.get("a") is not None
        assert small_cache.get("b") is None
        assert small_cache.get("c") is not None


# ===========================================================================
# 5. Periodic purge
# ===========================================================================


class TestPeriodicPurge:
    def test_expired_entries_purged_on_put(self, fast_purge_cache):
        """Expired entries should be purged when purge_interval has elapsed."""
        fast_purge_cache.put("a", 1)
        fast_purge_cache.put("b", 2)
        assert fast_purge_cache.size == 2

        # Wait for TTL + purge interval
        time.sleep(1.2)

        # Next put should trigger purge
        fast_purge_cache.put("c", 3)
        # a and b should have been purged
        assert fast_purge_cache.size == 1
        assert fast_purge_cache.get("c") == 3

    def test_purge_returns_count(self, fast_purge_cache):
        """_purge_expired returns the number of entries removed."""
        fast_purge_cache.put("a", 1)
        fast_purge_cache.put("b", 2)
        time.sleep(1.1)
        count = fast_purge_cache._purge_expired()
        assert count == 2
        assert fast_purge_cache.size == 0

    def test_purge_on_fresh_cache_removes_nothing(self, small_cache):
        count = small_cache._purge_expired()
        assert count == 0


# ===========================================================================
# 6. Stats tracking
# ===========================================================================


class TestStats:
    def test_initial_stats(self):
        cache = _CacheManager(max_size=10, ttl=5.0)
        stats = cache.stats
        assert stats["size"] == 0
        assert stats["max_size"] == 10
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["evictions"] == 0
        assert stats["hit_rate_pct"] == 0.0
        assert stats["ttl_seconds"] == 5.0

    def test_hits_and_misses(self, small_cache):
        small_cache.put("a", 1)
        small_cache.get("a")     # hit
        small_cache.get("a")     # hit
        small_cache.get("miss")  # miss
        stats = small_cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1

    def test_hit_rate_calculation(self, small_cache):
        small_cache.put("a", 1)
        for _ in range(3):
            small_cache.get("a")  # 3 hits
        small_cache.get("x")  # 1 miss
        stats = small_cache.stats
        assert stats["hit_rate_pct"] == 75.0

    def test_hit_rate_zero_when_no_accesses(self):
        cache = _CacheManager(max_size=5, ttl=1.0)
        assert cache.stats["hit_rate_pct"] == 0.0

    def test_expired_get_counts_as_miss(self, fast_purge_cache):
        fast_purge_cache.put("a", 1)
        time.sleep(1.1)
        fast_purge_cache.get("a")  # expired → miss
        stats = fast_purge_cache.stats
        assert stats["misses"] == 1
        assert stats["hits"] == 0


# ===========================================================================
# 7. Clear
# ===========================================================================


class TestClear:
    def test_clear_removes_all_entries(self, small_cache):
        for i in range(5):
            small_cache.put(f"k{i}", i)
        assert small_cache.size == 5
        small_cache.clear()
        assert small_cache.size == 0

    def test_clear_does_not_affect_stats(self, small_cache):
        small_cache.put("a", 1)
        small_cache.get("a")
        small_cache.clear()
        stats = small_cache.stats
        assert stats["hits"] == 1  # stats preserved
        assert stats["size"] == 0  # entries removed


# ===========================================================================
# 8. Size property
# ===========================================================================


class TestSize:
    def test_size_empty(self):
        cache = _CacheManager(max_size=5, ttl=1.0)
        assert cache.size == 0

    def test_size_grows(self, small_cache):
        small_cache.put("a", 1)
        assert small_cache.size == 1
        small_cache.put("b", 2)
        assert small_cache.size == 2

    def test_size_capped_by_max_size(self, small_cache):
        for i in range(10):
            small_cache.put(f"k{i}", i)
        assert small_cache.size == 5  # max_size=5


# ===========================================================================
# 9. Update existing key
# ===========================================================================


class TestUpdateExistingKey:
    def test_update_preserves_size(self, small_cache):
        small_cache.put("a", 1)
        small_cache.put("a", 2)
        assert small_cache.size == 1

    def test_update_returns_new_value(self, small_cache):
        small_cache.put("a", "old")
        small_cache.put("a", "new")
        assert small_cache.get("a") == "new"

    def test_update_refreshes_ttl(self, small_cache):
        small_cache.put("a", 1)
        time.sleep(0.6)
        small_cache.put("a", 2)  # refresh
        time.sleep(0.6)  # total 1.2s from original, but 0.6s from update
        assert small_cache.get("a") == 2  # should survive

    def test_update_does_not_trigger_eviction(self, small_cache):
        """Updating an existing key should NOT count as an eviction."""
        for i in range(5):
            small_cache.put(f"k{i}", i)
        small_cache.put("k0", 999)  # update, not new
        assert small_cache.stats["evictions"] == 0
        assert small_cache.size == 5

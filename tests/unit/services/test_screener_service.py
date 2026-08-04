"""Unit tests for ScreenerService — cache, helpers, and pipeline.

Covers:
  - _CacheManager: TTL expiry, hard eviction, LRU refresh, stats, clear
  - _parse_numeric: Persian/English formatting, edge cases
  - _is_numeric: type checking
  - _get_filter_value: field mapping and extraction
  - ScreenedSymbol: dataclass defaults
  - build_real_quote_from_snapshot: snapshot → quote dict
  - build_real_history_from_rows: DB rows → history list
"""

from __future__ import annotations

import time

from services.screener_service import (
    ScreenedSymbol,
    _CacheManager,
    _get_filter_value,
    _is_numeric,
    _parse_numeric,
    build_real_history_from_rows,
    build_real_quote_from_snapshot,
)

# ════════════════════════════════════════════════════════════════
# 1. _CacheManager
# ════════════════════════════════════════════════════════════════


class TestCacheManager:
    def test_put_and_get(self):
        c = _CacheManager(max_size=10, ttl=60.0)
        c.put("k1", "v1")
        assert c.get("k1") == "v1"

    def test_get_missing_key(self):
        c = _CacheManager(max_size=10, ttl=60.0)
        assert c.get("nonexistent") is None

    def test_ttl_expiry(self):
        c = _CacheManager(max_size=10, ttl=0.05)
        c.put("k1", "v1")
        time.sleep(0.1)
        assert c.get("k1") is None

    def test_lru_refresh(self):
        """Accessing a key should refresh its position."""
        c = _CacheManager(max_size=3, ttl=60.0, purge_interval=0)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        # Access 'a' to refresh it (move to end)
        c.get("a")
        # Add 'd' → should evict 'b' (oldest unaccessed)
        c.put("d", 4)
        assert c.get("a") == 1
        assert c.get("b") is None  # evicted
        assert c.get("d") == 4

    def test_hard_eviction(self):
        c = _CacheManager(max_size=2, ttl=60.0, purge_interval=0)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)  # evicts 'a'
        assert c.get("a") is None
        assert c.get("b") == 2
        assert c.get("c") == 3

    def test_update_existing_key(self):
        c = _CacheManager(max_size=10, ttl=60.0)
        c.put("k1", "old")
        c.put("k1", "new")
        assert c.get("k1") == "new"
        assert c.size == 1

    def test_periodic_purge(self):
        """Expired entries should be purged on next put after purge_interval."""
        c = _CacheManager(max_size=10, ttl=0.05, purge_interval=0.01)
        c.put("k1", "v1")
        time.sleep(0.1)
        c.put("k2", "v2")  # triggers purge
        assert c.get("k1") is None  # expired and purged
        assert c.get("k2") == "v2"

    def test_clear(self):
        c = _CacheManager(max_size=10, ttl=60.0)
        c.put("a", 1)
        c.put("b", 2)
        c.clear()
        assert c.size == 0
        assert c.get("a") is None

    def test_size_property(self):
        c = _CacheManager(max_size=10, ttl=60.0)
        assert c.size == 0
        c.put("a", 1)
        assert c.size == 1
        c.put("b", 2)
        assert c.size == 2

    def test_stats(self):
        c = _CacheManager(max_size=10, ttl=60.0)
        c.put("a", 1)
        c.get("a")  # hit
        c.get("b")  # miss
        stats = c.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_pct"] == 50.0
        assert stats["size"] == 1

    def test_stats_empty(self):
        c = _CacheManager(max_size=10, ttl=60.0)
        stats = c.stats
        assert stats["hit_rate_pct"] == 0.0


# ════════════════════════════════════════════════════════════════
# 2. _parse_numeric
# ════════════════════════════════════════════════════════════════


class TestParseNumeric:
    def test_none(self):
        assert _parse_numeric(None) is None

    def test_int(self):
        assert _parse_numeric(42) == 42.0

    def test_float(self):
        assert _parse_numeric(3.14) == 3.14

    def test_string_number(self):
        assert _parse_numeric("123.45") == 123.45

    def test_string_with_commas(self):
        assert _parse_numeric("1,234,567") == 1234567.0

    def test_string_with_persian_separator(self):
        # Arabic comma (٬) is stripped, Persian digits (۱۲۳۴) happen to work
        # because Python float() accepts some Unicode digit equivalents
        result = _parse_numeric("1٬234")
        assert result == 1234.0

    def test_string_with_percent(self):
        assert _parse_numeric("12.5%") == 12.5

    def test_negative_string(self):
        assert _parse_numeric("-5.5") == -5.5

    def test_string_with_plus(self):
        assert _parse_numeric("+10") == 10.0

    def test_non_numeric_string(self):
        assert _parse_numeric("hello") is None

    def test_empty_string(self):
        assert _parse_numeric("") is None


class TestIsNumeric:
    def test_numeric(self):
        assert _is_numeric(42) is True
        assert _is_numeric("123") is True
        assert _is_numeric(None) is False
        assert _is_numeric("abc") is False


# ════════════════════════════════════════════════════════════════
# 3. _get_filter_value
# ════════════════════════════════════════════════════════════════


class TestGetFilterValue:
    def test_direct_attribute(self):
        item = ScreenedSymbol(
            symbol="test", name="Test", market="tse", industry="metal",
            last_price=100.0, change_pct=2.5, volume=1000, value=100000,
        )
        assert _get_filter_value(item, {}, "smc_score") == 0.0
        assert _get_filter_value(item, {}, "last_price") == 100.0
        assert _get_filter_value(item, {}, "volume") == 1000.0

    def test_from_watch(self):
        item = ScreenedSymbol(
            symbol="test", name="Test", market="tse", industry="metal",
            last_price=100.0, change_pct=2.5, volume=1000, value=100000,
        )
        watch = {"pe_ratio": 15.5, "eps": 2.0}
        assert _get_filter_value(item, watch, "pe_ratio") == 15.5

    def test_field_alias(self):
        item = ScreenedSymbol(
            symbol="test", name="Test", market="tse", industry="metal",
            last_price=100.0, change_pct=2.5, volume=1000, value=100000,
        )
        # "price" is an alias for "last_price"
        assert _get_filter_value(item, {}, "price") == 100.0
        assert _get_filter_value(item, {}, "close") == 100.0

    def test_empty_field(self):
        item = ScreenedSymbol(
            symbol="test", name="Test", market="tse", industry="metal",
            last_price=100.0, change_pct=2.5, volume=1000, value=100000,
        )
        assert _get_filter_value(item, {}, "") is None

    def test_from_details(self):
        item = ScreenedSymbol(
            symbol="test", name="Test", market="tse", industry="metal",
            last_price=100.0, change_pct=2.5, volume=1000, value=100000,
            details={"rsi": 65.5},
        )
        assert _get_filter_value(item, {}, "rsi") == 65.5


# ════════════════════════════════════════════════════════════════
# 4. ScreenedSymbol dataclass
# ════════════════════════════════════════════════════════════════


class TestScreenedSymbol:
    def test_defaults(self):
        s = ScreenedSymbol(
            symbol="تست", name="Test", market="tse", industry="metal",
            last_price=100.0, change_pct=2.0, volume=1000, value=100000,
        )
        assert s.smc_score == 0.0
        assert s.phase == "neutral"
        assert s.rank == 0
        assert s.details == {}

    def test_custom_values(self):
        s = ScreenedSymbol(
            symbol="فولاد", name="Foolad", market="tse", industry="metal",
            last_price=500.0, change_pct=3.5, volume=50000, value=25000000,
            smc_score=0.85, phase="accumulation", rank=1,
        )
        assert s.smc_score == 0.85
        assert s.phase == "accumulation"
        assert s.rank == 1


# ════════════════════════════════════════════════════════════════
# 5. build_real_quote_from_snapshot
# ════════════════════════════════════════════════════════════════


class TestBuildRealQuoteFromSnapshot:
    def test_basic(self):
        snap = {
            "symbol": "فولاد",
            "price_close": 500, "price_first": 490, "price_max": 510,
            "price_min": 480, "price_last": 505, "price_last_change": 10,
            "price_last_change_pct": 2.0, "trade_volume": 100000,
            "trade_value": 50000000, "trade_count": 500,
            "buy_real_volume": 60000, "buy_real_count": 300,
            "sell_real_volume": 40000, "sell_real_count": 200,
            "buy_legal_volume": 0, "buy_legal_count": 0,
            "sell_legal_volume": 0, "sell_legal_count": 0,
        }
        q = build_real_quote_from_snapshot(snap)
        assert q["symbol"] == "فولاد"
        assert q["price_open"] == 490
        assert q["price_close"] == 500
        assert q["price_high"] == 510
        assert q["price_low"] == 480
        assert q["volume"] == 100000
        assert q["value"] == 50000000

    def test_missing_fields(self):
        q = build_real_quote_from_snapshot({"symbol": "test"})
        assert q["price_open"] == 0.0
        assert q["volume"] == 0

    def test_real_buy_value_computed(self):
        snap = {
            "price_close": 100, "price_first": 100, "price_max": 100,
            "price_min": 100, "trade_volume": 1000,
            "buy_real_volume": 500, "buy_real_count": 10,
        }
        q = build_real_quote_from_snapshot(snap)
        assert q["real_buy_value"] > 0


# ════════════════════════════════════════════════════════════════
# 6. build_real_history_from_rows
# ════════════════════════════════════════════════════════════════


class TestBuildRealHistoryFromRows:
    def test_basic(self):
        rows = [
            {"date": "2024-01-02", "price_close": 110, "price_first": 100, "price_max": 115, "price_min": 95, "trade_volume": 1000, "trade_value": 110000},
            {"date": "2024-01-01", "price_close": 100, "price_first": 90, "price_max": 105, "price_min": 85, "trade_volume": 800, "trade_value": 80000},
        ]
        result = build_real_history_from_rows(rows)
        assert len(result) == 2
        # Should be sorted oldest first
        assert result[0]["date"] == "2024-01-01"
        assert result[1]["date"] == "2024-01-02"

    def test_empty(self):
        assert build_real_history_from_rows([]) == []

    def test_with_real_legal_data(self):
        daily = [{"date": "2024-01-01", "price_close": 100, "trade_volume": 1000, "trade_value": 100000}]
        rl = [{"date": "2024-01-01", "buy_real_volume": 500, "sell_real_volume": 300, "buy_real_count": 10, "sell_real_count": 5, "buy_legal_volume": 200, "sell_legal_volume": 100, "buy_legal_count": 3, "sell_legal_count": 2}]
        result = build_real_history_from_rows(daily, rl)
        assert len(result) == 1
        assert result[0]["real_buy_value"] > 0

    def test_missing_real_legal(self):
        daily = [{"date": "2024-01-01", "price_close": 100, "trade_volume": 1000, "trade_value": 100000}]
        result = build_real_history_from_rows(daily)
        assert len(result) == 1

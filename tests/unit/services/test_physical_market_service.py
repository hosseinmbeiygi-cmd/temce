"""Service tests for the cached physical-market reports.

The DB loaders are stubbed, so these tests exercise cache behavior, config
loading and response shaping without touching a real database or Redis.
"""

from __future__ import annotations

import pytest

from services.gold import physical_market_service as service


class FakeCache:
    def __init__(self, initial: dict | None = None) -> None:
        self.store = dict(initial or {})
        self.set_calls: list[tuple[str, object, int | None]] = []

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value, ttl: int | None = None) -> None:
        self.set_calls.append((key, value, ttl))
        self.store[key] = value


def _install_cache(monkeypatch: pytest.MonkeyPatch, cache: FakeCache) -> None:
    monkeypatch.setattr(service, "get_cache", lambda: cache)


async def test_coin_report_cache_hit_skips_loaders(monkeypatch) -> None:
    cached = {"available": True, "coins": {"emami": {"bubble_pct": 1.0}}}
    cache = FakeCache({"gold:analytics:coins:200": cached})
    _install_cache(monkeypatch, cache)

    async def boom(session):
        raise AssertionError("loader must not run on a cache hit")

    monkeypatch.setattr(service, "_load_coin_market_state", boom)

    assert await service.get_coin_bubble_report(object()) is cached
    assert cache.set_calls == []


async def test_coin_report_cache_miss_computes_and_sets(monkeypatch) -> None:
    cache = FakeCache()
    _install_cache(monkeypatch, cache)

    async def state(session):
        return {
            "available": True,
            "xau_usd": 2_000.0,
            "usd_irr": 1_000_000.0,
            "coin_prices": {"IR_COIN_EMAMI": 500_000_000.0},
            "missing_symbols": ["IR_COIN_HALF"],
        }

    async def history(session, symbols, limit):
        assert symbols == ["IR_COIN_EMAMI"]
        assert limit == 50
        return {"IR_COIN_EMAMI": [10.0, 20.0, 30.0]}

    monkeypatch.setattr(service, "_load_coin_market_state", state)
    monkeypatch.setattr(service, "_load_bubble_history", history)

    result = await service.get_coin_bubble_report(object(), history_limit=50)

    assert result["available"] is True
    assert result["history_limit"] == 50
    assert result["missing_symbols"] == ["IR_COIN_HALF"]
    # STEP 6-FIX-2: intrinsic includes the unified 80,000 IRR emami fee.
    assert result["coins"]["emami"]["bubble_abs_irr"] == pytest.approx(
        500_000_000.0 - (470_714_710.7878512 + 80_000.0)
    )
    assert result["coins"]["emami"]["history_sample_size"] == 3

    assert len(cache.set_calls) == 1
    key, value, ttl = cache.set_calls[0]
    assert key == "gold:analytics:coins:50"
    assert value is result
    assert ttl == service.CACHE_TTL_SECONDS


async def test_coin_report_missing_reference_is_not_fabricated(monkeypatch) -> None:
    cache = FakeCache()
    _install_cache(monkeypatch, cache)

    async def state(session):
        return {
            "available": False,
            "reason": "XAUUSD price unavailable",
            "missing_symbols": ["XAUUSD"],
        }

    monkeypatch.setattr(service, "_load_coin_market_state", state)

    result = await service.get_coin_bubble_report(object())

    assert result["available"] is False
    assert result["coins"] == {}
    assert result["reason"] == "XAUUSD price unavailable"
    assert result["missing_symbols"] == ["XAUUSD"]


async def test_arbitrage_report_uses_configured_limits(monkeypatch) -> None:
    cache = FakeCache()
    _install_cache(monkeypatch, cache)

    async def state(session):
        return {
            "available": True,
            "cert_price_per_gram_irr": 7_000_000.0,
            "melted_gram18_price_irr": 5_000_000.0,
            "cert_contract_code": "CERT-1",
            "cert_contract_size": 1,
            "cert_contract_size_unit": "gram",
            "cert_price_last_irr": 7_000_000.0,
            "source": "brsapi_ime_certificates+brsapi_gold_coin_prices",
        }

    monkeypatch.setattr(service, "_load_arbitrage_state", state)
    monkeypatch.setattr(
        service,
        "load_ime_config",
        lambda: {
            "physical_market": {
                "ime_certificate_position_limit_grams": 0.5,
                "ime_certificate_ownership_limit_grams": 2.0,
            }
        },
    )

    result = await service.get_ime_arbitrage_report(object(), quantity_grams=1.0)

    assert result["available"] is True
    assert result["action"] == "BUY_MELTED_SELL_IME_CERT"
    assert result["limit_check"]["status"] == "breach"
    assert result["limit_check"]["violations"] == ["position"]
    assert cache.set_calls[0][2] == service.CACHE_TTL_SECONDS


async def test_arbitrage_report_reports_unconfigured_limits(monkeypatch) -> None:
    cache = FakeCache()
    _install_cache(monkeypatch, cache)

    async def state(session):
        return {
            "available": True,
            "cert_price_per_gram_irr": 7_000_000.0,
            "melted_gram18_price_irr": 5_000_000.0,
            "cert_contract_code": "CERT-1",
            "cert_contract_size": 1,
            "cert_contract_size_unit": "gram",
            "cert_price_last_irr": 7_000_000.0,
            "source": "test",
        }

    monkeypatch.setattr(service, "_load_arbitrage_state", state)
    monkeypatch.setattr(service, "load_ime_config", lambda: {"physical_market": {}})

    result = await service.get_ime_arbitrage_report(object())

    assert result["limit_check"]["status"] == "not_configured"
    assert result["limit_check"]["ok"] is None


async def test_arbitrage_report_is_honest_when_certificate_data_is_missing(monkeypatch) -> None:
    cache = FakeCache()
    _install_cache(monkeypatch, cache)

    async def state(session):
        return {
            "available": False,
            "reason": "IME certificate contract size unit is not gram-compatible",
            "missing_symbols": ["IME_CERTIFICATE"],
        }

    monkeypatch.setattr(service, "_load_arbitrage_state", state)

    result = await service.get_ime_arbitrage_report(object())

    assert result["available"] is False
    assert "gram-compatible" in result["reason"]
    assert "action" not in result


async def test_aed_history_cache_hit_skips_loader(monkeypatch) -> None:
    cached = {"available": True, "series": [], "current": {"alert": False}}
    cache = FakeCache({"gold:analytics:aed-history:200": cached})
    _install_cache(monkeypatch, cache)

    async def boom(session, limit):
        raise AssertionError("loader must not run on a cache hit")

    monkeypatch.setattr(service, "_load_aed_history", boom)

    assert await service.get_aed_history_report(object()) is cached


async def test_aed_history_computes_zscore_and_alert(monkeypatch) -> None:
    cache = FakeCache()
    _install_cache(monkeypatch, cache)

    async def rows(session, limit):
        assert limit == 10
        return [
            {"snapshot_at": "t1", "usd_irt": 3_600_000.0, "aed_irt": 1_000_000.0},
            {"snapshot_at": "t2", "usd_irt": 3_700_000.0, "aed_irt": 1_000_000.0},
            {"snapshot_at": "t3", "usd_irt": 3_800_000.0, "aed_irt": 1_000_000.0},
        ]

    monkeypatch.setattr(service, "_load_aed_history", rows)
    monkeypatch.setattr(
        service,
        "load_ime_config",
        lambda: {"physical_market": {"aed_hawala_alert_zscore": 1.0}},
    )

    result = await service.get_aed_history_report(object(), limit=10)

    assert result["available"] is True
    assert len(result["series"]) == 3
    assert result["current"]["alert"] is True
    assert result["current"]["z_score"] > 1.0
    assert result["alert_zscore"] == pytest.approx(1.0)
    assert cache.set_calls[0][2] == service.CACHE_TTL_SECONDS


async def test_aed_history_without_snapshots_is_not_fabricated(monkeypatch) -> None:
    cache = FakeCache()
    _install_cache(monkeypatch, cache)

    async def rows(session, limit):
        return []

    monkeypatch.setattr(service, "_load_aed_history", rows)
    monkeypatch.setattr(service, "load_ime_config", lambda: {"physical_market": {}})

    result = await service.get_aed_history_report(object())

    assert result["available"] is False
    assert result["series"] == []
    assert result["current"] is None

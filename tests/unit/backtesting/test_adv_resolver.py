"""Tests for F5 — per-symbol ADV resolution in the Broker.

Guards that:
  1. Slippage uses the symbol's real average daily volume (from
     ``OrderEvent.daily_volume`` or the AdvResolver) instead of a generic 1M
     default for every symbol.
  2. The AdvResolver caches DB lookups (TTL) and supports a sync cache-only
     peek for the deterministic backtest path.
  3. ``require_daily_volume`` gives the fail-fast development mode from the
     audit, and the default mode warns loudly instead of failing silently.
"""

from __future__ import annotations

import logging

import pytest

from backtesting.engine.adv import AdvResolver
from backtesting.engine.broker import Broker
from backtesting.types import OrderEvent


def _make_order(side: str = "buy", daily_volume: int | None = None) -> OrderEvent:
    return OrderEvent(
        instrument_id="SYM",
        side=side,
        quantity=1000,
        price=1000.0,
        order_type="MARKET",
        daily_volume=daily_volume,
    )


class TestAdvResolver:
    def test_peek_miss_returns_none(self) -> None:
        assert AdvResolver().peek("SYM") is None

    def test_set_and_peek(self) -> None:
        resolver = AdvResolver()
        resolver.set("SYM", 50_000)
        assert resolver.peek("SYM") == 50_000
        assert "SYM" in resolver.cached_symbols()

    def test_resolve_fetches_and_caches(self, monkeypatch) -> None:
        resolver = AdvResolver()
        calls = []

        async def fake_fetch(symbol: str) -> int | None:
            calls.append(symbol)
            return 50_000

        monkeypatch.setattr(resolver, "_fetch_from_db", fake_fetch)

        assert resolver.peek("SYM") is None
        assert asyncio_run(resolver.resolve("SYM")) == 50_000
        # Second resolve is served from cache — no extra DB call.
        assert asyncio_run(resolver.resolve("SYM")) == 50_000
        assert calls == ["SYM"]

    def test_resolve_returns_none_when_db_unavailable(self, monkeypatch) -> None:
        resolver = AdvResolver()

        async def fake_fetch(symbol: str) -> int | None:
            return None

        monkeypatch.setattr(resolver, "_fetch_from_db", fake_fetch)
        assert asyncio_run(resolver.resolve("SYM")) is None
        assert resolver.cached_symbols() == []

    def test_resolve_many(self, monkeypatch) -> None:
        resolver = AdvResolver()

        async def fake_fetch(symbol: str) -> int | None:
            return {"A": 10_000, "B": 20_000}.get(symbol)

        monkeypatch.setattr(resolver, "_fetch_from_db", fake_fetch)
        result = asyncio_run(resolver.resolve_many(["A", "B", "C"]))
        assert result == {"A": 10_000, "B": 20_000}

    def test_clear(self) -> None:
        resolver = AdvResolver()
        resolver.set("SYM", 10_000)
        resolver.clear()
        assert resolver.peek("SYM") is None


class TestBrokerAdvWiring:
    def test_order_daily_volume_drives_slippage(self) -> None:
        broker = Broker()
        low_adv_fill = broker.submit_order_sync(_make_order(daily_volume=50_000))
        high_adv_fill = broker.submit_order_sync(_make_order(daily_volume=5_000_000))

        assert low_adv_fill is not None and high_adv_fill is not None
        # IRAN_MARKET_COSTS: base 5 bps, impact 0.15. participation 2% -> 35 bps
        # (3.5/share * 1000); participation 0.02% -> 5.3 bps (0.53/share * 1000).
        assert low_adv_fill.slippage == pytest.approx(3500.0)
        assert high_adv_fill.slippage == pytest.approx(530.0)
        assert low_adv_fill.slippage > high_adv_fill.slippage

    def test_require_daily_volume_fails_fast_when_unknown(self) -> None:
        broker = Broker(require_daily_volume=True)  # no resolver, no order ADV
        with pytest.raises(ValueError, match="ADV unknown"):
            broker.submit_order_sync(_make_order())

    def test_require_daily_volume_passes_with_resolved_cache(self) -> None:
        resolver = AdvResolver()
        resolver.set("SYM", 50_000)
        broker = Broker(adv_resolver=resolver, require_daily_volume=True)
        fill = broker.submit_order_sync(_make_order())
        assert fill is not None
        assert fill.slippage == pytest.approx(3500.0)  # ADV 50k -> 35 bps

    def test_default_mode_warns_once_per_symbol(self, caplog) -> None:
        broker = Broker()  # no resolver, require=False -> warned fallback
        with caplog.at_level(logging.WARNING):
            broker.submit_order_sync(_make_order())
            broker.submit_order_sync(_make_order())
        fallback_warnings = [
            r for r in caplog.records if "No ADV resolved for 'SYM'" in r.getMessage()
        ]
        assert len(fallback_warnings) == 1

    def test_async_submit_order_auto_fetches_from_resolver(self, monkeypatch) -> None:
        resolver = AdvResolver()

        async def fake_fetch(symbol: str) -> int | None:
            return 50_000

        monkeypatch.setattr(resolver, "_fetch_from_db", fake_fetch)
        broker = Broker(adv_resolver=resolver)

        order = _make_order()  # no daily_volume
        fill = asyncio_run(broker.submit_order(order))

        assert fill is not None
        assert order.daily_volume == 50_000  # resolved and attached
        assert fill.slippage == pytest.approx(3500.0)  # ADV 50k -> 35 bps

    def test_async_resolve_attaches_only_when_found(self, monkeypatch) -> None:
        resolver = AdvResolver()

        async def fake_fetch(symbol: str) -> int | None:
            return None

        monkeypatch.setattr(resolver, "_fetch_from_db", fake_fetch)
        broker = Broker(adv_resolver=resolver)

        order = _make_order()
        fill = asyncio_run(broker.submit_order(order))
        assert fill is not None
        assert order.daily_volume is None  # nothing to attach; warned fallback path


def asyncio_run(coro):
    """Run a coroutine to completion (tests are otherwise sync here)."""
    import asyncio

    return asyncio.run(coro)

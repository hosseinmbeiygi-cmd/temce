"""Tests for services.market_watch_helper."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from services.market_watch_helper import (
    build_market_watch_from_snapshots,
    fetch_market_watch,
)


def _sample_snapshot(**overrides: Any) -> dict[str, Any]:
    return {
        "symbol": "FOLD",
        "name": "فولاد",
        "market": "BOURS",
        "sector": "فلزات",
        "price_last": 12345,
        "price_close": 12000,
        "price_last_change_pct": 2.5,
        "price_last_change": 345,
        "trade_volume": 1_500_000,
        "trade_value": 18_000_000_000,
        "price_max": 12400,
        "price_min": 12100,
        "pe_ratio": 5.6,
        "eps": 2200,
        **overrides,
    }


def test_build_market_watch_from_snapshots_basic() -> None:
    raw = [_sample_snapshot()]
    instruments, market_watch = build_market_watch_from_snapshots(raw)

    assert len(instruments) == 1
    assert len(market_watch) == 1

    instr = instruments[0]
    assert instr["symbol"] == "FOLD"
    assert instr["name"] == "فولاد"
    assert instr["market"] == "BOURS"
    assert instr["industry"] == "فلزات"

    watch = market_watch[0]
    assert watch["symbol"] == "FOLD"
    assert watch["last_price"] == 12345
    assert watch["volume"] == 1_500_000
    assert watch["high"] == 12400
    assert watch["low"] == 12100
    assert watch["pe_ratio"] == 5.6
    assert watch["_snapshot"] is raw[0]


def test_build_market_watch_from_snapshots_empty() -> None:
    instruments, market_watch = build_market_watch_from_snapshots([])
    assert instruments == []
    assert market_watch == []


def test_build_market_watch_from_snapshots_skips_missing_symbol() -> None:
    raw = [
        _sample_snapshot(symbol="FOO"),
        _sample_snapshot(symbol=""),
        _sample_snapshot(symbol=None),  # type: ignore[arg-type]
    ]
    instruments, market_watch = build_market_watch_from_snapshots(raw)
    assert [i["symbol"] for i in instruments] == ["FOO"]
    assert [w["symbol"] for w in market_watch] == ["FOO"]


def test_build_market_watch_from_snapshots_defaults() -> None:
    raw = [{"symbol": "X"}]
    instruments, market_watch = build_market_watch_from_snapshots(raw)
    assert instruments == [{"symbol": "X", "name": "X", "market": "", "industry": ""}]
    watch = market_watch[0]
    assert watch["last_price"] == 0
    assert watch["volume"] == 0
    assert watch["sector"] == ""
    assert watch["pe_ratio"] is None


def test_build_market_watch_from_snapshots_none() -> None:
    instruments, market_watch = build_market_watch_from_snapshots(None)
    assert instruments == []
    assert market_watch == []


async def test_fetch_market_watch_uses_fallback() -> None:
    service = AsyncMock()
    service.get_enriched_snapshots.side_effect = RuntimeError("BRS failure")
    service.get_latest_snapshots.return_value = [_sample_snapshot(symbol="ABC")]

    instruments, market_watch = await fetch_market_watch(service, limit=50)

    service.get_enriched_snapshots.assert_awaited_once_with(limit=50)
    service.get_latest_snapshots.assert_awaited_once_with(limit=50)
    assert [i["symbol"] for i in instruments] == ["ABC"]
    assert [w["symbol"] for w in market_watch] == ["ABC"]


async def test_fetch_market_watch_prefers_enriched() -> None:
    service = AsyncMock()
    service.get_enriched_snapshots.return_value = [_sample_snapshot(symbol="XYZ")]

    instruments, market_watch = await fetch_market_watch(service, limit=10)

    service.get_enriched_snapshots.assert_awaited_once_with(limit=10)
    service.get_latest_snapshots.assert_not_awaited()
    assert [i["symbol"] for i in instruments] == ["XYZ"]
    assert [w["symbol"] for w in market_watch] == ["XYZ"]


async def test_fetch_market_watch_raises_primary_on_total_failure() -> None:
    service = AsyncMock()
    service.get_enriched_snapshots.side_effect = RuntimeError("primary")
    service.get_latest_snapshots.side_effect = RuntimeError("fallback")

    with pytest.raises(RuntimeError, match="primary"):
        await fetch_market_watch(service, limit=10)

    service.get_enriched_snapshots.assert_awaited_once_with(limit=10)
    service.get_latest_snapshots.assert_awaited_once_with(limit=10)

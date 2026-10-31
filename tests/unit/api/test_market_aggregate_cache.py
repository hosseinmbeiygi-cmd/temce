"""Unit tests for the aggregate-cache behaviour of
apps/api/endpoints/market.py (/enriched-heatmap, /treemap,
/asset-allocation, /cashflow-by-sector).

All BrsApi/DB access is mocked; no live service or database is touched.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.endpoints import market as market_ep
from apps.api.endpoints.market import (
    invalidate_agg_cache,
    market_asset_allocation,
    market_cashflow_by_sector,
    market_enriched_heatmap,
    market_heatmap,
)


@pytest.fixture(autouse=True)
def _clear_agg_cache():
    """Each test starts with an empty aggregate cache."""
    market_ep._AGG_CACHE.clear()
    yield
    market_ep._AGG_CACHE.clear()


def _brsapi_with_snapshots(snapshots: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(get_latest_snapshots=AsyncMock(return_value=snapshots))


def _session_with_latest_fetched(value) -> SimpleNamespace:
    """MagicMock session whose execute(...).scalar_one_or_none() returns value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return SimpleNamespace(session=session)


SNAPSHOT = {
    "symbol": "فولاد",
    "name": "فولاد مبارکه",
    "market_value": 5e12,
    "fetched_at": "2026-10-28T09:30:00+00:00",
}


class TestAssetAllocation:
    def test_first_call_is_cache_miss_with_data_as_of(self) -> None:
        brsapi = _brsapi_with_snapshots([SNAPSHOT])
        resp = asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        assert resp.success is True
        assert resp.cache_hit is False
        assert resp.data_as_of == SNAPSHOT["fetched_at"]
        assert resp.data[0]["label"] == "سهام"

    def test_second_call_is_cache_hit(self) -> None:
        brsapi = _brsapi_with_snapshots([SNAPSHOT])
        first = asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        second = asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        assert second.success is True
        assert second.cache_hit is True
        assert second.data_as_of == first.data_as_of
        assert brsapi.get_latest_snapshots.call_count == 1

    def test_miss_after_ttl_expiry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        brsapi = _brsapi_with_snapshots([SNAPSHOT])
        fake_now = [1000.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])
        first = asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        assert first.cache_hit is False
        fake_now[0] = 1000.0 + market_ep._AGG_TTL + 1
        second = asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        assert second.cache_hit is False
        assert brsapi.get_latest_snapshots.call_count == 2

    def test_invalidate_forces_refetch(self) -> None:
        brsapi = _brsapi_with_snapshots([SNAPSHOT])
        asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        invalidate_agg_cache()
        asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        assert brsapi.get_latest_snapshots.call_count == 2

    def test_different_limit_does_not_share_cache_entry(self) -> None:
        brsapi = _brsapi_with_snapshots([SNAPSHOT])
        asyncio.run(market_asset_allocation(limit=100, brsapi=brsapi))
        asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        assert brsapi.get_latest_snapshots.call_count == 2


class TestHeatmap:
    def test_success_reports_snapshot_time_without_raw_query(self) -> None:
        snapshot = dict(SNAPSHOT, price_last_change_pct=1.5, trade_value=1e9, trade_volume=10, price_last=1000)
        brsapi = SimpleNamespace(get_latest_snapshots=AsyncMock(return_value=[snapshot]))

        resp = asyncio.run(market_heatmap(brsapi=brsapi))

        assert resp.success is True
        assert resp.data_as_of == SNAPSHOT["fetched_at"]
        assert resp.data[0]["symbol"] == "فولاد"

    def test_empty_snapshots_returns_success_false(self) -> None:
        brsapi = _session_with_latest_fetched(None)
        brsapi.get_latest_snapshots = AsyncMock(return_value=[])
        resp = asyncio.run(market_heatmap(brsapi=brsapi))
        assert resp.success is False
        assert resp.data == []
        assert resp.error is not None


class TestCashflowBySector:
    def test_different_limit_does_not_share_cache_entry(self) -> None:
        brsapi = _brsapi_with_snapshots([SNAPSHOT])
        asyncio.run(market_cashflow_by_sector(limit=50, brsapi=brsapi))
        asyncio.run(market_cashflow_by_sector(limit=500, brsapi=brsapi))
        assert brsapi.get_latest_snapshots.call_count == 2

    def test_error_path_returns_success_false(self) -> None:
        brsapi = SimpleNamespace(
            get_latest_snapshots=AsyncMock(side_effect=RuntimeError("db down"))
        )
        resp = asyncio.run(market_cashflow_by_sector(limit=500, brsapi=brsapi))
        assert resp.success is False
        assert resp.data == []
        assert resp.error is not None


class TestEnrichedHeatmap:
    def test_limit_is_part_of_cache_key(self) -> None:
        brsapi = SimpleNamespace(get_enriched_snapshots=AsyncMock(return_value=[SNAPSHOT]))
        asyncio.run(market_enriched_heatmap(limit=120, brsapi=brsapi))
        asyncio.run(market_enriched_heatmap(limit=500, brsapi=brsapi))
        assert brsapi.get_enriched_snapshots.call_count == 2

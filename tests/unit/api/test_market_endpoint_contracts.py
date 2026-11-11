"""HTTP-layer contracts for freshness/error reporting.

These tests run entirely against async functions with fake services: no
FastAPI server, PostgreSQL or BrsApi access is required.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from apps.api.endpoints import market_info
from apps.api.endpoints.market import (
    market_flow_summary,
    market_sparklines,
)
from apps.api.endpoints.market_dashboard import market_dashboard
from apps.api.endpoints.market_watch import market_watch as market_watch_endpoint
from core.result import Result


def test_market_watch_without_snapshots_is_not_success_empty() -> None:
    brsapi = SimpleNamespace(get_latest_snapshots=AsyncMock(return_value=[]))

    resp = asyncio.run(market_watch_endpoint(market="all", sector=None, brsapi=brsapi))

    assert resp.success is False
    assert resp.error is not None


def test_heatmap_empty_is_not_a_successful_empty() -> None:
    # Covered in test_market_aggregate_cache too; kept here as a contract.
    from apps.api.endpoints.market import market_heatmap

    brsapi = SimpleNamespace(get_latest_snapshots=AsyncMock(return_value=[]))
    resp = asyncio.run(market_heatmap(brsapi=brsapi))
    assert resp.success is False
    assert resp.error is not None


def test_flow_summary_without_snapshots_is_an_error() -> None:
    brsapi = SimpleNamespace(get_latest_snapshots=AsyncMock(return_value=[]))

    resp = asyncio.run(market_flow_summary(limit=500, brsapi=brsapi))

    assert resp.success is False
    assert resp.data == {}
    assert resp.error is not None


def test_flow_summary_success_carries_data_as_of() -> None:
    snapshot = {
        "price_last": 1000,
        "buy_real_volume": 10,
        "sell_real_volume": 4,
        "buy_legal_volume": 2,
        "sell_legal_volume": 1,
        "bid_volume_1": 0,
        "ask_volume_1": 0,
        "trade_volume": 10,
        "fetched_at": "2026-10-28T09:30:00+00:00",
    }
    brsapi = SimpleNamespace(get_latest_snapshots=AsyncMock(return_value=[snapshot]))

    resp = asyncio.run(market_flow_summary(limit=500, brsapi=brsapi))

    assert resp.success is True
    assert resp.data_as_of == snapshot["fetched_at"]


def test_sparklines_failure_keeps_dict_contract() -> None:
    service = SimpleNamespace(get_batch_sparklines=AsyncMock(return_value=Result.fail("db down")))

    resp = asyncio.run(market_sparklines(symbols="A,B", limit=30, service=service))

    assert resp.success is False
    assert resp.data == {}
    assert resp.error is not None


def test_market_info_industries_failure_is_not_success_empty() -> None:
    brsapi = SimpleNamespace(get_commodity_categories=AsyncMock(side_effect=RuntimeError("db down")))

    resp = asyncio.run(market_info.list_industries(brsapi=brsapi))

    assert resp.success is False
    assert resp.error is not None
    assert resp.data.items == []


def test_market_info_funds_keep_latest_fetched_at_not_last_row() -> None:
    funds = [
        {"symbol": "A", "name": "new", "price_last": 20, "fetched_at": "2026-10-28T09:10:00Z"},
        {"symbol": "A", "name": "old", "price_last": 10, "fetched_at": "2026-10-28T09:00:00Z"},
        {"symbol": "B", "name": "bee", "price_last": 5, "fetched_at": "2026-10-28T09:00:00Z"},
    ]
    brsapi = SimpleNamespace(get_ime_funds=AsyncMock(return_value=funds))

    resp = asyncio.run(market_info.list_funds(brsapi=brsapi))

    assert resp.success is True
    by_symbol = {row["symbol"]: row for row in resp.data.items}
    assert len(resp.data.items) == 2
    # The IME table carries no NAV: the last price must not be published as one,
    # otherwise every fund's premium/discount is structurally zero (ISSUE-128).
    assert by_symbol["A"]["price_last"] == 20
    assert by_symbol["A"]["nav"] is None
    assert by_symbol["A"]["nav_source"] is None
    assert resp.data.items[0]["symbol"] == "A"  # still sorted by price, not by NAV


def test_market_info_funds_failure_is_not_success_empty() -> None:
    brsapi = SimpleNamespace(get_ime_funds=AsyncMock(side_effect=RuntimeError("db down")))

    resp = asyncio.run(market_info.list_funds(brsapi=brsapi))

    assert resp.success is False
    assert resp.error is not None


class _FailingMarketService:
    async def get_overview(self):
        raise RuntimeError("overview down")

    async def get_index_values(self):
        return Result.fail("indices down")

    async def get_top_gainers(self, limit):
        raise RuntimeError("gainers down")

    async def get_top_losers(self, limit):
        raise RuntimeError("losers down")

    async def get_most_active(self, limit):
        raise RuntimeError("active down")


class _FailingBrsapi:
    async def get_enriched_snapshots(self, limit):
        raise RuntimeError("snapshots down")

    async def get_commodity_prices(self):
        raise RuntimeError("commodities down")

    async def get_crypto_prices(self):
        raise RuntimeError("crypto down")


def test_dashboard_all_sources_failed_is_success_false() -> None:
    resp = asyncio.run(
        market_dashboard(
            market_service=_FailingMarketService(),
            brsapi=_FailingBrsapi(),
        )
    )

    assert resp.success is False
    assert resp.error is not None
    assert "overview" in resp.data["errors"]


class _PartialMarketService(_FailingMarketService):
    async def get_overview(self):
        return Result.ok({"indices": []})


class _PartialBrsapi(_FailingBrsapi):
    pass


def test_dashboard_partial_failure_reports_sources() -> None:
    resp = asyncio.run(
        market_dashboard(
            market_service=_PartialMarketService(),
            brsapi=_PartialBrsapi(),
        )
    )

    assert resp.success is True
    assert "errors" in resp.data
    assert "commodities" in resp.data["errors"]
    assert resp.data["overview"] is not None


class _AllResultFailMarketService:
    async def get_overview(self):
        return Result.fail("overview failed")

    async def get_index_values(self):
        return Result.fail("indices failed")

    async def get_top_gainers(self, limit):
        return Result.fail("gainers failed")

    async def get_top_losers(self, limit):
        return Result.fail("losers failed")

    async def get_most_active(self, limit):
        return Result.fail("active failed")


def test_dashboard_result_failures_are_not_success() -> None:
    resp = asyncio.run(
        market_dashboard(
            market_service=_AllResultFailMarketService(),
            brsapi=_FailingBrsapi(),
        )
    )

    assert resp.success is False
    assert resp.error is not None
    assert set(resp.data["errors"]) >= {"overview", "gainers", "losers", "active"}


@pytest.mark.asyncio
async def test_dashboard_http_keeps_result_envelope(client: AsyncClient, app: FastAPI) -> None:
    from apps.api.dependencies import get_brsapi_query_service, get_market_service

    class _Service:
        async def get_overview(self):
            return Result.ok({"gainers": 1})

        async def get_index_values(self):
            return Result.ok([])

        async def get_top_gainers(self, limit):
            return Result.ok([])

        async def get_top_losers(self, limit):
            return Result.ok([])

        async def get_most_active(self, limit):
            return Result.ok([])

    class _Brs:
        async def get_enriched_snapshots(self, limit):
            return []

        async def get_commodity_prices(self):
            return []

        async def get_crypto_prices(self):
            return []

    app.dependency_overrides[get_market_service] = lambda: _Service()
    app.dependency_overrides[get_brsapi_query_service] = lambda: _Brs()
    try:
        resp = await client.get("/api/v1/market-dashboard")
    finally:
        app.dependency_overrides.pop(get_market_service, None)
        app.dependency_overrides.pop(get_brsapi_query_service, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["overview"]["value"]["gainers"] == 1


@pytest.mark.asyncio
async def test_heatmap_http_serializes_data_as_of(client: AsyncClient, app: FastAPI) -> None:
    from apps.api.dependencies import get_brsapi_query_service

    snapshot = {
        "symbol": "فولاد",
        "name": "فولاد مبارکه",
        "price_last": 1000,
        "price_last_change_pct": 1.5,
        "trade_value": 1e9,
        "trade_volume": 10,
        "fetched_at": "2026-10-28T09:30:00+00:00",
    }
    fake = SimpleNamespace(get_latest_snapshots=AsyncMock(return_value=[snapshot]))
    app.dependency_overrides[get_brsapi_query_service] = lambda: fake
    try:
        resp = await client.get("/api/v1/market/heatmap")
    finally:
        app.dependency_overrides.pop(get_brsapi_query_service, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data_as_of"] == snapshot["fetched_at"]
    assert body["data"][0]["symbol"] == "فولاد"

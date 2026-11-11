"""Dashboard endpoints must publish the source timestamp they served.

Audit API-04. ``/market/overview``, ``/market-dashboard`` and ``/market-watch``
returned data with no ``data_as_of``, so the frontend had no way to tell a
fresh snapshot from a stale one and hard-coded ``isFresh: false`` instead.
"""

from __future__ import annotations

from datetime import datetime

from core.result import Result
from services.market_service import MarketService

TS = datetime(2026, 10, 29, 9, 30)


class _Brsapi:
    def __init__(self, rows=None) -> None:
        self.rows = rows or []

    async def get_latest_snapshots(self, limit: int = 500):
        return self.rows

    async def get_latest_indices(self):
        return []

    async def get_enriched_snapshots(self, limit: int = 500):
        return []

    async def get_commodity_prices(self):
        return Result.ok([])

    async def get_crypto_prices(self):
        return Result.ok([])


class _QuoteRepo:
    async def get_market_summary(self):
        return Result.ok({})


async def test_service_overview_carries_the_source_timestamp() -> None:
    service = MarketService(
        quote_repo=_QuoteRepo(),
        brsapi_query_service=_Brsapi([{"symbol": "AAA", "fetched_at": TS}]),
    )

    result = await service.get_overview()

    assert result.success
    assert result.value["data_as_of"] == TS.isoformat()


async def test_overview_endpoint_lifts_it_into_the_envelope(client, app) -> None:
    from apps.api.dependencies import get_market_service

    class _FakeService:
        async def get_overview(self):
            return Result.ok(
                {
                    "total_instruments": 1,
                    "total_quotes": 1,
                    "gainers": 1,
                    "losers": 0,
                    "unchanged": 0,
                    "total_value": 0,
                    "total_volume": 0,
                    "avg_change_pct": 0,
                    "data_as_of": TS.isoformat(),
                }
            )

    app.dependency_overrides[get_market_service] = lambda: _FakeService()
    response = await client.get("/api/v1/market/overview")

    body = response.json()
    assert body["data_as_of"] == TS.isoformat()
    assert "data_as_of" not in (body["data"] or {})


async def test_dashboard_envelope_carries_the_source_timestamp(client, app) -> None:
    from apps.api.dependencies import get_brsapi_query_service, get_market_service

    class _FakeService:
        async def get_overview(self):
            return Result.ok({"gainers": 1, "losers": 0, "unchanged": 0, "data_as_of": TS.isoformat()})

        async def get_index_values(self):
            return Result.ok([])

        async def get_top_gainers(self, limit=20):
            return Result.ok([])

        async def get_top_losers(self, limit=20):
            return Result.ok([])

        async def get_most_active(self, limit=20):
            return Result.ok([])

    app.dependency_overrides[get_market_service] = lambda: _FakeService()
    app.dependency_overrides[get_brsapi_query_service] = lambda: _Brsapi()
    response = await client.get("/api/v1/market-dashboard")

    assert response.json()["data_as_of"] == TS.isoformat()


async def test_market_watch_envelope_carries_the_snapshot_timestamp(client, app) -> None:
    from apps.api.dependencies import get_brsapi_query_service

    row = {
        "symbol": "AAA",
        "name": "الف",
        "fetched_at": TS,
        "price_last": 1000.0,
        "price_last_change_pct": 1.0,
        "trade_value": 1e9,
        "trade_volume": 1000,
    }
    app.dependency_overrides[get_brsapi_query_service] = lambda: _Brsapi([row])
    response = await client.get("/api/v1/market-watch")

    assert response.json()["data_as_of"] == TS.isoformat()

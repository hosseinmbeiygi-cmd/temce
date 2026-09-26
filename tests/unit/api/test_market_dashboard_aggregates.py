"""Unit tests for the dashboard aggregate endpoints in apps/api/endpoints/market.py.

Covers:
  * /market/cashflow-by-sector — per-sector net real flow grouping
  * /market/value-history      — daily market trade value from historical daily
  * /market/ownership-history  — daily real/legal net flow from historical real/legal
  * _fa_weekday helper          — YYYYMMDD and YYYY-MM-DD parsing

All DB/BrsApi access is mocked; no real database is touched.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.endpoints.market import (
    _classify_asset,
    _fa_weekday,
    market_asset_allocation,
    market_cashflow_by_sector,
    market_ownership_history,
    market_value_history,
)


@pytest.fixture(autouse=True)
def _clear_agg_cache():
    """Each test must start with an empty aggregate cache, or cached rows
    from a previous test shadow the current mock's snapshots."""
    from apps.api.endpoints import market as market_ep

    market_ep._AGG_CACHE.clear()
    yield
    market_ep._AGG_CACHE.clear()


def _brsapi_with_snapshots(snapshots: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(get_latest_snapshots=AsyncMock(return_value=snapshots))


def _brsapi_with_session(execute_results: list) -> SimpleNamespace:
    """Session whose execute() returns the given objects in order."""
    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute_results)
    return SimpleNamespace(session=session)


class TestFaWeekday:
    def test_compact_gregorian(self) -> None:
        # 2026-09-21 is a Monday → دوشنبه
        assert _fa_weekday("20260921") == "دوشنبه"

    def test_dashed_gregorian(self) -> None:
        assert _fa_weekday("2026-09-21") == "دوشنبه"

    def test_jalali_date(self) -> None:
        # 1405-06-18 (Jalali) = 2026-09-09 → Wednesday
        assert _fa_weekday("1405-06-18") == "چهارشنبه"
        # 1405-06-21 (Jalali) = 2026-09-12 → Saturday (a real TSE trading day)
        assert _fa_weekday("1405-06-21") == "شنبه"

    def test_unparsable_returns_raw(self) -> None:
        assert _fa_weekday("جمعه") == "جمعه"
        assert _fa_weekday("") == ""


class TestClassifyAsset:
    def test_plain_equity(self) -> None:
        assert _classify_asset("فولاد مبارکه اصفهان") == "سهام"

    def test_holding(self) -> None:
        assert _classify_asset("سرمایه‌گذاری تامین اجتماعی") == "سرمایه‌گذاری"
        assert _classify_asset("سرمایه گذاری غدیر") == "سرمایه‌گذاری"

    def test_funds(self) -> None:
        assert _classify_asset("صندوق سرمایه‌گذاری طلا") == "صندوق طلا"
        assert _classify_asset("صندوق درآمد ثابت مفید") == "اوراق درآمد ثابت"
        assert _classify_asset("صندوق سهامی آریا") == "صندوق سهامی"

    def test_rights_and_empty_excluded(self) -> None:
        assert _classify_asset("حق تقدم فلزات") is None
        assert _classify_asset("") is None

    def test_bonds(self) -> None:
        assert _classify_asset("اوراق اجاره") == "اوراق درآمد ثابت"


class TestAssetAllocation:
    def test_buckets_and_percentage(self) -> None:
        brsapi = _brsapi_with_snapshots(
            [
                {"name": "فولاد", "market_value": 5e12},
                {"name": "سرمایه‌گذاری غدیر", "market_value": 2e12},
                {"name": "صندوق طلا یکم", "market_value": 1e12},
                {"name": "حق تقدم", "market_value": 9e12},  # excluded
                {"name": "فولاد", "market_value": 0},  # zero skipped
            ]
        )
        resp = asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        assert resp.success is True
        by_label = {r["label"]: r for r in resp.data}
        # total = 5e12 (سهام) + 2e12 (سرمایه‌گذاری) + 1e12 (صندوق طلا) = 8e12
        assert by_label["سهام"]["pct"] == 62.5
        assert by_label["سرمایه‌گذاری"]["pct"] == 25.0
        assert by_label["صندوق طلا"]["pct"] == 12.5
        assert by_label["صندوق طلا"]["value_b"] == 1.0
        # حق تقدم must not leak into any bucket
        assert len(resp.data) == 3

    def test_zero_total_returns_empty(self) -> None:
        brsapi = _brsapi_with_snapshots([{"name": "فولاد", "market_value": 0}])
        resp = asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        assert resp.success is True
        assert resp.data == []

    def test_error_path(self) -> None:
        brsapi = SimpleNamespace(get_latest_snapshots=AsyncMock(side_effect=RuntimeError("db down")))
        resp = asyncio.run(market_asset_allocation(limit=2000, brsapi=brsapi))
        assert resp.success is False


class TestCashflowBySector:
    def test_groups_by_sector_and_sorts(self) -> None:
        brsapi = _brsapi_with_snapshots(
            [
                {"sector": "فلزات اساسی", "price_last": 1000, "buy_real_volume": 2_000_000, "sell_real_volume": 0},
                {"sector": "فلزات اساسی", "price_last": 500, "buy_real_volume": 0, "sell_real_volume": 1_000_000},
                {"sector": "بانک‌ها", "price_last": 2000, "buy_real_volume": 1_000_000, "sell_real_volume": 1_000_000},
            ]
        )
        resp = asyncio.run(market_cashflow_by_sector(limit=500, brsapi=brsapi))
        assert resp.success is True
        by_name = {r["name"]: r["value_b"] for r in resp.data}
        # (2M − 0)×1000 + (0 − 1M)×500 = +1.5e9 → 1.5
        assert by_name["فلزات اساسی"] == 1.5
        assert by_name["بانک‌ها"] == 0.0
        # sorted descending
        values = [r["value_b"] for r in resp.data]
        assert values == sorted(values, reverse=True)

    def test_blank_sector_becomes_sayr(self) -> None:
        brsapi = _brsapi_with_snapshots(
            [{"sector": None, "price_last": 100, "buy_real_volume": 1_000_000, "sell_real_volume": 0}]
        )
        resp = asyncio.run(market_cashflow_by_sector(limit=500, brsapi=brsapi))
        assert resp.data[0]["name"] == "سایر"

    def test_skips_zero_price_and_zero_flow(self) -> None:
        brsapi = _brsapi_with_snapshots(
            [
                {"sector": "A", "price_last": 0, "buy_real_volume": 5, "sell_real_volume": 0},
                {"sector": "B", "price_last": 100, "buy_real_volume": 0, "sell_real_volume": 0},
            ]
        )
        resp = asyncio.run(market_cashflow_by_sector(limit=500, brsapi=brsapi))
        assert resp.data == []

    def test_error_path(self) -> None:
        brsapi = SimpleNamespace(get_latest_snapshots=AsyncMock(side_effect=RuntimeError("db down")))
        resp = asyncio.run(market_cashflow_by_sector(limit=500, brsapi=brsapi))
        assert resp.success is False
        assert resp.data == []


class TestValueHistory:
    def test_maps_rows_to_billion_toman(self) -> None:
        dates_result = MagicMock()
        dates_result.scalars.return_value.all.return_value = ["20260921", "20260922"]
        rows_result = MagicMock()
        rows_result.all.return_value = [
            SimpleNamespace(date="20260921", total_value=8.4e12),
            SimpleNamespace(date="20260922", total_value=9.1e12),
        ]
        brsapi = _brsapi_with_session([dates_result, rows_result])
        resp = asyncio.run(market_value_history(days=5, brsapi=brsapi))
        assert resp.success is True
        assert len(resp.data) == 2
        assert resp.data[0]["value_b"] == 8400.0
        assert resp.data[0]["day"] == "دوشنبه"  # 2026-09-21 Monday
        assert resp.data[1]["day"] == "سه‌شنبه"

    def test_empty_db_returns_empty(self) -> None:
        dates_result = MagicMock()
        dates_result.scalars.return_value.all.return_value = []
        brsapi = _brsapi_with_session([dates_result])
        resp = asyncio.run(market_value_history(days=5, brsapi=brsapi))
        assert resp.success is True
        assert resp.data == []


class TestOwnershipHistory:
    def test_net_real_legal_per_day(self) -> None:
        dates_result = MagicMock()
        dates_result.scalars.return_value.all.return_value = ["20260921"]
        rows_result = MagicMock()
        rows_result.all.return_value = [
            SimpleNamespace(date="20260921", real_buy=3e9, real_sell=1e9, legal_buy=2e9, legal_sell=6e9),
        ]
        brsapi = _brsapi_with_session([dates_result, rows_result])
        resp = asyncio.run(market_ownership_history(days=5, brsapi=brsapi))
        assert resp.success is True
        row = resp.data[0]
        assert row["real_b"] == 2.0
        assert row["legal_b"] == -4.0
        assert row["day"] == "دوشنبه"

    def test_empty_db_returns_empty(self) -> None:
        dates_result = MagicMock()
        dates_result.scalars.return_value.all.return_value = []
        brsapi = _brsapi_with_session([dates_result])
        resp = asyncio.run(market_ownership_history(days=5, brsapi=brsapi))
        assert resp.data == []

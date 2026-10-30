"""Phase 2 market-coverage contract — pure builders, no database.

Pins the behaviours Phase 2 is judged on:

* the Tehran board keeps all eleven rows and every required column even when
  the retail feed is missing (fail-closed, never zero);
* a used-gold row's bubble is computed from its own price, not copied from the
  official 18k row;
* platforms expose price comparison only — no order/payment/checkout surface;
* the returns matrix labels insufficient periods and never emits NaN/Infinity;
* the fund map drops non-finite sizes, guards division by zero, and links each
  cell back to the Phase 1 fund row.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db_session
from src.gold_desk import phase1, phase2
from src.gold_desk.api import router as gold_router
from src.gold_desk.phase2_schemas import MarketCapabilities, PlatformQuote

NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
FRESH = (NOW - timedelta(minutes=1)).isoformat()
XAU_USD = 4000.0
USD_TOMAN = 100_000.0
USD_RIAL = USD_TOMAN * 10

MARKET: dict[str, dict] = {
    "XAUUSD": {"symbol": "XAUUSD", "price": XAU_USD, "change_value": 10.0, "fetched_at": FRESH},
    "USD": {"symbol": "USD", "price": USD_TOMAN, "change_value": 1_000.0, "fetched_at": FRESH},
    "IR_GOLD_18K": {
        "symbol": "IR_GOLD_18K",
        "price": 6_800_000.0,
        "change_value": 100_000.0,
        "change_percent": 1.5,
        "fetched_at": FRESH,
    },
    "IR_GOLD_24K": {
        "symbol": "IR_GOLD_24K",
        "price": 9_000_000.0,
        "change_value": 150_000.0,
        "change_percent": 1.7,
        "fetched_at": FRESH,
    },
    "IR_COIN_EMAMI": {
        "symbol": "IR_COIN_EMAMI",
        "price": 80_000_000.0,
        "change_value": 1_000_000.0,
        "change_percent": 1.2,
        "fetched_at": FRESH,
    },
    "IR_COIN_BAHAR": {"symbol": "IR_COIN_BAHAR", "price": 79_000_000.0, "fetched_at": FRESH},
    "IR_COIN_HALF": {"symbol": "IR_COIN_HALF", "price": 45_000_000.0, "fetched_at": FRESH},
    "IR_COIN_QUARTER": {"symbol": "IR_COIN_QUARTER", "price": 26_000_000.0, "fetched_at": FRESH},
    "IR_COIN_1G": {"symbol": "IR_COIN_1G", "price": 9_500_000.0, "fetched_at": FRESH},
}


def _sources() -> tuple[dict[str, phase1.PhysicalRow], phase1.TerminalReferences]:
    refs = phase1.build_references(MARKET, now=NOW)
    rows = {
        symbol: phase1.build_physical_row(
            symbol,
            label,
            basis,
            MARKET.get(symbol),
            xau_usd=refs.xau_usd,
            usd_irt_rial=refs.usd_irt_rial,
            ref_quality=refs.quality,
            now=NOW,
        )
        for symbol, label, basis in phase1.PHASE1_PHYSICAL
    }
    return rows, refs  # type: ignore[return-value]


def _series(days: int, *, start: date = date(2026, 7, 1), base: float = 100.0, step: float = 0.1):
    return {start + timedelta(days=index): base + step * index for index in range(days)}


# ════════════════════════════════════════════════════════════════
# 1. Tehran board
# ════════════════════════════════════════════════════════════════


class TestTehranBoard:
    def test_all_eleven_rows_survive_a_missing_feed(self) -> None:
        official, refs = _sources()
        board = phase2.build_tehran_board(official_rows=official, references=refs, now=NOW)

        assert len(board.rows) == 11
        assert {row.key for row in board.rows} == {spec.key for spec in phase2.TEHRAN_SPECS}
        assert board.source_status == "not_connected"
        for row in board.rows:
            assert row.tehran_price is None
            assert row.quality == "NO_DATA"
            assert row.official_price and row.official_price > 0
            assert row.data_gaps
        assert board.capabilities.checkout is False
        assert board.capabilities.payment is False

    def test_used_gold_bubble_differs_from_the_official_18k_row(self) -> None:
        official, refs = _sources()
        quotes = {
            "tehran_gold_18": {
                "price_rial": 70_000_000.0,
                "as_of": NOW,
                "source": "fixture",
                "source_detail": "tehran_fixture",
            },
            "tehran_used_18": {
                "price_rial": 60_000_000.0,
                "as_of": NOW,
                "source": "fixture",
                "source_detail": "tehran_fixture",
            },
        }
        board = phase2.build_tehran_board(official_rows=official, references=refs, source_rows=quotes, now=NOW)

        rows = {row.key: row for row in board.rows}
        used = rows["tehran_used_18"]
        fresh = rows["tehran_gold_18"]
        assert used.kind == "used"
        assert used.intrinsic == fresh.intrinsic  # same 18k intrinsic
        assert used.bubble_pct is not None and fresh.bubble_pct is not None
        assert used.bubble_pct != fresh.bubble_pct
        assert used.spread_vs_official_amount == pytest.approx(60_000_000.0 - 68_000_000.0)
        assert used.spread_vs_official_pct == pytest.approx(-11.76, abs=0.01)
        assert used.implied_usd is not None
        assert "دست‌دوم" in (used.note or "")

    def test_gram_intrinsic_grows_with_purity(self) -> None:
        official, refs = _sources()
        board = phase2.build_tehran_board(official_rows=official, references=refs, now=NOW)
        intrinsic = {row.key: row.intrinsic for row in board.rows}

        assert intrinsic["tehran_gold_18"] is not None
        assert intrinsic["tehran_gold_18"] < intrinsic["tehran_gold_20"] < intrinsic["tehran_gold_21"]
        assert intrinsic["tehran_gold_21"] < intrinsic["tehran_gold_24"]

    def test_partial_feed_reports_partial_status(self) -> None:
        official, refs = _sources()
        quotes = {
            "tehran_gold_18": {
                "price_rial": 70_000_000.0,
                "as_of": NOW,
                "source": "fixture",
                "source_detail": "tehran_fixture",
            }
        }
        board = phase2.build_tehran_board(official_rows=official, references=refs, source_rows=quotes, now=NOW)

        assert board.source_status == "partial"
        priced = [row for row in board.rows if row.tehran_price is not None]
        assert len(priced) == 1


# ════════════════════════════════════════════════════════════════
# 2. Platforms — price comparison only
# ════════════════════════════════════════════════════════════════


class TestPlatforms:
    def test_no_source_means_no_rows_and_no_capabilities(self) -> None:
        _, refs = _sources()
        platforms = phase2.build_platforms(references=refs, now=NOW)

        assert platforms.rows == []
        assert platforms.platform_count == 0
        assert platforms.source_status == "not_connected"
        assert platforms.notice
        assert platforms.capabilities == MarketCapabilities()

    def test_quote_rows_are_priced_but_schema_has_no_order_fields(self) -> None:
        _, refs = _sources()
        raw = [
            {
                "platform": "نمونه",
                "platform_slug": "sample",
                "buy_price_rial": 70_000_000.0,
                "sell_price_rial": 69_000_000.0,
                "low_price_rial": 69_500_000.0,
                "high_price_rial": 70_500_000.0,
                "as_of": NOW,
                "source": "fixture",
                "source_detail": "platform_fixture",
            }
        ]
        platforms = phase2.build_platforms(references=refs, source_rows=raw, now=NOW)

        row = platforms.rows[0]
        assert row.buy_price == 70_000_000.0
        assert row.sell_price == 69_000_000.0
        assert row.intrinsic_18k is not None
        assert row.bubble_pct is not None
        assert row.implied_usd is not None
        assert platforms.source_status == "connected"
        assert platforms.capabilities.model_dump() == {
            "orders": False,
            "wallet": False,
            "delivery": False,
            "checkout": False,
            "payment": False,
            "preview_only": True,
        }

        forbidden = {"order", "orders", "buy_url", "sell_url", "checkout", "payment", "cart"}
        assert not forbidden & set(PlatformQuote.model_fields)

    def test_phase2_routes_are_read_only_and_never_trade(self) -> None:
        phase2_paths = {"/gold/tehran-board", "/gold/platforms", "/gold/returns-matrix", "/gold/fund-map"}
        forbidden = {"order", "orders", "buy", "sell", "wallet", "delivery", "custody", "checkout", "payment"}
        mounted = {getattr(route, "path", ""): route for route in gold_router.routes}

        assert phase2_paths <= set(mounted)
        for path in phase2_paths:
            assert mounted[path].methods == {"GET"}
        for path in mounted:
            assert not forbidden & set(path.strip("/").split("/"))


# ════════════════════════════════════════════════════════════════
# 3. Returns matrix
# ════════════════════════════════════════════════════════════════


class TestReturnsMatrix:
    def test_periods_with_enough_data_are_complete_and_the_rest_are_no_data(self) -> None:
        series = {"coin_emami": _series(110), "usd": _series(110), "xau_usd": _series(110)}
        matrix = phase2.build_returns_matrix_from_series(series=series, now=NOW)
        coin = {row.key: row for row in matrix.rows}["coin_emami"]

        assert coin.returns["1m"].status == "complete"
        assert coin.returns["1m"].value is not None
        assert coin.returns["3m"].status == "complete"
        assert coin.returns["6m"].status == "no_data"
        assert coin.returns["9m"].status == "no_data"
        assert coin.returns["1y"].status == "no_data"
        assert coin.returns["6m"].reason

    def test_stale_end_observation_is_labelled_incomplete_not_hidden(self) -> None:
        series = {"coin_emami": _series(60, start=date(2026, 7, 1)), "usd": _series(60, start=date(2026, 7, 1))}
        matrix = phase2.build_returns_matrix_from_series(series=series, now=NOW)
        coin = {row.key: row for row in matrix.rows}["coin_emami"]

        month = coin.returns["1m"]
        assert month.value is not None
        assert month.status == "incomplete"
        assert "قدیمی" in (month.reason or "")

    def test_usd_base_switch_converts_through_the_same_window(self) -> None:
        series = {"coin_emami": _series(110), "usd": _series(110)}
        matrix = phase2.build_returns_matrix_from_series(series=series, base_currency="USD", now=NOW)
        rows = {row.key: row for row in matrix.rows}

        # The coin and USD/IRR series are identical, so the USD return is zero.
        assert rows["coin_emami"].returns["1m"].value == pytest.approx(0.0, abs=0.02)
        # The USD/IRR row expressed in USD is trivially zero.
        assert rows["usd"].returns["1m"].value == pytest.approx(0.0, abs=1e-9)
        assert matrix.base_currency == "USD"

    def test_correlation_needs_twenty_common_daily_returns(self) -> None:
        long_series = _series(110)
        matrix = phase2.build_returns_matrix_from_series(
            series={"coin_emami": long_series, "usd": long_series}, now=NOW
        )
        coin = {row.key: row for row in matrix.rows}["coin_emami"]
        assert coin.correlation_status == "complete"
        assert coin.correlation_90d == pytest.approx(1.0)
        assert coin.correlation_observations >= phase2.MIN_CORRELATION_OBS

        short = _series(10)
        matrix = phase2.build_returns_matrix_from_series(series={"coin_emami": short, "usd": short}, now=NOW)
        coin = {row.key: row for row in matrix.rows}["coin_emami"]
        assert coin.correlation_90d is None
        assert coin.correlation_status == "no_data"
        assert "حداقل" in (coin.correlation_reason or "")

    def test_missing_sources_are_reported_not_invented(self) -> None:
        matrix = phase2.build_returns_matrix_from_series(series={"usd": _series(110)}, now=NOW)
        rows = {row.key: row for row in matrix.rows}

        cpi = rows["cpi"]
        assert cpi.quality == "NO_DATA"
        assert all(item.status == "no_data" for item in cpi.returns.values())
        assert cpi.data_gaps
        assert rows["tedpix"].quality == "NO_DATA"

    def test_payload_never_contains_nan_or_infinity(self) -> None:
        series = {"coin_emami": _series(110), "usd": _series(110), "xau_usd": _series(110)}
        matrix = phase2.build_returns_matrix_from_series(series=series, base_currency="USD", now=NOW)
        payload = json.dumps(matrix.model_dump(mode="json"), allow_nan=False)

        assert "NaN" not in payload
        assert "Infinity" not in payload


class TestReturnsSeriesLoading:
    """Regression guards for the dev-DB anomalies found on 2026-10-26."""

    def test_fx_history_is_already_rial_and_is_never_multiplied_by_ten(self) -> None:
        series = phase2._series_from_rows([("1405-06-23", 2_339_600.0)], unit="rial")

        assert series == {date(2026, 9, 14): 2_339_600.0}

    def test_physical_history_is_toman_and_is_converted_to_rial(self) -> None:
        series = phase2._series_from_rows([("1405-06-23", 1_000.0)], unit="toman")

        assert series == {date(2026, 9, 14): 10_000.0}

    def test_backfilled_rows_outside_the_window_are_dropped(self) -> None:
        cutoff = date(2025, 6, 13)
        rows = [
            ("1405-06-23", 100.0),
            ("1389-01-14", 9_999.0),  # backfilled 2010 row that used to poison 3m
        ]
        series = phase2._series_from_rows(rows, unit="rial", cutoff=cutoff)

        assert series == {date(2026, 9, 14): 100.0}

    def test_duplicate_dates_keep_the_newest_ingested_row(self) -> None:
        rows = [("1405-06-23", 200.0), ("1405-06-23", 100.0)]  # newest id first

        series = phase2._series_from_rows(rows, unit="rial")

        assert series[date(2026, 9, 14)] == 200.0

    async def test_build_returns_matrix_loads_usd_history_in_rial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        units: dict[str, str] = {}

        async def fake_pro(session, symbol, *, unit, now, days=phase2.HISTORY_WINDOW_DAYS):
            units[symbol] = unit
            return {}

        async def empty(session, *args, **kwargs):
            return {}

        async def no_current(session):
            return {}

        monkeypatch.setattr(phase2, "_load_pro_history", fake_pro)
        monkeypatch.setattr(phase2, "_load_current_prices", no_current)
        monkeypatch.setattr(phase2, "_load_gold_history", empty)
        monkeypatch.setattr(phase2, "_load_gold_fund_index", empty)
        monkeypatch.setattr(phase2, "_load_index_series", empty)
        monkeypatch.setattr(phase2, "_load_crypto_history", empty)

        await phase2.build_returns_matrix(None, now=NOW)  # type: ignore[arg-type]

        assert units == {"USD": "rial", "XAUUSD": "usd"}

    def test_discontinuous_series_reports_no_data_instead_of_an_absurd_return(self) -> None:
        series = {date(2024, 1, 1): 100.0, date(2026, 10, 20): 200.0}

        month = phase2._period_return(series, "1m", now=NOW)

        assert month.status == "no_data"
        assert month.value is None
        assert "پیوسته نیست" in (month.reason or "")
        assert month.start_date == date(2024, 1, 1)
        assert month.end_date == date(2026, 10, 20)


# ════════════════════════════════════════════════════════════════
# 4. Fund market map + summary
# ════════════════════════════════════════════════════════════════


def _fund(symbol: str, size: float, *, name: str | None = None) -> dict:
    return {
        "symbol": symbol,
        "name": name or symbol,
        "trade_value": size,
        "market_value": size * 2,
        "price_last": 1_000.0,
        "price_last_change_pct": 1.5,
        "fetched_at": FRESH,
    }


class TestFundMap:
    def test_non_finite_and_zero_sizes_never_reach_the_map(self) -> None:
        funds = [
            _fund("A", 500.0),
            _fund("B", 300.0),
            _fund("C", float("inf")),
            _fund("D", 0.0),
            _fund("E", -5.0),
            _fund("F", float("nan")),
        ]
        fund_map = phase2.build_fund_map_from_funds(funds, top_n=1, now=NOW)

        assert [cell.symbol for cell in fund_map.cells] == ["A", "B"]
        assert fund_map.summary.total_value == 800.0
        assert [item.symbol for item in fund_map.summary.items] == ["A"]
        assert fund_map.summary.other_value == 300.0
        assert fund_map.summary.other_share_pct == pytest.approx(37.5)
        assert fund_map.summary.cells_count == 2
        for cell in fund_map.cells:
            assert math.isfinite(cell.size)
            assert cell.size_share_pct is not None and math.isfinite(cell.size_share_pct)
        json.dumps(fund_map.model_dump(mode="json"), allow_nan=False)

    def test_cells_link_to_the_phase1_fund_row(self) -> None:
        fund_map = phase2.build_fund_map_from_funds([_fund("کهربا", 100.0)], now=NOW)

        assert fund_map.cells[0].href == f"/gold/terminal#fund-{quote('کهربا', safe='')}"

    def test_zero_total_does_not_divide_by_zero(self) -> None:
        fund_map = phase2.build_fund_map_from_funds([], now=NOW)

        assert fund_map.cells == []
        assert fund_map.summary.total_value == 0.0
        assert fund_map.summary.other_share_pct is None
        assert fund_map.summary.items == []

    def test_market_value_metric_switches_the_size_axis(self) -> None:
        fund_map = phase2.build_fund_map_from_funds(
            [_fund("A", 100.0), _fund("B", 400.0)],
            size_metric="market_value",
            now=NOW,
        )

        assert [cell.symbol for cell in fund_map.cells] == ["B", "A"]
        assert fund_map.summary.total_value == 1_000.0
        assert fund_map.size_metric == "market_value"


# ════════════════════════════════════════════════════════════════
# 5. HTTP contract on a probe app (DB dependency stubbed)
# ════════════════════════════════════════════════════════════════


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    official, refs = _sources()
    board = phase2.build_tehran_board(official_rows=official, references=refs, now=NOW)
    platforms = phase2.build_platforms(references=refs, now=NOW)
    matrix = phase2.build_returns_matrix_from_series(series={"coin_emami": _series(110), "usd": _series(110)}, now=NOW)
    fund_map = phase2.build_fund_map_from_funds([_fund("A", 100.0)], now=NOW)

    async def _board(session, *, now=None):
        return board

    async def _platforms(session, *, now=None):
        return platforms

    async def _matrix(session, *, base_currency="IRR", now=None):
        return matrix

    async def _fund_map(session, *, size_metric="trade_value", top_n=10, now=None):
        return fund_map

    monkeypatch.setattr(phase2, "load_tehran_board", _board)
    monkeypatch.setattr(phase2, "load_platforms", _platforms)
    monkeypatch.setattr(phase2, "build_returns_matrix", _matrix)
    monkeypatch.setattr(phase2, "build_fund_map", _fund_map)

    probe = FastAPI()
    probe.include_router(gold_router)
    probe.dependency_overrides[get_db_session] = lambda: None
    return TestClient(probe, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "path",
    ["/gold/tehran-board", "/gold/platforms", "/gold/returns-matrix", "/gold/fund-map"],
)
def test_phase2_http_routes_return_success_and_closed_capabilities(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["capabilities"]["orders"] is False
    assert body["data"]["capabilities"]["preview_only"] is True


def test_returns_matrix_rejects_an_unknown_base_currency(client: TestClient) -> None:
    assert client.get("/gold/returns-matrix", params={"base_currency": "EUR"}).status_code == 422


def test_fund_map_rejects_an_unknown_size_metric(client: TestClient) -> None:
    assert client.get("/gold/fund-map", params={"size_metric": "nav"}).status_code == 422

"""Gate test: the V2 screener reports absences, never zeroes.

The screener used to hand every advanced analytic a ``0.0`` default, and ``0.0`` is a real
reading for several of them — RSI 0 is maximum oversold, %B 0 is a close sitting on the lower
Bollinger band. Worse, ``/screener-v2`` never passed ``history_map`` into ``batch_analyze``,
so *no* symbol had ever been measured and the whole table was rendered from defaults.

Invariant under test (owner, 2026-09-21): a number the platform shows is either real data or
an explicit declaration that there is none. Zero is a claim, not an empty cell.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.api.endpoints import screener_v2 as screener_ep
from services.market_watch_helper import candles_from_daily_rows, fetch_history_map
from services.smart_screener_v2 import NOT_MEASURED, EnhancedScreenedSymbol, SmartScreenerV2

#: Numerics that come out of the analytics engine.
ANALYTIC_FIELDS = (
    "rsi",
    "macd_histogram",
    "bb_pct",
    "atr_pct",
    "adx",
    "trend_strength",
    "pattern_confidence",
    "technical_score",
    "momentum_score",
    "risk_score",
    "support_level",
    "resistance_level",
    "distance_to_support",
    "distance_to_resistance",
    "poc_price",
    "value_area_high",
    "value_area_low",
)

#: Categoricals that used to fall back to a reading ("sideways", "normal", "neutral").
CATEGORY_FIELDS = ("trend_direction", "volatility_regime", "volume_trend", "composite_signal")


def _history(bars: int, *, start: float = 100.0) -> list[dict[str, Any]]:
    """A drifting OHLCV series — enough shape for the indicators to converge."""
    out: list[dict[str, Any]] = []
    price = start
    for i in range(bars):
        price = start + i * 0.7 + (1.5 if i % 3 else -1.0)
        out.append({
            "date": f"2026-09-{(i % 28) + 1:02d}",
            "price_close": round(price, 2),
            "price_high": round(price + 2, 2),
            "price_low": round(price - 2, 2),
            "price_open": round(price - 0.5, 2),
            "volume": 100_000 + i * 500,
            "value": (100_000 + i * 500) * price,
        })
    return out


def _quote(symbol: str = "فولاد") -> dict[str, Any]:
    return {
        "symbol": symbol,
        "price_close": 150.0,
        "price_last": 151.0,
        "price_high": 152.0,
        "price_low": 148.0,
        "price_change_pct": 1.2,
        "volume": 500_000,
        "value": 75_000_000,
    }


def _analyze(bars: int) -> EnhancedScreenedSymbol:
    return SmartScreenerV2().analyze_symbol(
        symbol="فولاد",
        name="فولاد مبارکه",
        market="بورس",
        industry="فلزات",
        quote=_quote(),
        history=_history(bars),
    )


class TestShortHistoryIsDeclaredNotScored:
    def test_every_analytic_is_null_below_the_compute_window(self) -> None:
        result = _analyze(12)

        assert result.analytics_computed is False
        assert result.analytics_bars == 12
        for field in ANALYTIC_FIELDS:
            assert getattr(result, field) is None, f"{field} reported a value it never measured"

    def test_categoricals_say_not_measured_not_a_reading(self) -> None:
        result = _analyze(12)

        for field in CATEGORY_FIELDS:
            assert getattr(result, field) == NOT_MEASURED, f"{field} claimed a state with no data"

    def test_empty_history_matches_short_history(self) -> None:
        result = _analyze(0)

        assert result.analytics_computed is False
        assert result.rsi is None
        assert result.trend_direction == NOT_MEASURED

    def test_reason_states_the_missing_data_instead_of_calling_it_normal(self) -> None:
        reason = _analyze(12).reason

        assert "کندل" in reason
        assert "تحلیل عادی" not in reason

    def test_rsi_zero_never_leaks_as_an_oversold_reading(self) -> None:
        """The specific harm: RSI 0.0 is maximum oversold, and the old default was 0.0."""
        assert _analyze(3).rsi is None
        assert _analyze(19).rsi is None


class TestLongHistoryIsMeasured:
    def test_analytics_appear_once_the_window_exists(self) -> None:
        result = _analyze(60)

        assert result.analytics_computed is True
        assert isinstance(result.rsi, float)
        assert result.trend_direction != NOT_MEASURED
        assert result.volatility_regime != NOT_MEASURED
        assert result.technical_score is not None
        assert result.momentum_score is not None
        assert result.risk_score is not None

    def test_composite_keeps_every_leg_when_measured(self) -> None:
        result = _analyze(60)

        legs = [result.technical_score, result.momentum_score, result.risk_score]
        assert all(leg is not None for leg in legs)


class TestCompositeDropsUnmeasuredLegs:
    def test_composite_is_the_smart_money_leg_alone_when_analytics_are_absent(self) -> None:
        screener = SmartScreenerV2()
        smc = 0.42

        composite = screener._compute_composite_score(
            smc_score=smc,
            technical_score=None,
            momentum_score=None,
            risk_score=None,
        )

        # Renormalising over one leg must reproduce it — no silent penalty from the gaps.
        assert composite == pytest.approx(smc)

    def test_unmeasured_risk_does_not_trigger_the_risk_penalty(self) -> None:
        screener = SmartScreenerV2()

        without_risk = screener._compute_composite_score(0.5, None, None, None)
        with_risk = screener._compute_composite_score(0.5, None, None, 0.9)

        assert without_risk == pytest.approx(0.5)
        assert with_risk < without_risk


class TestRankingAndStats:
    @staticmethod
    def _batch() -> tuple[SmartScreenerV2, list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        instruments = [
            {"symbol": "OLD", "name": "کهنه", "market": "بورس", "industry": "فلزات"},
            {"symbol": "NEW", "name": "نوپا", "market": "بورس", "industry": "کشاورزی"},
        ]
        market_watch = [
            {
                "symbol": sym,
                "close": 150.0,
                "last_price": 151.0,
                "high": 152.0,
                "low": 148.0,
                "change": 1.2,
                "volume": 500_000,
                "value": 75_000_000,
            }
            for sym in ("OLD", "NEW")
        ]
        history_map = {"OLD": _history(60), "NEW": _history(6)}
        return SmartScreenerV2(), instruments, market_watch, history_map

    @pytest.mark.parametrize("order", ["desc", "asc"])
    def test_unmeasured_symbols_sort_last_in_both_directions(self, order: str) -> None:
        screener, instruments, market_watch, history_map = self._batch()

        results, _ = screener.batch_analyze(
            instruments=instruments,
            market_watch=market_watch,
            history_map=history_map,
            sort_by="rsi",
            sort_order=order,
            limit=10,
            min_score=-1.0,
        )

        assert [r.symbol for r in results][0] == "OLD"
        assert results[-1].rsi is None

    def test_stats_average_only_measured_rows_and_report_the_split(self) -> None:
        screener, instruments, market_watch, history_map = self._batch()

        _, stats = screener.batch_analyze(
            instruments=instruments,
            market_watch=market_watch,
            history_map=history_map,
            sort_by="composite_score",
            sort_order="desc",
            limit=10,
            min_score=-1.0,
        )

        assert stats["analyticsMeasured"] == 1
        assert stats["analyticsNotMeasured"] == 1
        assert stats["avg_technical"] is not None

    def test_stats_report_null_instead_of_zero_when_nothing_was_measured(self) -> None:
        screener, instruments, market_watch, _ = self._batch()

        _, stats = screener.batch_analyze(
            instruments=instruments,
            market_watch=market_watch,
            history_map={"OLD": _history(6), "NEW": _history(4)},
            sort_by="composite_score",
            sort_order="desc",
            limit=10,
            min_score=-1.0,
        )

        assert stats["avg_technical"] is None
        assert stats["avg_momentum"] is None
        assert stats["avg_risk"] is None
        assert stats["analyticsMeasured"] == 0

    def test_numeric_filter_fails_closed_on_an_absence(self) -> None:
        """An unmeasured symbol must not satisfy «rsi < 30» by virtue of a default zero."""
        screener, _, _, _ = self._batch()
        unmeasured = _analyze(6)

        keep = screener._apply_client_filters(unmeasured, [{"field": "rsi", "operator": "lt", "value": 30}], "and")

        assert keep is False


class TestApiSerialisation:
    def test_item_emits_null_for_every_unmeasured_analytic(self) -> None:
        item = screener_ep._item(_analyze(9))

        for field in ANALYTIC_FIELDS:
            assert item[field] is None, f"{field} reached the client as a fabricated number"
        for field in CATEGORY_FIELDS:
            assert item[field] == NOT_MEASURED
        assert item["analyticsComputed"] is False
        assert item["analyticsBars"] == 9

    def test_item_rounds_only_what_exists(self) -> None:
        item = screener_ep._item(_analyze(60))

        assert item["analyticsComputed"] is True
        assert item["rsi"] == pytest.approx(round(item["rsi"], 2))

    def test_round_helper_passes_absence_through(self) -> None:
        assert screener_ep._n(None, 2) is None
        assert screener_ep._n(3.14159, 2) == 3.14

    def test_the_v2_history_is_fetched_not_assumed_empty(self) -> None:
        """The bug that made all of this dead data: batch_analyze was called without history."""
        import inspect

        source = inspect.getsource(screener_ep)

        assert "history_map=history_map" in source
        assert "fetch_history_map" in source


class TestCandleMapping:
    def test_brsapi_column_names_become_candles_oldest_first(self) -> None:
        rows = [
            {"symbol": "خ", "trade_date": "2026-09-03", "price_close": 103, "price_max": 105,
             "price_min": 101, "price_first": 102, "trade_volume": 900, "trade_value": 92_700},
            {"symbol": "خ", "trade_date": "2026-09-02", "price_close": 100, "price_max": 102,
             "price_min": 98, "price_first": 99, "trade_volume": 800, "trade_value": 80_000},
        ]

        candles = candles_from_daily_rows(rows)

        assert [c["date"] for c in candles] == ["2026-09-02", "2026-09-03"]
        assert candles[-1]["price_high"] == 105
        assert candles[-1]["price_low"] == 101
        assert candles[-1]["price_open"] == 102
        assert candles[-1]["volume"] == 900

    def test_a_day_without_a_close_is_not_a_candle(self) -> None:
        rows = [
            {"trade_date": "2026-09-03", "price_close": 0, "price_max": 0, "price_min": 0},
            {"trade_date": "2026-09-02", "price_close": 100, "price_max": 102, "price_min": 98},
        ]

        assert len(candles_from_daily_rows(rows)) == 1


class _StubHistoryService:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.requested: int | None = None

    async def get_batch_historical_daily(self, limit: int = 61) -> list[dict[str, Any]]:
        self.requested = limit
        return self._rows


class TestHistoryMap:
    @pytest.mark.asyncio
    async def test_grouped_by_symbol_and_limited_to_the_requested_symbols(self) -> None:
        svc = _StubHistoryService([
            {"symbol": "فولاد", "trade_date": "2026-09-02", "price_close": 100},
            {"symbol": "فولاد", "trade_date": "2026-09-01", "price_close": 99},
            {"symbol": "غیر", "trade_date": "2026-09-02", "price_close": 50},
        ])

        history_map = await fetch_history_map(svc, symbols={"فولاد"})

        assert set(history_map) == {"فولاد"}
        assert len(history_map["فولاد"]) == 2
        assert svc.requested is not None

    @pytest.mark.asyncio
    async def test_a_symbol_with_no_usable_rows_is_absent_not_empty(self) -> None:
        svc = _StubHistoryService([{"symbol": "فولاد", "trade_date": "2026-09-02", "price_close": 0}])

        history_map = await fetch_history_map(svc, symbols={"فولاد"})

        assert history_map == {}

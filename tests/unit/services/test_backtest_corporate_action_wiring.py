"""Regression tests for Phase 1 plan fixes (.claude/plan.md).

F7 part (a): the dead, broken ``CorporateActionAdjuster.adjust_prices`` /
``_cutoff_index`` legacy API (always adjusted ``n - 1`` points regardless of
the action's effective date, and had zero callers) has been removed —
``adjust_prices_with_dates`` is the one exact API now.

F7 part (b): ``services/adjusted_price_reader.load_daily_candles_range`` must
read the corporate-action adjusted view and feed
``BacktestService._load_historical_data``'s "historical" source, instead of
raw ``brsapi_historical_daily`` prices that silently ignore capital increases,
bonus shares and dividends.
"""

from __future__ import annotations

from datetime import date

import pytest


class TestLegacyAdjustPricesRemoved:
    def test_adjust_prices_no_longer_exists(self):
        from backtesting.corporate_actions import CorporateActionAdjuster

        assert not hasattr(CorporateActionAdjuster, "adjust_prices")
        assert not hasattr(CorporateActionAdjuster, "_cutoff_index")

    def test_adjust_prices_with_dates_still_exact(self):
        """The surviving API must still give an exact, as-of-safe cutoff."""
        from backtesting.corporate_actions import CorporateActionAdjuster
        from domain.market_data.corporate_action import CorporateAction

        adjuster = CorporateActionAdjuster()
        points = [
            (date(2026, 1, 1), 100.0),
            (date(2026, 1, 2), 100.0),
            (date(2026, 1, 3), 50.0),
            (date(2026, 1, 4), 51.0),
        ]
        points_dt = [(__import__("datetime").datetime(d.year, d.month, d.day), p) for d, p in points]
        actions = [
            CorporateAction(
                id="ca1", instrument_id="X", action_type="stock_split",
                ratio=2.0, date=date(2026, 1, 3),
            )
        ]
        adjusted = adjuster.adjust_prices_with_dates(points_dt, actions)
        assert adjusted[0] == pytest.approx(200.0)
        assert adjusted[1] == pytest.approx(200.0)
        assert adjusted[2] == pytest.approx(50.0)
        assert adjusted[3] == pytest.approx(51.0)


class TestAdjustedPriceReaderRangeQuery:
    def test_range_query_reads_the_adjusted_view(self):
        from services.adjusted_price_reader import ADJUSTED_VIEW, build_range_query

        sql = build_range_query(ADJUSTED_VIEW, adjusted=True)
        assert f"FROM {ADJUSTED_VIEW} d" in sql
        assert "price_close_adj" in sql or "price_last_adj" in sql
        assert "d.trade_date >= :start AND d.trade_date <= :end" in sql

    def test_range_query_raw_mode_is_unadjusted(self):
        from services.adjusted_price_reader import RAW_SOURCE, build_range_query

        sql = build_range_query(RAW_SOURCE, adjusted=False)
        assert "FROM daily_history d" in sql
        assert "_adj" not in sql

    def test_unknown_source_is_a_programming_error(self):
        from services.adjusted_price_reader import build_range_query

        with pytest.raises(ValueError):
            build_range_query("nope", adjusted=True)


class TestBacktestServiceUsesAdjustedView:
    def test_load_historical_data_imports_the_adjusted_reader(self):
        """The historical-source branch must route through the adjusted
        reader, not a raw ad-hoc SQL SELECT against brsapi_historical_daily.
        """
        import inspect

        import services.backtest_service as mod

        src = inspect.getsource(mod.BacktestService._load_historical_data)
        assert "load_daily_candles_range" in src
        assert "FROM brsapi_historical_daily" not in src

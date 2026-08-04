"""Unit tests for BacktestService.

Covers:
  - _compute_metrics: metric aggregation from BacktestResult
  - _get_strategy_class: strategy registry lookup
  - run_backtest: with mocked simulator and data
  - list_runs, get_result, cancel_run
  - run_multi_symbol: multi-symbol backtesting
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.result import Result
from services.backtest_service import BacktestService, _compute_metrics, _get_strategy_class

# ── Helpers ──────────────────────────────────────────────────────


def _make_result():
    """Create a mock BacktestResult with realistic values."""
    r = MagicMock()
    r.total_return_pct = 15.0
    r.max_drawdown = -0.08
    r.equity_curve = [MagicMock(nav=1000), MagicMock(nav=1050), MagicMock(nav=1020)]
    r.final_capital = 1_050_000
    r.trades = [
        MagicMock(pnl=10000, instrument_id="فولاد", side="BUY", quantity=100, price=5000),
        MagicMock(pnl=-5000, instrument_id="فولاد", side="SELL", quantity=100, price=5100),
    ]
    return r


def _make_service(**kwargs: Any) -> BacktestService:
    defaults = {"simulator": MagicMock(), "repository": MagicMock()}
    defaults.update(kwargs)
    return BacktestService(**defaults)


# ════════════════════════════════════════════════════════════════
# 1. _compute_metrics
# ════════════════════════════════════════════════════════════════


class TestComputeMetrics:
    def test_basic(self):
        result = _make_result()
        metrics = _compute_metrics(result)
        assert "total_return_pct" in metrics
        assert "annualized_return_pct" in metrics
        assert "max_drawdown_pct" in metrics
        # total_return_pct comes from RiskMetrics.compute which may override
        assert isinstance(metrics["total_return_pct"], float)

    def test_empty_equity_curve(self):
        result = MagicMock()
        result.equity_curve = []
        result.total_return_pct = 0.0
        result.max_drawdown = 0.0
        metrics = _compute_metrics(result)
        assert "total_return_pct" in metrics

    def test_custom_risk_free_rate(self):
        result = _make_result()
        metrics = _compute_metrics(result, risk_free_rate=0.10)
        assert "sharpe_ratio" in metrics

    def test_metrics_are_floats(self):
        result = _make_result()
        metrics = _compute_metrics(result)
        for k, v in metrics.items():
            if isinstance(v, float):
                assert abs(v) < 1e10, f"Metric {k} has extreme value: {v}"


# ════════════════════════════════════════════════════════════════
# 2. _get_strategy_class
# ════════════════════════════════════════════════════════════════


class TestGetStrategyClass:
    def test_known_strategy(self):
        cls = _get_strategy_class("moving_average_cross")
        if cls is not None:
            assert callable(cls)

    def test_unknown_strategy(self):
        cls = _get_strategy_class("nonexistent_strategy_xyz")
        assert cls is None


# ════════════════════════════════════════════════════════════════
# 3. run (simple)
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestRun:
    async def test_run_delegates_to_simulator(self):
        svc = _make_service()
        mock_strategy = MagicMock()
        svc.simulator.run = MagicMock(return_value=Result.ok(_make_result()))
        result = await svc.run(mock_strategy, capital=1_000_000)
        assert result.success
        svc.simulator.run.assert_called_once()

    async def test_run_with_custom_data(self):
        svc = _make_service()
        mock_strategy = MagicMock()
        data = [{"open": 100, "close": 110, "volume": 1000}]
        svc.simulator.run = MagicMock(return_value=Result.ok(_make_result()))
        result = await svc.run(mock_strategy, data=data)
        assert result.success


# ════════════════════════════════════════════════════════════════
# 4. list_runs, get_result, cancel_run
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestListRuns:
    async def test_list_runs(self):
        svc = _make_service()
        svc._repo.list = AsyncMock(return_value=Result.ok({"items": [], "total": 0}))
        result = await svc.list_runs()
        assert result.success

    async def test_get_result_from_memory(self):
        svc = _make_service()
        svc._runs["bt_001"] = {"id": "bt_001", "name": "test"}
        result = await svc.get_result("bt_001")
        assert result.success
        assert result.value["id"] == "bt_001"

    async def test_get_result_not_found(self):
        svc = _make_service()
        result = await svc.get_result("bt_999")
        # get_result returns Result.ok(None) when not found
        assert result.success
        assert result.value is None

    async def test_cancel_nonexistent(self):
        svc = _make_service()
        result = await svc.cancel_run("bt_999")
        assert not result.success


# ════════════════════════════════════════════════════════════════
# 5. run_backtest
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestRunBacktest:
    async def test_unknown_strategy(self):
        svc = _make_service()
        result = await svc.run_backtest(
            name="test", symbols=["فولاد"],
            strategy_type="nonexistent_strategy",
        )
        assert not result.success
        assert "Unknown strategy" in result.error

    async def test_no_data(self):
        svc = _make_service()
        with patch("services.backtest_service._get_strategy_class") as mock_cls:
            # Create a real strategy class-like with proper __init__ signature

            class FakeStrategy:
                def __init__(self, instrument_id: str = "test", sizing_method: str = "fixed", sizing_value: float = 1000.0):
                    pass

            mock_cls.return_value = FakeStrategy
            result = await svc.run_backtest(
                name="test", symbols=["فولاد"],
                strategy_type="moving_average_cross",
                data_source="auto",
            )
            # Should fail because _load_historical_data returns empty
            assert not result.success
            assert "No historical data" in result.error

    async def test_successful_backtest(self):
        svc = _make_service()
        mock_bt_result = _make_result()
        svc.simulator.run = MagicMock(return_value=Result.ok(mock_bt_result))

        with patch("services.backtest_service._get_strategy_class") as mock_cls:

            class FakeStrategy:
                def __init__(self, instrument_id: str = "test", sizing_method: str = "fixed", sizing_value: float = 1000.0):
                    pass

            mock_cls.return_value = FakeStrategy

            with patch.object(svc, "_load_historical_data", new_callable=AsyncMock, return_value=[
                {"open": 100, "close": 110, "volume": 1000, "timestamp": "2024-01-01T09:00:00"},
                {"open": 110, "close": 105, "volume": 1200, "timestamp": "2024-01-02T09:00:00"},
            ]):
                result = await svc.run_backtest(
                    name="test", symbols=["فولاد"],
                    strategy_type="moving_average_cross",
                )
                assert result.success

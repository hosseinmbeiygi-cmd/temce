"""Unit tests for backtesting/runner.BacktestRunner (audit D1).

Locks in the consolidation contract:
  - ``BacktestSimulator`` is the canonical engine and the runner is a faithful
    pass-through for it (same orders → same PnL).
  - Every engine (replay / hybrid / portfolio / legacy) is dispatched through
    the same result normalisation, so their outputs share one schema.
  - The orphaned ``SimulationEngine`` and legacy ``BacktestEngine`` emit
    deprecation warnings instead of being silently treated as first-class.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backtesting.engine.simulator import BacktestSimulator
from backtesting.runner import BacktestRunner
from backtesting.strategies.base import BaseStrategy
from backtesting.types import BacktestResult, EquityPoint, FillEvent, OrderEvent
from core.result import Result

SYMBOL = "فولاد"


# ── Minimal deterministic strategy ────────────────────────────────────────


class _BuyFirstBar(BaseStrategy):
    """Buy 10 units on the first bar at its close, then hold."""

    def __init__(self) -> None:
        self._bought = False

    def reset(self) -> None:
        self._bought = False

    def on_bar(self, bar: dict[str, Any]) -> list[Any]:
        if self._bought:
            return []
        self._bought = True
        return [
            OrderEvent(
                instrument_id=bar.get("instrument_id", SYMBOL),
                side="buy",
                quantity=10,
                price=float(bar.get("close", 100.0)),
                order_type="market",
            )
        ]


def _bars() -> list[dict[str, Any]]:
    return [
        {"instrument_id": SYMBOL, "close": 100.0, "timestamp": "2025-01-01T09:00:00"},
        {"instrument_id": SYMBOL, "close": 110.0, "timestamp": "2025-01-02T09:00:00"},
        {"instrument_id": SYMBOL, "close": 120.0, "timestamp": "2025-01-03T09:00:00"},
    ]


def _canned_result() -> BacktestResult:
    return BacktestResult(
        strategy_name="Canned",
        initial_capital=1_000_000_000,
        final_capital=1_010_000_000,
        total_return=10_000_000,
        total_return_pct=1.0,
        total_trades=1,
        trades=[],
        equity_curve=[
            EquityPoint(timestamp=datetime(2025, 1, 1, tzinfo=UTC), nav=1_000_000_000, cash=1_000_000_000, positions_value=0),
            EquityPoint(timestamp=datetime(2025, 1, 2, tzinfo=UTC), nav=1_005_000_000, cash=900_000_000, positions_value=105_000_000),
            EquityPoint(timestamp=datetime(2025, 1, 3, tzinfo=UTC), nav=1_010_000_000, cash=900_000_000, positions_value=110_000_000),
        ],
    )


# ── Runner parity (canonical engine) ─────────────────────────────────────


async def test_simulator_parity_via_runner() -> None:
    """The runner must be a faithful pass-through for BacktestSimulator —
    same orders, same data → identical final capital / trades."""
    runner = BacktestRunner()
    strategy = _BuyFirstBar()
    data = _bars()

    summary = await runner.run("simulator", strategy=strategy, data=data)
    direct = BacktestSimulator().run(_BuyFirstBar(), 1_000_000_000, data)

    assert direct.success
    bt = direct.unwrap()
    assert summary["final_capital"] == pytest.approx(bt.final_capital)
    assert summary["total_trades"] == bt.total_trades
    assert len(summary["equity_points"]) == len(bt.equity_curve)
    assert summary["engine"] == "simulator"


async def test_runner_accepts_engine_instance() -> None:
    runner = BacktestRunner()
    summary = await runner.run(BacktestSimulator(), strategy=_BuyFirstBar(), data=_bars())
    assert summary["engine"] == "simulator"
    assert summary["total_trades"] == 1


async def test_runner_result_schema() -> None:
    summary = await BacktestRunner().run("simulator", strategy=_BuyFirstBar(), data=_bars())
    expected_keys = {
        "engine", "strategy_name", "initial_capital", "final_capital",
        "total_return", "total_return_pct", "total_trades",
        "sharpe_ratio", "sortino_ratio", "max_drawdown_pct", "cagr",
        "win_rate", "profit_factor", "volatility", "equity_points",
    }
    assert set(summary) == expected_keys
    assert summary["strategy_name"] == "_BuyFirstBar"
    assert isinstance(summary["equity_points"], list) and len(summary["equity_points"]) == 3


# ── Hybrid normalisation ─────────────────────────────────────────────────


async def test_hybrid_result_normalized_to_backtest_result(monkeypatch: pytest.MonkeyPatch) -> None:
    from backtesting.hybrid.hybrid_simulator import HybridMarketSimulator, HybridResult

    fill = FillEvent(
        order_id="o1", instrument_id=SYMBOL, side="buy",
        quantity=10, price=100.0, commission=400.0,
    )
    hybrid_result = HybridResult(fills=[fill])

    engine = HybridMarketSimulator()
    monkeypatch.setattr(engine, "run", AsyncMock(return_value=Result.ok(hybrid_result)))

    summary = await BacktestRunner().run(
        engine, initial_capital=1_000_000_000
    )

    assert summary["engine"] == "hybrid"
    # nav = initial + gross(1000) - costs(400) = 1_000_000_600
    assert summary["final_capital"] == pytest.approx(1_000_000_600)
    assert summary["total_trades"] == 1


# ── Failure propagation ──────────────────────────────────────────────────


async def test_engine_failure_propagates_as_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from backtesting.hybrid.hybrid_simulator import HybridMarketSimulator

    engine = HybridMarketSimulator()
    monkeypatch.setattr(engine, "run", AsyncMock(return_value=Result.fail("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        await BacktestRunner().run(engine, initial_capital=1_000_000_000)


async def test_runner_unknown_engine_raises() -> None:
    with pytest.raises(ValueError, match="unknown backtest engine"):
        await BacktestRunner().run("not-an-engine")


# ── Deprecation (orphaned SimulationEngine / legacy BacktestEngine) ──────


def test_simulation_engine_constructor_warns() -> None:
    from backtesting.engine.simulation_engine import SimulationEngine

    with pytest.warns(DeprecationWarning, match="deprecated"):
        SimulationEngine()


async def test_runner_deprecates_simulation_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    from backtesting.engine.simulation_engine import SimulationEngine

    monkeypatch.setattr(
        SimulationEngine, "run", AsyncMock(return_value=Result.ok(_canned_result()))
    )

    with pytest.warns(DeprecationWarning, match="deprecated"):
        summary = await BacktestRunner().run("simulation")

    assert summary["engine"] == "simulation"
    assert summary["final_capital"] == pytest.approx(1_010_000_000)


async def test_runner_deprecates_backtest_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    from backtesting.engine.backtest_engine import BacktestEngine

    monkeypatch.setattr(
        BacktestEngine, "run", AsyncMock(return_value=_canned_result())
    )

    with pytest.warns(DeprecationWarning, match="deprecated"):
        summary = await BacktestRunner().run("backtest_engine", strategy=_BuyFirstBar(), data=_bars())

    assert summary["engine"] == "backtest_engine"
    assert summary["total_trades"] == 1


# ── Registry ─────────────────────────────────────────────────────────────


def test_list_engines_marks_canonical_and_deprecated() -> None:
    engines = {e["name"]: e for e in BacktestRunner.list_engines()}
    assert engines["simulator"]["canonical"] is True
    assert engines["simulation"]["deprecated"] is True
    assert engines["backtest_engine"]["deprecated"] is True
    assert engines["replay"]["deprecated"] is False

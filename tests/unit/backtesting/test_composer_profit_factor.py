"""Composer metrics must use the canonical Profit Factor and include costs.

The composer feeds ``QualityFilter`` (stage 6: PF ≥ 1.2). It used to divide
average win by average loss, ignored commissions, and matched at most one buy
lot per sell — so the gate could reject a profitable strategy or accept one
whose gross PnL was negative.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backtesting.composer.phase_runner import PhaseRunner
from backtesting.composer.quality_filter import QualityFilter
from backtesting.types import BacktestResult, EquityPoint, FillEvent
from domain.common.enum_types import OrderSide


def _fill(side: str, qty: int, price: float, commission: float = 0.0, i: int = 0) -> FillEvent:
    return FillEvent(
        order_id=f"f{i}",
        instrument_id="X",
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        quantity=qty,
        price=price,
        commission=commission,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _result(trades: list[FillEvent]) -> BacktestResult:
    equity = [
        EquityPoint(timestamp=datetime(2026, 1, 1, tzinfo=UTC), nav=1_000_000_000.0, cash=0.0, positions_value=0.0),
        EquityPoint(timestamp=datetime(2026, 1, 2, tzinfo=UTC), nav=1_050_000_000.0, cash=0.0, positions_value=0.0),
    ]
    return BacktestResult(
        strategy_name="t", initial_capital=1_000_000_000.0,
        final_capital=1_050_000_000.0, equity_curve=equity, trades=trades,
    )


def test_profit_factor_is_gross_wins_over_gross_losses() -> None:
    """10 small wins (1,000 total) vs one 500 loss → PF 2.0, not 0.2."""
    fills: list[FillEvent] = []
    for i in range(10):
        fills.append(_fill("buy", 100, 1000.0, 0.0, 2 * i))
        fills.append(_fill("sell", 100, 1001.0, 0.0, 2 * i + 1))
    fills.append(_fill("buy", 100, 1000.0, 0.0, 100))
    fills.append(_fill("sell", 100, 995.0, 0.0, 101))

    metrics = PhaseRunner()._compute_metrics(_result(fills), 1_000_000_000.0)

    assert metrics["profit_factor"] == pytest.approx(2.0)
    assert metrics["avg_win"] == pytest.approx(100.0)
    assert metrics["avg_loss"] == pytest.approx(500.0)

    # The old average-based figure (0.2) failed stage 6 despite a 2.0 PF.
    gate_metrics = {
        **metrics,
        "total_return_pct": 5.0, "max_drawdown_pct": 5.0,
        "sharpe_ratio": 1.0, "win_rate": 50.0,
    }
    assert QualityFilter().should_keep(gate_metrics)[0] is True


def test_all_winning_strategy_has_a_passing_profit_factor() -> None:
    fills: list[FillEvent] = []
    for i in range(5):
        fills.append(_fill("buy", 100, 1000.0, 0.0, 2 * i))
        fills.append(_fill("sell", 100, 1010.0, 0.0, 2 * i + 1))

    metrics = PhaseRunner()._compute_metrics(_result(fills), 1_000_000_000.0)

    assert metrics["profit_factor"] > 1.2
    assert metrics["win_rate"] == pytest.approx(100.0)


def test_profit_factor_includes_commissions() -> None:
    fills = [
        _fill("buy", 100, 1000.0, 20.0, 0),
        _fill("sell", 100, 1100.0, 25.0, 1),
    ]

    metrics = PhaseRunner()._compute_metrics(_result(fills), 1_000_000_000.0)

    # (1100-1000)*100 - 20 - 25 = 9955; no losses → floor of 1.0
    assert metrics["avg_win"] == pytest.approx(9955.0)
    assert metrics["profit_factor"] == pytest.approx(9955.0)


def test_partial_lots_are_split_across_sells() -> None:
    """A sell larger than one buy lot must consume several lots (FIFO)."""
    fills = [
        _fill("buy", 50, 100.0, 0.0, 0),
        _fill("buy", 50, 200.0, 0.0, 1),
        _fill("sell", 100, 300.0, 0.0, 2),
    ]

    metrics = PhaseRunner()._compute_metrics(_result(fills), 1_000_000_000.0)

    # round_trip_pnls books one outcome per matched lot:
    # (300-100)*50 = 10,000 and (300-200)*50 = 5,000 → avg 7,500, PF 15,000.
    assert metrics["avg_win"] == pytest.approx(7_500.0)
    assert metrics["profit_factor"] == pytest.approx(15_000.0)

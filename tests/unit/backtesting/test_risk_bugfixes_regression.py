"""Unit regression tests for backtest BUG FIXes documented in README.

Covers the fixes applied in the backtesting engine:
  #1  Stop Loss percentage check against entry price      (backtesting/risk/stop_loss.py:66)
  #2  Take Profit percentage check against entry price     (backtesting/risk/take_profit.py:44)
  #5  Zero volatility → fall back to max position          (backtesting/risk/position_sizing.py:19)
  #6  Standard Kelly formula for fractional payoffs        (backtesting/risk/position_sizing.py:27)
  #9  Calmar ratio — max_drawdown already a percentage     (backtesting/metrics/risk_metrics.py:28)
  #10 Omega ratio — divide-by-zero clamp                   (backtesting/metrics/risk_metrics.py:40)
  #11 All-positive returns — Sortino/tail-ratio robustness (backtesting/metrics/risk_metrics.py:50)
  #20 Sample std dev (ddof=1) for return series            (backtesting/metrics/risk_metrics.py:16,56)

These are pure unit tests — no DB, no async I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np
import pytest

from backtesting.metrics.risk_metrics import RiskMetrics
from backtesting.risk.position_sizing import PositionSizing
from backtesting.risk.stop_loss import StopLoss
from backtesting.risk.take_profit import TakeProfit
from backtesting.types import BacktestResult, EquityPoint, PositionState


# ── Shared helpers ────────────────────────────────────────────────────────────


def _position(price: float, qty: int = 100) -> PositionState:
    return PositionState(instrument_id="X", quantity=qty, avg_price=price)


def _event(price: float, entry_price: float | None = None) -> SimpleNamespace:
    payload = {"price": price}
    if entry_price is not None:
        payload["entry_price"] = entry_price
    return SimpleNamespace(instrument_id="X", payload=payload)


def _equity(navs: list[float]) -> list[EquityPoint]:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    return [EquityPoint(timestamp=ts, nav=n, cash=0.0, positions_value=n) for n in navs]


def _result(navs: list[float], metrics: dict | None = None) -> BacktestResult:
    return BacktestResult(
        equity_curve=_equity(navs),
        metrics=metrics or {},
    )


# ── BUG FIX #1: Stop Loss percentage vs entry price ──────────────────────────


class TestStopLossPercentageRegression:
    """BUG FIX #1 — percentage stop must be checked against the ENTRY price."""

    def test_percentage_stop_uses_entry_price(self):
        sl = StopLoss(pct=2.0)  # 2% stop
        pos = _position(price=100.0)
        # Stop = 100 * (1 - 0.02) = 98. Price 97 → triggered
        assert sl.should_stop_out(pos, current_price=97.0) is True
        # Price 99 (> stop 98) → NOT triggered
        assert sl.should_stop_out(pos, current_price=99.0) is False

    def test_is_triggered_percentage_uses_entry_price(self):
        sl = StopLoss(pct=2.0)
        sl.set_entry_price("X", 100.0)
        # 97 <= 98 → trigger
        assert sl.is_triggered({"X": 100}, _event(price=97.0)) is True
        # 99 > 98 → no trigger
        assert sl.is_triggered({"X": 100}, _event(price=99.0)) is False

    def test_is_triggered_falls_back_to_payload_entry_price(self):
        """When set_entry_price was never called, use event payload entry_price."""
        sl = StopLoss(pct=2.0)
        # entry not in _entry_prices → falls back to payload["entry_price"]
        assert sl.is_triggered({"X": 100}, _event(price=97.0, entry_price=100.0)) is True
        assert sl.is_triggered({"X": 100}, _event(price=99.0, entry_price=100.0)) is False

    def test_zero_quantity_never_triggers(self):
        sl = StopLoss(pct=2.0)
        assert sl.is_triggered({"X": 0}, _event(price=1.0)) is False
        assert sl.should_stop_out(_position(price=100.0, qty=0), current_price=1.0) is False

    def test_invalid_price_never_triggers(self):
        sl = StopLoss(pct=2.0)
        sl.set_entry_price("X", 100.0)
        # is_triggered() guards non-positive prices
        assert sl.is_triggered({"X": 100}, _event(price=0.0)) is False
        assert sl.is_triggered({"X": 100}, _event(price=-5.0)) is False

    def test_absolute_mode_wins_over_percentage(self):
        sl = StopLoss(pct=2.0, absolute=95.0)
        pos = _position(price=100.0)
        # absolute 95 — price 96 (above pct stop 98, above absolute 95) → NOT triggered
        assert sl.should_stop_out(pos, current_price=96.0) is False
        # price 94 <= absolute 95 → triggered
        assert sl.should_stop_out(pos, current_price=94.0) is True

    def test_get_stop_price_percentage_vs_entry(self):
        sl = StopLoss(pct=2.0)
        assert sl.get_stop_price(entry_price=100.0) == pytest.approx(98.0)
        sl_abs = StopLoss(pct=2.0, absolute=95.0)
        assert sl_abs.get_stop_price(entry_price=100.0) == 95.0

    def test_should_stop_out_nonpositive_price_documented_behavior(self):
        """Document current behavior: should_stop_out() lacks the non-positive
        price guard that is_triggered() has (price 0 → 0 <= stop → True).
        Kept as a regression marker so the inconsistency is explicit.
        """
        sl = StopLoss(pct=2.0)
        pos = _position(price=100.0)
        assert sl.should_stop_out(pos, current_price=0.0) is True  # no guard here (see is_triggered)

    def test_trailing_stop_ratchets_up(self):
        sl = StopLoss(pct=5.0, trailing=True)
        pos = _position(price=100.0)
        # Price rises to 110 → new stop = 110 * 0.95 = 104.5
        assert sl.should_stop_out(pos, current_price=110.0) is False
        # 105 still above 104.5 → no trigger
        assert sl.should_stop_out(pos, current_price=105.0) is False
        # 104 <= 104.5 → trigger
        assert sl.should_stop_out(pos, current_price=104.0) is True


# ── BUG FIX #2: Take Profit percentage vs entry price ────────────────────────


class TestTakeProfitPercentageRegression:
    """BUG FIX #2 — percentage take-profit must be checked against ENTRY price."""

    def test_percentage_target_uses_entry_price(self):
        tp = TakeProfit(pct=5.0)
        pos = _position(price=100.0)
        # Target = 100 * 1.05 = 105. 106 → triggered
        assert tp.should_take_profit(pos, current_price=106.0) is True
        # 104 < 105 → NOT triggered
        assert tp.should_take_profit(pos, current_price=104.0) is False

    def test_is_triggered_percentage_uses_entry_price(self):
        tp = TakeProfit(pct=5.0)
        tp.set_entry_price("X", 100.0)
        assert tp.is_triggered({"X": 100}, _event(price=106.0)) is True
        assert tp.is_triggered({"X": 100}, _event(price=104.0)) is False

    def test_is_triggered_falls_back_to_payload_entry_price(self):
        tp = TakeProfit(pct=5.0)
        assert tp.is_triggered({"X": 100}, _event(price=106.0, entry_price=100.0)) is True
        assert tp.is_triggered({"X": 100}, _event(price=104.0, entry_price=100.0)) is False

    def test_absolute_mode(self):
        tp = TakeProfit(pct=5.0, absolute=110.0)
        pos = _position(price=100.0)
        assert tp.should_take_profit(pos, current_price=109.0) is False
        assert tp.should_take_profit(pos, current_price=110.0) is True

    def test_zero_quantity_never_triggers(self):
        tp = TakeProfit(pct=5.0)
        assert tp.is_triggered({"X": 0}, _event(price=1000.0)) is False

    def test_get_target_price_percentage_vs_entry(self):
        tp = TakeProfit(pct=5.0)
        assert tp.get_target_price(entry_price=100.0) == pytest.approx(105.0)
        tp_abs = TakeProfit(pct=5.0, absolute=110.0)
        assert tp_abs.get_target_price(entry_price=100.0) == 110.0


# ── BUG FIX #5: Zero volatility → no division by zero ────────────────────────


class TestPositionSizingZeroVolatility:
    """BUG FIX #5 — volatility=0 must not raise; fall back to max position."""

    def test_zero_volatility_returns_max_position(self):
        ps = PositionSizing(risk_per_trade_pct=1.0, max_position_pct=10.0)
        capital = 1_000_000.0
        price = 1_000.0
        # max_capital = 100_000 → qty = 100
        qty = ps.compute_quantity(capital=capital, price=price, volatility=0.0)
        assert qty == 100

    def test_zero_volatility_matches_max_position_calculation(self):
        ps = PositionSizing(risk_per_trade_pct=1.0, max_position_pct=25.0)
        capital = 10_000_000.0
        price = 2_500.0
        expected = int(capital * 0.25 / price)
        assert ps.compute_quantity(capital=capital, price=price, volatility=0.0) == expected

    def test_positive_volatility_uses_risk_budget(self):
        ps = PositionSizing(risk_per_trade_pct=1.0, max_position_pct=100.0)
        capital = 1_000_000.0
        price = 1_000.0
        vol = 0.01  # 1%
        # risk qty = (1% * 1M) / (1000 * 0.01) = 10000 / 10 = 1000
        qty = ps.compute_quantity(capital=capital, price=price, volatility=vol)
        assert qty == 1000


# ── BUG FIX #6: Standard Kelly formula ───────────────────────────────────────


class TestPositionSizingKelly:
    """BUG FIX #6 — standard Kelly: f* = p - q*(avg_loss/avg_win), clamped [0, max]."""

    def test_kelly_standard_formula(self):
        ps = PositionSizing(max_position_pct=100.0)  # cap = 1.0
        # p=0.6, q=0.4, avg_loss/avg_win = 0.05/0.1 = 0.5 → f* = 0.6 - 0.4*0.5 = 0.4
        f = ps.compute_kelly_fraction(win_rate=0.6, avg_win=0.1, avg_loss=0.05)
        assert f == pytest.approx(0.4, abs=1e-9)

    def test_kelly_edge_case_positive_edge(self):
        ps = PositionSizing(max_position_pct=100.0)
        # p=0.5, q=0.5, ratio=0.5/0.5=1.0 → f* = 0.5 - 0.5 = 0.0
        assert ps.compute_kelly_fraction(win_rate=0.5, avg_win=0.5, avg_loss=0.5) == pytest.approx(0.0, abs=1e-9)
        # p=0.6, q=0.4, ratio=0.4/0.6 → f* = 0.6 - 0.4*(2/3) = 0.6 - 0.2667 = 0.3333
        f = ps.compute_kelly_fraction(win_rate=0.6, avg_win=0.6, avg_loss=0.4)
        assert f == pytest.approx(1.0 / 3.0, abs=1e-9)

    def test_kelly_clamped_to_max_position(self):
        ps = PositionSizing(max_position_pct=10.0)  # cap = 0.10
        f = ps.compute_kelly_fraction(win_rate=0.8, avg_win=0.2, avg_loss=0.05)
        # f* = 0.8 - 0.2*0.25 = 0.75 → clamped to 0.10
        assert f == 0.10

    def test_kelly_negative_edge_clamped_to_zero(self):
        ps = PositionSizing(max_position_pct=100.0)
        # p=0.3, q=0.7, ratio=0.5 → f* = 0.3 - 0.35 = -0.05 → clamped to 0
        assert ps.compute_kelly_fraction(win_rate=0.3, avg_win=0.1, avg_loss=0.05) == 0.0

    def test_kelly_invalid_inputs_return_zero(self):
        ps = PositionSizing()
        assert ps.compute_kelly_fraction(win_rate=0.5, avg_win=0.0, avg_loss=0.05) == 0.0
        assert ps.compute_kelly_fraction(win_rate=0.5, avg_win=0.1, avg_loss=0.0) == 0.0


# ── BUG FIX #9: Calmar ratio units ───────────────────────────────────────────


class TestRiskMetricsCalmar:
    """BUG FIX #9 — max_drawdown in metrics is already a percentage."""

    def test_calmar_uses_percentage_drawdown_directly(self):
        # navs: peak 120 → trough 100 → drawdown = 16.67%
        result = _result([100.0, 120.0, 100.0, 120.0], metrics={"max_drawdown": 16.6667})
        metrics = RiskMetrics.compute(result)
        returns = np.diff([100.0, 120.0, 100.0, 120.0]) / np.array([100.0, 120.0, 100.0, 120.0])[:-1]
        avg_ret = float(np.mean(returns)) * 252
        assert metrics["calmar_ratio"] == pytest.approx(avg_ret / 16.6667, rel=1e-6)

    def test_calmar_zero_drawdown_returns_zero(self):
        result = _result([100.0, 110.0, 120.0], metrics={"max_drawdown": 0.0})
        metrics = RiskMetrics.compute(result)
        assert metrics["calmar_ratio"] == 0.0


# ── BUG FIX #10: Omega ratio clamp ───────────────────────────────────────────


class TestRiskMetricsOmega:
    """BUG FIX #10 — Omega ratio must not divide by zero (clamp to 9999)."""

    def test_omega_all_gains_clamped(self):
        # Strictly increasing navs → every return is a gain → losses = 0 → clamp
        result = _result([100.0, 110.0, 121.0])
        metrics = RiskMetrics.compute(result)
        assert metrics["omega_ratio"] == 9999.0

    def test_omega_normal_ratio(self):
        # Mixed returns → finite omega
        result = _result([100.0, 105.0, 99.0, 103.0])
        metrics = RiskMetrics.compute(result)
        assert 0.0 < metrics["omega_ratio"] < 9999.0


# ── BUG FIX #11: All-positive returns robustness ─────────────────────────────


class TestRiskMetricsAllPositiveReturns:
    """BUG FIX #11 — all-positive returns must not crash Sortino / tail ratio."""

    def test_all_positive_returns_no_crash(self):
        result = _result([100.0, 110.0, 121.0, 133.1])
        metrics = RiskMetrics.compute(result)
        assert "sortino_ratio" in metrics
        assert np.isfinite(metrics["sortino_ratio"])
        assert "tail_ratio" in metrics
        assert np.isfinite(metrics["tail_ratio"])

    def test_tail_ratio_clamped_when_no_downside(self):
        # Series with flat + rising periods → 5th percentile return == 0 → clamp
        result = _result([100.0, 100.0, 100.0, 110.0, 121.0])
        metrics = RiskMetrics.compute(result)
        assert metrics["tail_ratio"] == 9999.0


# ── BUG FIX #20: Sample std (ddof=1) ─────────────────────────────────────────


class TestRiskMetricsSampleStd:
    """BUG FIX #20 — volatility/skewness/kurtosis use ddof=1 sample std."""

    def test_volatility_uses_ddof1(self):
        navs = [100.0, 110.0, 99.0]
        returns = np.diff(navs) / np.array(navs[:-1])
        expected_vol = float(np.std(returns, ddof=1) * np.sqrt(252))
        result = _result(navs)
        metrics = RiskMetrics.compute(result)
        assert metrics["volatility"] == pytest.approx(expected_vol, rel=1e-9)
        # population std (ddof=0) would differ — prove we're NOT using it
        pop_vol = float(np.std(returns) * np.sqrt(252))
        assert metrics["volatility"] != pytest.approx(pop_vol, abs=1e-12)

    def test_skewness_uses_ddof1(self):
        navs = [100.0, 90.0, 110.0, 95.0, 115.0]
        returns = np.diff(navs) / np.array(navs[:-1])
        std_val = np.std(returns, ddof=1)
        expected_skew = float(((returns - np.mean(returns)) ** 3).mean() / (std_val ** 3))
        result = _result(navs)
        metrics = RiskMetrics.compute(result)
        assert metrics["skewness"] == pytest.approx(expected_skew, rel=1e-6)

    def test_short_series_no_crash(self):
        result = _result([100.0])  # single point
        metrics = RiskMetrics.compute(result)
        assert metrics["volatility"] == 0.0
        assert metrics["sharpe_ratio"] == 0.0

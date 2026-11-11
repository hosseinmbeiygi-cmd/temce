"""تست معیارهای کارایی/ریسک GoldDesk (pure)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.gold_desk.performance import (  # noqa: E402
    annualized_volatility_pct,
    concentration_pct,
    conditional_value_at_risk_pct,
    gold_silver_ratio,
    max_drawdown_pct,
    relative_to_benchmark_pct,
    sharpe_ratio,
    simple_returns,
    sortino_ratio,
    time_weighted_return_pct,
    total_return_pct,
    value_at_risk_pct,
)


def test_simple_returns_basic():
    assert simple_returns([100, 110, 99]) == pytest.approx([0.1, -0.1])


def test_total_return_pct():
    assert total_return_pct([100, 150]) == pytest.approx(50.0)
    assert total_return_pct([100]) is None
    assert total_return_pct([0, 10]) is None


def test_max_drawdown_pct():
    assert max_drawdown_pct([100, 120, 60, 90]) == pytest.approx(50.0)
    assert max_drawdown_pct([100, 110]) == pytest.approx(0.0)
    assert max_drawdown_pct([100]) is None


def test_volatility_annualizes():
    rets = [0.01, -0.01, 0.01, -0.01]
    vol = annualized_volatility_pct(rets, periods_per_year=252)
    assert vol is not None and vol > 0
    # انحراف معیار نمونه ≈ 0.011547
    assert vol == pytest.approx(0.011547 * math.sqrt(252) * 100, rel=1e-3)
    assert annualized_volatility_pct([0.01]) is None


def test_sharpe_none_when_no_variance():
    assert sharpe_ratio([0.01, 0.01, 0.01]) is None


def test_sharpe_positive_for_positive_excess():
    rets = [0.02, -0.01, 0.03, -0.01]
    s = sharpe_ratio(rets)
    assert s is not None and s > 0


def test_sortino_none_without_downside():
    assert sortino_ratio([0.01, 0.02, 0.03]) is None


def test_sortino_positive_for_positive_excess_with_downside():
    rets = [0.05, -0.01, 0.05, -0.01]
    s = sortino_ratio(rets)
    assert s is not None and s > 0


def test_gold_silver_ratio():
    assert gold_silver_ratio(4000.0, 50.0) == pytest.approx(80.0)
    assert gold_silver_ratio(4000.0, 0.0) is None


def test_relative_to_benchmark():
    assert relative_to_benchmark_pct(12.0, 9.0) == pytest.approx(3.0)
    assert relative_to_benchmark_pct(None, 9.0) is None
    assert relative_to_benchmark_pct(12.0, None) is None


def test_time_weighted_return_ignores_flows():
    # ارزش دو برابر شده ولی همهٔ رشد از واریز ۵۰ است → بازده صفر
    assert time_weighted_return_pct([100.0, 150.0], [0.0, 50.0]) == pytest.approx(0.0)
    # رشد واقعی ۱۰۰٪
    assert time_weighted_return_pct([100.0, 200.0], [0.0, 0.0]) == pytest.approx(100.0)
    assert time_weighted_return_pct([100.0], [0.0]) is None
    assert time_weighted_return_pct([100.0, 200.0], [0.0]) is None


def test_value_at_risk_positive_loss_convention():
    rets = [-0.10, -0.08, -0.06] + [0.01] * 17
    assert value_at_risk_pct(rets, 0.95) == pytest.approx(8.0)
    assert conditional_value_at_risk_pct(rets, 0.95) == pytest.approx(10.0)
    assert value_at_risk_pct([0.01] * 5) is None  # نمونهٔ کم


def test_concentration_pct():
    assert concentration_pct([50.0, 30.0, 20.0]) == pytest.approx(50.0)
    assert concentration_pct([]) is None
    assert concentration_pct([0.0, 0.0]) is None

"""Tests for the options backtest + ML services."""
import math

from services.options_backtest_service import HistoryBar, OptionsBacktestService
from services.options_ml_service import OptionsMLService


def _bars(n: int = 120, start: float = 100.0, drift: float = 0.002) -> list[HistoryBar]:
    bars, px = [], start
    for i in range(n):
        bars.append(HistoryBar(date=f"2024-01-{(i % 28) + 1:02d}", close=px))
        px *= 1 + drift
    return bars


def test_backtest_report_metrics():
    svc = OptionsBacktestService(entry_filter="always", days_to_expiry=30)
    rep = svc.run(_bars())
    assert rep.metrics.n_trades > 0
    assert 0.0 <= rep.metrics.win_rate <= 100.0
    assert len(rep.equity_curve) == len(rep.equity_dates) == rep.metrics.n_trades + 1
    assert all(math.isfinite(v) for v in rep.equity_curve)
    assert rep.metrics.max_drawdown >= 0
    assert math.isfinite(rep.metrics.sharpe_ratio)


def test_backtest_momentum_runs():
    svc = OptionsBacktestService(entry_filter="momentum", days_to_expiry=20)
    rep = svc.run(_bars())
    assert rep.metrics.n_trades >= 0
    assert all(math.isfinite(t.pnl_net) for t in rep.trades)


def test_backtest_unknown_strategy_raises():
    try:
        OptionsBacktestService(entry_filter="nope")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_expected_move_bands_ordered():
    svc = OptionsMLService(n_paths=5000, seed=1)
    r = svc.expected_move(spot=100.0, sigma=0.30, days_to_expiry=30)
    assert r.lower_95 < r.lower_68 < r.median_terminal < r.upper_68 < r.upper_95
    assert r.analytic_lower_68 < 100.0 < r.analytic_upper_68
    assert all(math.isfinite(v) for v in (
        r.lower_68, r.upper_68, r.lower_95, r.upper_95,
        r.median_terminal, r.mean_terminal))


def test_probability_above_sane():
    svc = OptionsMLService(n_paths=5000, seed=1)
    p = svc.probability_above(100.0, 0.30, 30, 100.0)
    assert 0.0 <= p <= 1.0


def test_max_pain_known_case():
    svc = OptionsMLService()
    r = svc.max_pain(
        strikes=[90.0, 100.0, 110.0],
        call_oi=[100.0, 10.0, 10.0],
        put_oi=[10.0, 10.0, 100.0],
    )
    assert r.max_pain_strike == 100.0
    assert r.total_payout_at_max_pain == min(r.payout_by_strike.values())

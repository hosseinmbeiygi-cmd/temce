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
    assert math.isfinite(rep.metrics.profit_factor)
    assert math.isfinite(rep.metrics.annualized_return_pct)
    assert {t.exit_reason for t in rep.trades} <= {"stop", "target", "expiry"}


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


def test_garch_forecast_sane():
    import numpy as np

    rng = np.random.default_rng(7)
    rets = list(rng.normal(0.0, 0.02, 250))
    f = OptionsMLService.garch_forecast(rets, horizon_days=30)
    assert math.isfinite(f.realized_vol_annual) and f.realized_vol_annual > 0
    assert 0.0 < f.garch_alpha + f.garch_beta < 1.0
    assert f.n_observations == 250
    # Few observations → sample-std fallback, no crash.
    f2 = OptionsMLService.garch_forecast([0.01, -0.02, 0.015], horizon_days=10)
    assert math.isfinite(f2.realized_vol_annual)


def test_touch_probabilities_ordered():
    svc = OptionsMLService(n_paths=5000, seed=3)
    t = svc.touch_probabilities(100.0, 0.30, 30, 115.0, 85.0)
    assert 0.0 <= t.probability_of_profit <= 1.0
    assert 0.0 <= t.probability_of_touch_upper <= 1.0
    assert 0.0 <= t.probability_of_touch_lower <= 1.0
    # Touching is always at least as likely as expiring beyond.
    assert t.probability_of_touch_upper >= t.probability_of_profit - 0.02


def test_put_call_ratio():
    assert OptionsMLService.put_call_ratio(100.0, 150.0) == 1.5
    assert OptionsMLService.put_call_ratio(0.0, 150.0) == 0.0

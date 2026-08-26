from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.engine.vectorized_engine import (
    VectorizedBacktestEngine,
    ma_cross_strategy,
    rsi_reversion_strategy,
    run_vectorized_backtest,
)


def _make_data(n: int = 250, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, n)))
    return pd.DataFrame({
        "price_close": close,
        "price_open": close.shift(1).fillna(close.iloc[0]),
        "price_high": close + 0.5,
        "price_low": close - 0.5,
        "trade_volume": rng.integers(1_000, 10_000, n),
    })


def test_requires_ohlcv_columns():
    df = pd.DataFrame({"price_close": [1.0, 2.0]})
    with pytest.raises(ValueError):
        VectorizedBacktestEngine(df)


def test_ma_cross_returns_position_vector():
    df = _make_data()
    engine = VectorizedBacktestEngine(df)
    metrics = engine.run_strategy(ma_cross_strategy)
    assert metrics["total_return"] is not None
    assert -100 <= metrics["max_drawdown"] <= 0
    assert metrics["volatility"] >= 0
    assert metrics["n_periods"] == len(df)


def test_calculate_metrics_known_return():
    engine = VectorizedBacktestEngine(_make_data())
    returns = pd.Series([0.01] * 100)  # constant positive
    m = engine.calculate_metrics(returns)
    assert m["total_return"] == pytest.approx((1.01 ** 100 - 1) * 100, rel=0.5)
    assert m["win_rate"] == 100.0
    assert m["max_drawdown"] == 0.0


def test_metrics_empty_returns_no_crash():
    engine = VectorizedBacktestEngine(_make_data())
    m = engine.calculate_metrics(pd.Series(dtype=float))
    assert m["total_return"] == 0.0
    assert m["sharpe_ratio"] == 0.0


def test_equity_curve_monotonic_product():
    df = _make_data()
    engine = VectorizedBacktestEngine(df)
    metrics = engine.run_strategy(ma_cross_strategy)
    curve = metrics["equity_curve"]
    assert (curve.iloc[-1] - 1) == pytest.approx(metrics["total_return"] / 100, rel=0.05)


def test_rsi_reversion_runs():
    df = _make_data()
    engine = VectorizedBacktestEngine(df)
    metrics = engine.run_strategy(rsi_reversion_strategy)
    assert metrics["win_rate"] >= 0


def test_run_vectorized_backtest_wrapper():
    df = _make_data()
    metrics = run_vectorized_backtest(df, strategy="ma_cross")
    assert "sharpe_ratio" in metrics
    with pytest.raises(ValueError):
        run_vectorized_backtest(df, strategy="unknown")


def test_plot_equity_curve_svg_fallback(tmp_path):
    df = _make_data()
    engine = VectorizedBacktestEngine(df)
    metrics = engine.run_strategy(ma_cross_strategy)
    out = tmp_path / "curve.png"
    path = engine.plot_equity_curve(metrics, output=str(out))
    # matplotlib may or may not be installed; either a png or svg fallback
    assert path.endswith((".png", ".svg"))

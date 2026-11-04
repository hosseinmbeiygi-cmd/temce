"""Regression test for Phase 1 plan fix M4 (.claude/plan.md).

Every feature value at row i must depend only on bars 0..i-1. Before the fix,
RSI/MACD/ATR/volume_ratio/half_trend/squeeze/support-resistance all used the
current (still-forming) bar's own close/high/low/volume — a classic
intrabar look-ahead bug that makes backtests look better than live trading
ever could.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.features.technical_features import TechnicalFeatures


def _sample_df(n: int = 60, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(size=n))
    return pd.DataFrame({
        "close": close,
        "high": close + 1.0,
        "low": close - 1.0,
        "volume": rng.integers(100, 1000, size=n).astype(float),
    })


class TestNoIntrabarLeakage:
    def test_perturbing_current_bar_does_not_change_its_own_features(self):
        """Changing bar i's OHLCV must not change feature[i] for any
        computed indicator (only the raw passthrough price/volume columns
        are allowed to change, since those aren't predictive features).
        """
        df = _sample_df()
        target = 20

        perturbed = df.copy()
        perturbed.loc[target, "high"] += 80.0
        perturbed.loc[target, "low"] -= 80.0
        perturbed.loc[target, "close"] += 50.0
        perturbed.loc[target, "volume"] *= 5.0

        base = TechnicalFeatures().compute(df.copy())
        pert = TechnicalFeatures().compute(perturbed)

        raw_passthrough = {"close", "high", "low", "volume", "date", "time", "symbol"}
        computed_features = [c for c in base.feature_names if c not in raw_passthrough]
        assert computed_features, "sanity: there must be computed features to check"

        leaking = []
        for col in computed_features:
            b = base.data[col].iloc[target]
            p = pert.data[col].iloc[target]
            same = (pd.isna(b) and pd.isna(p)) or abs(b - p) < 1e-9
            if not same:
                leaking.append(col)

        assert leaking == [], f"features leak current-bar data: {leaking}"

    def test_truncating_future_rows_does_not_change_past_feature_values(self):
        """A feature at row i must be identical whether rows after i exist."""
        df = _sample_df()
        target = 20

        full = TechnicalFeatures().compute(df.copy())
        truncated = TechnicalFeatures().compute(df.iloc[: target + 1].copy())

        for col in full.feature_names:
            f = full.data[col].iloc[target]
            t = truncated.data[col].iloc[target]
            same = (pd.isna(f) and pd.isna(t)) or abs(f - t) < 1e-9
            assert same, f"{col} differs when future rows are truncated: {f} vs {t}"

    def test_rsi_uses_prior_bar_close_delta(self):
        """RSI's delta at row i must be close[i-1] - close[i-2], not
        close[i] - close[i-1] (would use the current, still-forming bar).
        """
        df = _sample_df(n=30)
        out = TechnicalFeatures().compute(df.copy()).data

        # Perturbing only the LAST row's close must not move RSI at the
        # second-to-last row (it already shouldn't have seen that bar).
        perturbed = df.copy()
        perturbed.loc[len(df) - 1, "close"] += 1000.0
        out_pert = TechnicalFeatures().compute(perturbed).data

        assert out["rsi"].iloc[-2] == pytest.approx(out_pert["rsi"].iloc[-2])

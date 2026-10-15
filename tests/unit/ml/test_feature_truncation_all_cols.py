"""Task 1: truncation invariance for EVERY feature column.

Feature at bar t computed on full data must equal feature at bar t computed
on data truncated at t. Any column that differs has look-ahead bias.
"""
import pandas as pd


def _sample_df(n=120):
    import numpy as np

    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame(
        {
            "close": close,
            "high": close + rng.uniform(0, 1, n),
            "low": close - rng.uniform(0, 1, n),
            "volume": rng.integers(500, 2000, n).astype(float),
        }
    )


def test_truncation_invariance_all_columns():
    from ml.features.technical_features import TechnicalFeatures

    df = _sample_df()
    full = TechnicalFeatures().compute(df).data
    leaking: dict[int, list[str]] = {}
    for t in [30, 60, 90, 119]:
        trunc = TechnicalFeatures().compute(df.iloc[: t + 1]).data
        bad = []
        for col in full.columns:
            if col in ("date", "time", "symbol"):
                continue
            b = full[col].iloc[t]
            p = trunc[col].iloc[t]
            same = (pd.isna(b) and pd.isna(p)) or abs(float(b) - float(p)) < 1e-9
            if not same:
                bad.append(f"{col}(full={b:.6g} trunc={p:.6g})")
        if bad:
            leaking[t] = bad
    assert leaking == {}, f"look-ahead columns differ under truncation: {leaking}"

"""Task 1 (upgraded): truncation invariance on >=1500 bars, >=10 cut points.

- Cuts include points beyond the longest indicator warm-up (SMA/rolling 20,
  ewm span 26 → warm-up ~26+ bars; cuts at 25..1499 cover pre/post warm-up).
- NaNs are NEVER silently dropped: per cut we print non-NaN column counts
  (full vs truncated) and treat NaN-vs-value as a mismatch.
"""
import pandas as pd

N = 1600
CUTS = [10, 25, 26, 30, 50, 100, 200, 400, 800, 1200, 1499, 1599]


def _sample_df(n=N):
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


def test_truncation_invariance_large_all_columns():
    from ml.features.technical_features import TechnicalFeatures

    df = _sample_df()
    full = TechnicalFeatures().compute(df).data
    assert len(full) >= 1500
    leaking: dict[int, list[str]] = {}
    for t in CUTS:
        trunc = TechnicalFeatures().compute(df.iloc[: t + 1]).data
        full_nonnan = int(full.iloc[t].notna().sum())
        trunc_nonnan = int(trunc.iloc[t].notna().sum())
        print(f"cut t={t}: non-NaN cols full={full_nonnan} trunc={trunc_nonnan}")
        bad = []
        for col in full.columns:
            if col in ("date", "time", "symbol"):
                continue
            b = full[col].iloc[t]
            p = trunc[col].iloc[t]
            bn, pn = pd.isna(b), pd.isna(p)
            if bn and pn:
                continue  # both NaN — consistent, counted above
            if bn != pn or abs(float(b) - float(p)) > 1e-9:
                bad.append(f"{col}(full={b} trunc={p})")
        if bad:
            leaking[t] = bad
    assert leaking == {}, f"look-ahead columns differ under truncation: {leaking}"

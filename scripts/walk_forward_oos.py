"""Walk-forward out-of-sample backtest for one symbol — per-fold reporting.

For each fold: train a classifier on the train block ONLY (features are
truncation-invariant, labels use an explicit horizon, gap=horizon), evaluate
on the test block, and report per-fold accuracy + strategy metrics
(Sharpe/MDD/WinRate/PF). Prints one JSON object: {folds: [...], summary}.

Usage:
    python scripts/walk_forward_oos.py --symbol جهش --start 1405-01-01 --end 1405-06-31
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.compare_backtest import load_crypto, load_tse_ticks  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fold_metrics(closes: list[float], positions: list[int]) -> dict:
    """Long/flat next-open strategy: position decided at t applies t->t+1."""
    rets = []
    for t in range(len(closes) - 1):
        r = closes[t + 1] / closes[t] - 1 if closes[t] else 0.0
        rets.append(positions[t] * r)
    rets = rets[: len(positions)]
    vol = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    sharpe = (sum(rets) / len(rets) / vol * math.sqrt(252)) if vol > 0 else 0.0
    eq, peak, mdd = 1.0, 1.0, 0.0
    for r in rets:
        eq *= 1 + r
        peak = max(peak, eq)
        mdd = min(mdd, (eq / peak - 1) * 100)
    wins = sum(1 for r in rets if r > 0)
    losses = sum(1 for r in rets if r < 0)
    gp = sum(r for r in rets if r > 0)
    gl = -sum(r for r in rets if r < 0)
    n = wins + losses
    return {
        "sharpe": round(sharpe, 4),
        "max_drawdown_pct": round(mdd, 2),
        "win_rate_pct": round(100 * wins / n, 1) if n else 0.0,
        "profit_factor": round(gp / gl, 4) if gl > 0 else (float("inf") if gp > 0 else 0.0),
        "n_days": len(rets),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--start", default="1400-01-01")
    ap.add_argument("--end", default="1499-12-29")
    ap.add_argument("--n-splits", type=int, default=4)
    ap.add_argument("--horizon", type=int, default=5)
    ap.add_argument("--data-root", default=REPO_ROOT)
    a = ap.parse_args()

    import numpy as _np
    import pandas as _pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    from core.seed import set_global_seed
    from ml.dataset_builder import DatasetBuilder
    from ml.features.technical_features import TechnicalFeatures

    set_global_seed(42)
    try:
        bars = load_tse_ticks(a.symbol, a.start, a.end, a.data_root)
    except (FileNotFoundError, ValueError):
        bars = [b for b in load_crypto(a.symbol, a.data_root) if a.start <= b["date"] <= a.end]
    if len(bars) < 100:
        raise SystemExit(json.dumps({"error": f"only {len(bars)} bars — need >=100"}))

    df = _pd.DataFrame([{"close": b["close"], "high": b["high"], "low": b["low"],
                         "volume": b.get("volume") or 0} for b in bars])
    feat = TechnicalFeatures().compute(df).data
    feature_cols = [c for c in feat.columns if c not in ("date", "time", "symbol")]
    X_all = feat[feature_cols].to_numpy(dtype=float)
    closes = [b["close"] for b in bars]
    raw_y = DatasetBuilder().make_target(closes, horizon=a.horizon)
    valid = [i for i, y in enumerate(raw_y) if y is not None]
    X, y = X_all[valid], _np.array([raw_y[i] for i in valid])

    gap = a.horizon
    tss = TimeSeriesSplit(n_splits=a.n_splits, gap=gap)
    folds = []
    for k, (tr, te) in enumerate(tss.split(X)):
        if len(tr) < 30 or len(te) < 5:
            continue
        # Pipeline: scaler fit on TRAIN fold only (never on test) — the
        # correct pattern for scaler/PCA/imputer/feature-selection.
        clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
        clf.fit(X[tr], y[tr])
        proba = clf.predict_proba(X[te])[:, 1]
        pred = (proba > 0.5).astype(int)
        acc = float((pred == y[te]).mean())
        m = fold_metrics([closes[valid[i]] for i in te], [int(p) for p in pred])
        folds.append({
            "fold": k,
            "train_start": bars[valid[tr[0]]]["date"] if "date" in bars[0] else valid[int(tr[0])],
            "train_end": bars[valid[tr[-1]]]["date"] if "date" in bars[0] else valid[int(tr[-1])],
            "test_start": bars[valid[te[0]]]["date"] if "date" in bars[0] else valid[int(te[0])],
            "test_end": bars[valid[te[-1]]]["date"] if "date" in bars[0] else valid[int(te[-1])],
            "n_train": len(tr),
            "n_test": len(te),
            "accuracy": round(acc, 4),
            **m,
        })
    summary = {}
    if folds:
        for key in ("accuracy", "sharpe", "max_drawdown_pct", "win_rate_pct", "profit_factor"):
            vals = [f[key] for f in folds if isinstance(f[key], (int, float))]
            summary[f"mean_{key}"] = round(sum(vals) / len(vals), 4) if vals else 0.0
    print(json.dumps({"symbol": a.symbol, "horizon": a.horizon, "gap": gap,
                      "folds": folds, "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()

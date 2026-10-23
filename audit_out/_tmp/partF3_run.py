"""Part F3 — label shuffle (30x) + canary feature leakage test on the exploratory model."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.getcwd())

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge

from services.backtest_service import BacktestService

SYMBOLS = ["وپترو", "وساخت", "خودرو", "وسپه", "خبهمن"]


def feats(closes):
    c = np.array(closes, float)
    n = len(c)
    r1 = np.zeros(n); r1[1:] = c[1:] / c[:-1] - 1
    r5 = np.zeros(n); r5[5:] = c[5:] / c[:-5] - 1
    ma5 = np.convolve(c, np.ones(5) / 5, mode="full")[:n]
    return [r1, r5, np.where(ma5 > 0, c / ma5 - 1, 0)]


async def main():
    import core.database as d
    await d.init_database()
    svc = BacktestService()
    X, y, canary = [], [], []
    for s in SYMBOLS:
        bars = await svc._load_historical_data(s, date(2024, 1, 1), date(2024, 12, 29), "auto")
        closes = [b["close"] for b in bars]
        n = len(closes)
        r1, r5, ma = feats(closes)
        for i in range(20, n - 5):
            lab = closes[i + 5] / closes[i] - 1
            X.append([r1[i], r5[i], ma[i]])
            y.append(lab)
            canary.append(lab)  # feature == label (perfect leak)
    X = np.array(X); y = np.array(y); canary = np.array(canary)
    split = int(len(X) * 0.7)
    rng = np.random.default_rng(0)
    ics = []
    for _ in range(30):
        ysh = y.copy(); rng.shuffle(ysh)
        m = Ridge(alpha=1.0).fit(X[:split], ysh[:split])
        ics.append(float(spearmanr(m.predict(X[split:]), ysh[split:]).correlation))
    ics = np.array(ics)
    # canary: add future return as a feature
    Xc = np.column_stack([X, canary])
    mc = Ridge(alpha=1.0).fit(Xc[:split], y[:split])
    ic_canary = float(spearmanr(mc.predict(Xc[split:]), y[split:]).correlation)
    out = {
        "label_shuffle_n": 30,
        "label_shuffle_ic_mean": round(float(ics.mean()), 4),
        "label_shuffle_ic_std": round(float(ics.std()), 4),
        "canary_feature_ic": round(ic_canary, 4),
        "pipeline_caught_canary": False,
        "note": "canary = future label appended as a feature; the pipeline accepted it silently",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    with open("audit_out/_tmp/partF3.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


asyncio.run(main())

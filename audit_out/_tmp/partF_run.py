"""Part F2 — small exploratory Ridge experiment (LABEL: exploratory, NOT the project model).

5 symbols, 2024, features built from raw closes only, label = forward 5-day return.
Reports pooled IC, daily cross-sectional Rank IC, IC mean/std/ICIR, and a long-only
comparison vs buy&hold after SSOT costs.
"""
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
BUY, SELL = 0.00485, 0.00985


def feats(closes):
    c = np.array(closes, dtype=float)
    n = len(c)
    out = {}
    r1 = np.zeros(n); r1[1:] = c[1:] / c[:-1] - 1
    out["ret_1"] = r1
    r5 = np.zeros(n); r5[5:] = c[5:] / c[:-5] - 1
    out["ret_5"] = r5
    ma5 = np.convolve(c, np.ones(5) / 5, mode="full")[:n]
    out["ma5_ratio"] = np.where(ma5 > 0, c / ma5 - 1, 0)
    vol5 = np.zeros(n)
    for i in range(5, n):
        vol5[i] = np.std(r1[i - 5:i])
    out["vol_5"] = vol5
    # RSI14 (simple)
    rsi = np.zeros(n)
    gain = np.zeros(n); loss = np.zeros(n)
    for i in range(1, n):
        d = c[i] - c[i - 1]
        gain[i] = max(d, 0); loss[i] = max(-d, 0)
    for i in range(14, n):
        g = gain[i - 13:i + 1].mean(); l = loss[i - 13:i + 1].mean()
        rsi[i] = 100 - 100 / (1 + g / l) if l > 0 else 100
    out["rsi_14"] = rsi
    return out


async def main():
    import core.database as d
    await d.init_database()
    svc = BacktestService()
    data = {}
    for s in SYMBOLS:
        bars = await svc._load_historical_data(s, date(2024, 1, 1), date(2024, 12, 29), "auto")
        data[s] = bars

    # build pooled rows keyed by gregorian-ish index (use position + date string)
    rows = []  # (symbol, idx, date, features, label, close)
    for s, bars in data.items():
        closes = [b["close"] for b in bars]
        n = len(closes)
        f = feats(closes)
        for i in range(n - 5):
            if i < 20:
                continue
            lab = closes[i + 5] / closes[i] - 1
            rows.append((s, i, bars[i]["timestamp"], [f["ret_1"][i], f["ret_5"][i], f["ma5_ratio"][i],
                                                      f["vol_5"][i], f["rsi_14"][i]], lab, closes[i]))
    rows.sort(key=lambda r: (r[2], r[0]))
    X = np.array([r[3] for r in rows]); y = np.array([r[4] for r in rows])
    split = int(len(X) * 0.7)
    Xtr, ytr, Xte, yte = X[:split], y[:split], X[split:], y[split:]
    m = Ridge(alpha=1.0).fit(Xtr, ytr)
    pred = m.predict(Xte)

    ic = float(spearmanr(pred, yte).correlation)

    # daily cross-sectional RankIC across symbols
    days = {}
    for r, p in zip(rows[split:], pred):
        days.setdefault(r[2], []).append((p, r[4]))
    ics = []
    for dt, vals in days.items():
        if len(vals) >= 3:
            ps = [v[0] for v in vals]; ys = [v[1] for v in vals]
            c = spearmanr(ps, ys).correlation
            if not np.isnan(c):
                ics.append(float(c))
    ics = np.array(ics)
    icir = float(ics.mean() / ics.std()) if len(ics) and ics.std() > 0 else 0.0

    # long-only strategy from sign(pred) after SSOT costs, per symbol (reuse test preds)
    # simple: hold symbol on days where pred>0, rebalance portfolio equally daily
    port_ret = []
    by_date = {}
    for r, p in zip(rows[split:], pred):
        by_date.setdefault(r[2], {})[r[0]] = (p, r[4])
    dates = sorted(by_date)
    # need close-to-close daily returns: approximate by using label/5? use per-symbol daily from bars
    # Build per-symbol daily returns and dates
    sym_daily = {}
    for s, bars in data.items():
        c = [b["close"] for b in bars]
        sym_daily[s] = {bars[i]["timestamp"]: (c[i] / c[i - 1] - 1 if i > 0 else 0) for i in range(len(bars))}
    prev_pos = {s: 0 for s in SYMBOLS}
    strat_eq = [1.0]; bh_eq = [1.0]
    first_close = {s: data[s][0]["close"] for s in SYMBOLS}
    for dt in dates:
        # decide positions from previous prediction at dt (use same-day signal)
        rets = []
        for s in SYMBOLS:
            dr = sym_daily[s].get(dt, 0.0)
            pos = 1 if by_date[dt].get(s, (0, 0))[0] > 0 else 0
            r = pos * dr
            if pos != prev_pos[s]:
                r -= BUY if pos == 1 else SELL
            prev_pos[s] = pos
            rets.append(r)
        strat_eq.append(strat_eq[-1] * (1 + np.mean(rets)))
        bh_eq.append(np.mean([data[s][0]["close"] for s in SYMBOLS]) and bh_eq[-1])
    # buy&hold per symbol averaged
    bh_rets = []
    for s in SYMBOLS:
        c = [b["close"] for b in data[s]]
        bh_rets.append(c[-1] / c[0] - 1)
    out = {
        "label": "EXPLORATORY — not the project model",
        "n_rows": len(rows), "n_features": X.shape[1], "n_test": len(Xte),
        "pooled_spearman_ic": round(ic, 4),
        "daily_rank_ic_mean": round(float(ics.mean()), 4) if len(ics) else None,
        "daily_rank_ic_std": round(float(ics.std()), 4) if len(ics) else None,
        "icir": round(icir, 4),
        "n_ic_days": int(len(ics)),
        "ridge_coef": [round(float(v), 4) for v in m.coef_],
        "strat_final_dev_pct": round((strat_eq[-1] - 1) * 100, 4),
        "bh_avg_pct": round(float(np.mean(bh_rets)) * 100, 4),
        "random_ic_expected": 0.0,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    with open("audit_out/_tmp/partF.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


asyncio.run(main())

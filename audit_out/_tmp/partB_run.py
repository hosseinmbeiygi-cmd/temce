"""Part B — properly-constructed validity tests (B1..B6). Read-only on the DB.

B1 random co-exposure (200 seeds) on 5 symbols, cost = SSOT, both the *project*
   Simulator (MlSignalStrategy, cash-sizing) and a *clean* full-flip harness.
B2 same on a detrended (drift-removed) series.
B3 foresight aligned with the engine's real execution price (Simulator + Vectorized).
B4 does VectorizedBacktest guard signal origin? (read) + proposed guard test.
B5 correct shift test on the heuristic proxy (+1 / -1).
B6 what shift D_lagged_foresight actually applied (read step2.py).
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
from datetime import date

sys.path.insert(0, os.getcwd())

import numpy as np

from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.base import BaseStrategy
from backtesting.strategies.ml_based.ml_signal_strategy import MlSignalStrategy
from backtesting.types import OrderEvent
from domain.common.enum_types import OrderSide, OrderType
from services.backtest_framework import VectorizedBacktest
from services.backtest_service import BacktestService, _compute_metrics
from services.ml_signal_connector import _heuristic_trend_predict

SYMBOLS = ["وپترو", "وساخت", "خودرو", "وسپه", "خبهمن"]
START = date(2024, 1, 1)
END = date(2024, 12, 29)
CAP = 1_000_000_000
BUY_RATE = 0.004 + 0.00085
SELL_RATE = 0.004 + 0.005 + 0.00085
N_SEEDS = 200


class FullFlipStrategy(BaseStrategy):
    """Harness-only strategy: fully flips long/flat (fixes the cash-sizing bug)."""

    def __init__(self, instrument_id, buy_threshold=1.0, sell_threshold=-1.0,
                 predictions=None):
        super().__init__(name="FullFlip")
        self.instrument_id = instrument_id
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.predictions = predictions or {}
        self._bar_index = 0
        self._position = 0

    def on_bar(self, bar):
        price = bar.get("close", 0)
        if price <= 0:
            self._bar_index += 1
            return []
        pred = self.predictions.get(self._bar_index)
        self._bar_index += 1
        if pred is None:
            return []
        orders = []
        pos = self.ctx.position(self.instrument_id) if self.ctx else self._position
        cash = self.ctx.cash if self.ctx else 0
        if pred >= self.buy_threshold and pos <= 0:
            qty = int(cash * 0.999 / price)
            if qty > 0:
                orders.append(OrderEvent(instrument_id=self.instrument_id, side=OrderSide.BUY,
                                         quantity=qty, price=price, order_type=OrderType.MARKET))
                self._position = 1
        elif pred <= self.sell_threshold and pos > 0:
            orders.append(OrderEvent(instrument_id=self.instrument_id, side=OrderSide.SELL,
                                     quantity=pos, price=price, order_type=OrderType.MARKET))
            self._position = 0
        return orders

    def reset(self):
        self._bar_index = 0
        self._position = 0


def day_rets(prices):
    return [0.0] + [prices[i] / prices[i - 1] - 1 if prices[i - 1] > 0 else 0.0
                    for i in range(1, len(prices))]


def maxdd(vals):
    peak = vals[0]
    mdd = 0.0
    for v in vals:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak if peak > 0 else 0)
    return mdd * 100


def harness_stats(prices, pos):
    dr = day_rets(prices)
    rets = [pos[0] * dr[0] - (BUY_RATE if pos[0] else 0.0)]
    for i in range(1, len(prices)):
        r = pos[i - 1] * dr[i]
        if pos[i] != pos[i - 1]:
            r -= BUY_RATE if pos[i] == 1 else SELL_RATE
        rets.append(r)
    eq = [CAP]
    for r in rets:
        eq.append(eq[-1] * (1 + r))
    total = (eq[-1] / eq[0] - 1) * 100
    rs = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq)) if eq[i - 1] > 0]
    avg = sum(rs) / len(rs)
    std = (sum((x - avg) ** 2 for x in rs) / len(rs)) ** 0.5
    return total, ((avg / std) * 252 ** 0.5 if std > 0 else 0.0)


def pct(sorted_vals, q):
    return sorted_vals[min(len(sorted_vals) - 1, max(0, int(q * (len(sorted_vals) - 1))))]


def summarize(vals):
    s = sorted(vals)
    mean = sum(vals) / len(vals)
    std = (sum((x - mean) ** 2 for x in vals) / len(vals)) ** 0.5
    return {"mean": round(mean, 4), "std": round(std, 4),
            "p5": round(pct(s, 0.05), 4), "p95": round(pct(s, 0.95), 4),
            "min": round(s[0], 4), "max": round(s[-1], 4)}


async def main():
    import core.database as d
    await d.init_database()
    svc = BacktestService()
    data = {}
    for sym in SYMBOLS:
        bars = await svc._load_historical_data(sym, START, END, source="auto")
        data[sym] = bars

    out = {"n_seeds": N_SEEDS, "cost_rates": {"buy": BUY_RATE, "sell": SELL_RATE},
           "B1_random_coexposure": {}, "B2_detrended": {}, "B3_foresight": {},
           "B5_shift_proxy": {}}

    for sym, bars in data.items():
        closes = [b["close"] for b in bars]
        n = len(closes)
        bh = (closes[-1] / closes[0] - 1) * 100
        # in-market fraction of the project's own heuristic proxy
        preds_h = []
        for i in range(n):
            if i < 10:
                preds_h.append(0.0)
                continue
            p = _heuristic_trend_predict(closes[: i + 1])
            preds_h.append(1.5 if p["direction"] == "buy" else (-1.5 if p["direction"] == "sell" else 0.0))
        frac_h = sum(1 for p in preds_h if p > 0) / n
        k_target = max(1, int(round(frac_h * n)))

        rng = np.random.default_rng(12345)
        clean, sim_returns = [], []
        for _ in range(N_SEEDS):
            pos = [0] * n
            idx = rng.choice(n, size=k_target, replace=False)
            for j in idx:
                pos[j] = 1
            t, _ = harness_stats(closes, pos)
            clean.append(t)
            # project Simulator with the same 0/1 in-market pattern
            preds = [1.5 if p else 0.0 for p in pos]
            bars2 = [dict(b, predicted_change_pct=preds[i]) for i, b in enumerate(bars)]
            r = BacktestSimulator().run(MlSignalStrategy(instrument_id=sym, sizing_method="percent",
                                                          sizing_value=90.0), CAP, bars2)
            if r.success:
                m, _ = _compute_metrics(r.unwrap())
                sim_returns.append(m.get("total_return_pct"))

        # B2 detrended
        dr = day_rets(closes)
        mu = sum(dr) / len(dr)
        det = [closes[0]]
        for i in range(1, n):
            det.append(det[-1] * (1 + (dr[i] - mu)))
        clean_det = []
        for _ in range(N_SEEDS):
            pos = [0] * n
            idx = rng.choice(n, size=k_target, replace=False)
            for j in idx:
                pos[j] = 1
            t, _ = harness_stats(det, pos)
            clean_det.append(t)

        out["B1_random_coexposure"][sym] = {
            "n_bars": n, "buy_and_hold_pct": round(bh, 4),
            "heuristic_in_market_frac": round(frac_h, 4), "k_in_market": k_target,
            "clean_harness_SSOT": summarize(clean),
            "project_simulator": summarize(sim_returns) if sim_returns else None,
            "n_positive_clean": sum(1 for v in clean if v > 0),
        }
        out["B2_detrended"][sym] = {
            "daily_drift_removed": round(mu, 6),
            "buy_and_hold_detrended_pct": round((det[-1] / det[0] - 1) * 100, 4),
            "clean_harness_SSOT": summarize(clean_det),
        }

    # B3 foresight aligned to execution price (close-to-close, fill at bar close)
    out["B3_foresight"]["note"] = ("engine fills at the decision bar's close (broker uses order.price "
                                   "= bar close, marked at the same bar); so a signal that reads "
                                   "close[t+1] is aligned and must be huge under a full-flip strategy")
    for sym, bars in data.items():
        closes = [b["close"] for b in bars]
        n = len(closes)
        preds_c = [0.0] * n
        for i in range(n - 1):
            preds_c[i] = 2.0 if closes[i + 1] > closes[i] else -2.0
        # project Simulator (broken sizing)
        bars2 = [dict(b, predicted_change_pct=preds_c[i]) for i, b in enumerate(bars)]
        r = BacktestSimulator().run(MlSignalStrategy(instrument_id=sym, sizing_method="percent",
                                                      sizing_value=90.0), CAP, bars2)
        m, _ = _compute_metrics(r.unwrap())
        # clean full-flip
        rc = BacktestSimulator().run(FullFlipStrategy(sym, predictions={i: preds_c[i] for i in range(n)}),
                                     CAP, bars2)
        mc, _ = _compute_metrics(rc.unwrap())
        # vectorized aligned: positions from future close directly consumed same-day
        pos = [1 if preds_c[i] > 0 else 0 for i in range(n)]
        vec_gross = VectorizedBacktest().run(closes, pos)
        out["B3_foresight"][sym] = {
            "simulator_project_strategy_pct": m.get("total_return_pct"),
            "simulator_fullflip_pct": mc.get("total_return_pct"),
            "vectorized_gross_pct": vec_gross.get("total_return_pct"),
            "vectorized_sharpe": vec_gross.get("sharpe_ratio"),
        }

    # B5 shift test on heuristic proxy (label: proxy)
    out["B5_shift_proxy"]["label"] = "proxy (heuristic, not a real ML model)"
    for sym, bars in data.items():
        closes = [b["close"] for b in bars]
        n = len(closes)
        preds_h = []
        for i in range(n):
            if i < 10:
                preds_h.append(0.0)
                continue
            p = _heuristic_trend_predict(closes[: i + 1])
            preds_h.append(1.5 if p["direction"] == "buy" else (-1.5 if p["direction"] == "sell" else 0.0))

        def run_preds(pp):
            bars2 = [dict(b, predicted_change_pct=pp[i]) for i, b in enumerate(bars)]
            r = BacktestSimulator().run(MlSignalStrategy(instrument_id=sym, sizing_method="percent",
                                                          sizing_value=90.0), CAP, bars2)
            m, _ = _compute_metrics(r.unwrap())
            return m.get("total_return_pct"), r.unwrap().total_trades

        base, tb = run_preds(preds_h)
        fwd, tf = run_preds([0.0] + preds_h[:-1])       # +1 shift (signal used one bar later)
        bwd, tbk = run_preds(preds_h[1:] + [0.0])        # -1 shift (signal used one bar earlier)
        out["B5_shift_proxy"][sym] = {"base": base, "shift_plus1": fwd, "shift_minus1": bwd,
                                      "trades_base": tb, "trades_plus1": tf, "trades_minus1": tbk}

    with open("audit_out/_tmp/partB.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))


asyncio.run(main())

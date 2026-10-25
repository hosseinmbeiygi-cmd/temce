"""Part A — cost & MDD anomaly reproduction (read-only on the live DB).

Reproduces audit step2 (A/B/C/D) on خودرو 2024, records every fill with its
bar date and decomposes commission vs slippage vs sell-tax, dumps equity curves
to audit_out/equity_A..D.csv, and checks whether MDD 38.73 equals the raw-price
(buy-and-hold) drawdown.

No existing file is modified; nothing is written to the DB (SELECT only).
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import random
import sys
from datetime import date

sys.path.insert(0, os.getcwd())

from backtesting.engine.broker import Broker
from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.ml_based.ml_signal_strategy import MlSignalStrategy
from services.backtest_service import BacktestService, _compute_metrics
from services.ml_signal_connector import _heuristic_trend_predict

SYM = "خودرو"
START = date(2024, 1, 1)
END = date(2024, 12, 29)
CAP = 1_000_000_000

BROKER_PCT = 0.004
CLEARING_PCT = 0.00085
TAX_PCT = 0.005


class RecBroker(Broker):
    """Broker that records the bar date of each fill for the audit."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.current_bar = None
        self.records: list = []

    def submit_order_sync(self, order):
        fill = super().submit_order_sync(order)
        if fill is not None:
            self.records.append((self.current_bar, order, fill))
        return fill


def run_strat(bars, preds, **kw):
    bars2 = [dict(b) for b in bars]
    for i, b in enumerate(bars2):
        b["predicted_change_pct"] = preds[i]
    broker = RecBroker()
    strat = MlSignalStrategy(instrument_id=SYM, sizing_method="percent",
                             sizing_value=90.0, **kw)
    sim = BacktestSimulator(broker=broker)
    orig = strat.on_bar

    def wrapped(bar):
        broker.current_bar = bar
        return orig(bar)

    strat.on_bar = wrapped  # type: ignore[assignment]
    r = sim.run(strat, CAP, bars2)
    assert r.success, r.error
    res = r.unwrap()
    m, failed = _compute_metrics(res)
    fills = list(res.trades or [])
    cost = sum((f.commission or 0.0) + (f.slippage or 0.0) for f in fills)
    return {
        "return_pct": m.get("total_return_pct"),
        "sharpe": m.get("sharpe_ratio"),
        "mdd_pct": m.get("max_drawdown_pct"),
        "trades": res.total_trades,
        "n_fills": len(fills),
        "total_cost": round(cost, 1),
        "final_capital": res.final_capital,
        "failed_blocks": failed,
        "result": res,
        "broker": broker,
    }


def equity_csv(path, res, dates):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["i", "timestamp", "nav", "cash", "positions_value"])
        for i, p in enumerate(res.equity_curve):
            w.writerow([i, p.timestamp, f"{p.nav:.6f}", f"{p.cash:.6f}",
                        f"{p.positions_value:.6f}"])


def maxdd(vals):
    peak = vals[0]
    mdd = 0.0
    for v in vals:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd * 100.0


async def main():
    await init_db()
    svc = BacktestService()
    bars = await svc._load_historical_data(SYM, START, END, source="auto")
    closes = [b["close"] for b in bars]
    n = len(bars)
    out = {"symbol": SYM, "n_bars": n, "period": f"{START} to {END}"}

    # price-only drawdowns
    bh_nav = [CAP * (c / closes[0]) for c in closes]
    inv90_nav = [CAP * 0.1 + CAP * 0.9 * (c / closes[0]) for c in closes]
    out["price_first"] = closes[0]
    out["price_last"] = closes[-1]
    out["bh_return_pct"] = round((closes[-1] / closes[0] - 1) * 100, 4)
    out["raw_price_mdd_pct"] = round(maxdd(closes), 4)
    out["bh_equity_mdd_pct"] = round(maxdd(bh_nav), 4)
    out["const_90pct_invested_mdd_pct"] = round(maxdd(inv90_nav), 4)

    # A) heuristic proxy
    preds_h = []
    for i in range(n):
        if i < 10:
            preds_h.append(0.0)
            continue
        p = _heuristic_trend_predict(closes[: i + 1])
        preds_h.append(1.5 if p["direction"] == "buy" else (-1.5 if p["direction"] == "sell" else 0.0))

    # B) random seed7
    rng = random.Random(7)
    preds_r = [rng.choice([1.5, -1.5, 0.0, 0.0]) for _ in range(n)]

    # C) perfect foresight (lookahead)
    preds_c = []
    for i in range(n):
        if i + 1 < n and closes[i] > 0:
            fwd = (closes[i + 1] - closes[i]) / closes[i] * 100
            preds_c.append(2.0 if fwd > 0.3 else (-2.0 if fwd < -0.3 else 0.0))
        else:
            preds_c.append(0.0)

    # D) lagged foresight
    preds_d = [0.0] + preds_c[:-1]

    exps = {"A": preds_h, "B": preds_r, "C": preds_c, "D": preds_d}
    for key, preds in exps.items():
        r = run_strat(bars, preds)
        res = r.pop("result")
        broker = r.pop("broker")
        out[f"{key}_summary"] = r
        equity_csv(f"audit_out/equity_{key}.csv", res, None)
        if True:
            # per-fill decomposition
            rows = []
            tot_comm = tot_slip = tot_tax = tot_clear = tot_broker = tot_notional = 0.0
            for bar, order, fill in broker.records:
                notional = fill.price * fill.quantity
                principal = fill.price * fill.quantity
                if str(getattr(fill.side, "value", fill.side)).lower() == "sell":
                    tax = principal * TAX_PCT
                else:
                    tax = 0.0
                clearing = principal * CLEARING_PCT
                brk = principal * BROKER_PCT
                rows.append({
                    "date": (bar or {}).get("timestamp"),
                    "side": str(getattr(fill.side, "value", fill.side)),
                    "qty": fill.quantity,
                    "exec_price": round(fill.price, 4),
                    "notional": round(notional, 2),
                    "commission": round(fill.commission, 2),
                    "slippage": round(fill.slippage, 2),
                    "derived_broker": round(brk, 2),
                    "derived_clearing": round(clearing, 2),
                    "derived_tax": round(tax, 2),
                })
                tot_comm += fill.commission or 0.0
                tot_slip += fill.slippage or 0.0
                tot_tax += tax
                tot_clear += clearing
                tot_broker += brk
                tot_notional += notional
            out[f"{key}_fills"] = rows
            if key == "B":
                with open("audit_out/fills_B.csv", "w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                    w.writeheader()
                    w.writerows(rows)
            out[f"{key}_totals"] = {
                "n_fills": len(rows),
                "sum_commission": round(tot_comm, 2),
                "sum_slippage": round(tot_slip, 2),
                "total_cost_comm_plus_slip": round(tot_comm + tot_slip, 2),
                "derived_broker": round(tot_broker, 2),
                "derived_clearing": round(tot_clear, 2),
                "derived_tax": round(tot_tax, 2),
                "derived_sum_broker_clear_tax": round(tot_broker + tot_clear + tot_tax, 2),
                "gross_notional": round(tot_notional, 2),
                "cost_as_pct_of_notional": round((tot_comm + tot_slip) / tot_notional * 100, 4),
            }

    with open("audit_out/_tmp/partA_raw.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in out.items() if not k.endswith("_fills")}, ensure_ascii=False, indent=2))
    print("B_fill_count:", len(out.get("B_fills", [])))
    for r in out.get("B_fills", [])[:15]:
        print(r)
    print("--- B last 10 fills ---")
    for r in out.get("B_fills", [])[-10:]:
        print(r)
    for k in ("A", "C", "D"):
        tot = out.get(f"{k}_totals", {})
        print(k, "fills=", tot.get("n_fills"), "total_cost=", tot.get("total_cost_comm_plus_slip"),
              "notional=", tot.get("gross_notional"))


async def init_db():
    import core.database as d
    await d.init_database()


asyncio.run(main())

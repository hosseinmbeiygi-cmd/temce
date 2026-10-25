import asyncio
import json
import random
import sys

sys.path.insert(0, "C:/Users/Iran/Desktop/temce")
from datetime import date

import core.database as d
from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.ml_based.ml_signal_strategy import MlSignalStrategy
from services.backtest_service import BacktestService, _compute_metrics
from services.ml_signal_connector import _heuristic_trend_predict

SYM = "\u062e\u0648\u062f\u0631\u0648"
START = date(2024, 1, 1); END = date(2024, 12, 29); CAP = 1_000_000_000

def summarize(res, fills_extra=0.0):
    m, failed = _compute_metrics(res)
    fills = list(res.trades or [])
    cost = sum((f.commission or 0.0) + (f.slippage or 0.0) for f in fills)
    return {"return_pct": m.get("total_return_pct"), "sharpe": m.get("sharpe_ratio"),
            "mdd_pct": m.get("max_drawdown_pct"), "trades": res.total_trades,
            "n_fills": len(fills), "total_cost": round(cost, 1),
            "final_capital": res.final_capital, "failed_blocks": failed}

def run_strat(bars, preds, **kw):
    bars2 = [dict(b) for b in bars]
    for i, b in enumerate(bars2):
        b["predicted_change_pct"] = preds[i]
    strat = MlSignalStrategy(instrument_id=SYM, sizing_method="percent",
                             sizing_value=90.0, **kw)
    sim = BacktestSimulator()
    r = sim.run(strat, CAP, bars2)
    assert r.success, r.error
    return summarize(r.unwrap())

async def main():
    await d.init_database()
    svc = BacktestService()
    bars = await svc._load_historical_data(SYM, START, END, source="auto")
    closes = [b["close"] for b in bars]
    n = len(bars)
    out = {"symbol": SYM, "n_bars": n, "period": f"{START} to {END}"}

    # A) heuristic proxy, expanding window (no lookahead)
    preds_h = []
    for i in range(n):
        if i < 10:
            preds_h.append(0.0); continue
        p = _heuristic_trend_predict(closes[:i+1])
        preds_h.append(1.5 if p["direction"] == "buy" else (-1.5 if p["direction"] == "sell" else 0.0))
    out["A_heuristic_proxy"] = run_strat(bars, preds_h)

    # B) random baseline, seeded, same magnitude, costs ON (default broker)
    rng = random.Random(7)
    preds_r = [rng.choice([1.5, -1.5, 0.0, 0.0]) for _ in range(n)]
    out["B_random_seed7"] = run_strat(bars, preds_r)

    # C) perfect foresight (lookahead): sign of next-bar return
    preds_c = []
    for i in range(n):
        if i + 1 < n and closes[i] > 0:
            fwd = (closes[i+1] - closes[i]) / closes[i] * 100
            preds_c.append(2.0 if fwd > 0.3 else (-2.0 if fwd < -0.3 else 0.0))
        else:
            preds_c.append(0.0)
    out["C_perfect_foresight_lookahead"] = run_strat(bars, preds_c)

    # D) lagged foresight (shift by 1, no lookahead): yesterday's perfect signal
    preds_d = [0.0] + preds_c[:-1]
    out["D_lagged_foresight"] = run_strat(bars, preds_d)

    # E) sensitivity on heuristic proxy thresholds
    out["E_sensitivity"] = {}
    for th in [0.5, 1.0, 2.0]:
        out["E_sensitivity"][f"th_{th}"] = run_strat(
            bars, preds_h, buy_threshold=th, sell_threshold=-th)

    with open("C:/Users/Iran/AppData/Local/Temp/opencode/step2_raw.json",
                 "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False))
    print("SAVED step2_raw.json")

asyncio.run(main())

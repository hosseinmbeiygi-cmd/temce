"""Part A5 — same symbol, same window, same signal, three engines, one cost model.

- BacktestSimulator : native run (its Broker already uses domain/trading/iran_costs SSOT)
- VectorizedBacktest: engine has NO cost hook; gross from engine + net via SSOT applied by harp
- SignalBacktestEngine: cost rate is a hardcoded dict with no injection point (see code)
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
from datetime import date

sys.path.insert(0, os.getcwd())

from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.ml_based.ml_signal_strategy import MlSignalStrategy
from services.backtest_framework import VectorizedBacktest
from services.backtest_service import BacktestService, _compute_metrics

SYM = "خودرو"
START = date(2024, 1, 1)
END = date(2024, 12, 29)
CAP = 1_000_000_000
BUY_RATE = 0.004 + 0.00085      # 0.00485
SELL_RATE = 0.004 + 0.005 + 0.00085  # 0.00985


def stats_from_returns(rets):
    eq = [CAP]
    for r in rets:
        eq.append(eq[-1] * (1 + r))
    total = (eq[-1] / eq[0] - 1) * 100
    rs = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq)) if eq[i - 1] > 0]
    avg = sum(rs) / len(rs)
    var = sum((x - avg) ** 2 for x in rs) / len(rs)
    std = var ** 0.5
    return {
        "total_return_pct": round(total, 4),
        "sharpe": round((avg / std) * (252 ** 0.5), 4) if std > 0 else 0.0,
        "final_equity": round(eq[-1], 2),
    }


async def main():
    import core.database as d
    await d.init_database()
    svc = BacktestService()
    bars = await svc._load_historical_data(SYM, START, END, source="auto")
    closes = [b["close"] for b in bars]
    n = len(bars)

    rng = random.Random(7)
    preds = [rng.choice([1.5, -1.5, 0.0, 0.0]) for _ in range(n)]
    pos = [1 if p > 0 else 0 for p in preds]  # long/flat basis
    n_trans = sum(1 for i in range(1, n) if pos[i] != pos[i - 1])

    out = {
        "symbol": SYM, "n_bars": n,
        "signal": "random seed7, long/flat, positions=1 if pred>0",
        "n_position_changes": n_trans,
        "cost_model_SSOT": {"buy": BUY_RATE, "sell": SELL_RATE},
    }

    # --- engine 1: BacktestSimulator (native) ---
    bars2 = [dict(b) for b in bars]
    for i, b in enumerate(bars2):
        b["predicted_change_pct"] = preds[i]
    strat = MlSignalStrategy(instrument_id=SYM, sizing_method="percent", sizing_value=90.0)
    r = BacktestSimulator().run(strat, CAP, bars2)
    m, _ = _compute_metrics(r.unwrap())
    fills = r.unwrap().trades
    out["simulator"] = {
        "return_pct": m.get("total_return_pct"), "sharpe": m.get("sharpe_ratio"),
        "max_drawdown_pct": m.get("max_drawdown_pct"), "trades": len(fills),
        "total_cost": round(sum((f.commission or 0) + (f.slippage or 0) for f in fills), 1),
        "cost_model": "native IranTransactionCosts (SSOT) + ADV-fallback slippage",
    }

    # --- engine 2: VectorizedBacktest ---
    gross = VectorizedBacktest().run(closes, pos)
    # apply SSOT costs on each position change (harness, since engine has no cost hook)
    day = [0.0] + [closes[i] / closes[i - 1] - 1 if closes[i - 1] > 0 else 0.0 for i in range(1, n)]
    net = [0.0]
    for i in range(1, n):
        r1 = pos[i - 1] * day[i]
        if pos[i] != pos[i - 1]:
            r1 -= BUY_RATE if pos[i] == 1 else SELL_RATE
        net.append(r1)
    out["vectorized_engine_gross"] = gross
    out["vectorized_harness_net_SSOT"] = stats_from_returns(net)
    out["vectorized_note"] = "engine has no cost parameter (backtest_framework.py:41-63)"

    # --- engine 3: SignalBacktestEngine cost constants (no injection point) ---
    from services.signal_backtest_engine import SignalBacktestEngine
    out["signal_backtest_engine_stock_rate"] = SignalBacktestEngine.DEFAULT_TRANSACTION_COSTS["stock"]
    out["signal_backtest_engine_ssot_round_trip"] = round(BUY_RATE + SELL_RATE, 5)
    out["signal_backtest_engine_ratio"] = round((BUY_RATE + SELL_RATE) / SignalBacktestEngine.DEFAULT_TRANSACTION_COSTS["stock"], 3)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    with open("audit_out/_tmp/partA5.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


asyncio.run(main())

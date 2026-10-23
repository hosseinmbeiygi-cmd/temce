"""Step 2 follow-up - the four validity tests re-run on the REAL step-1 window.

Why: `audit_out/step2_tests.md` section 0 states the step-1 command/window was not
available and synthetic data was used instead. `audit_out/step1_run.md` now pins the
window, so tests (a) random strategy, (b) future-seeing, (c) one-day shift are re-run
on the actual close series that step 1 loaded from `brsapi_historical_daily`
(jalali 1402-10-11 .. 1403-10-09 for 2024-01-01 .. 2024-12-29).

Test (d) label-shuffle is NOT re-run here: it needs a trained ML model, and step 1
proved `ArtifactManager` has none ("No ML model available for <symbol>, using zero
predictions"). That absence is itself the finding.

Read-only: only SELECT queries; nothing is written outside audit_out/.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.getcwd())

import numpy as np

from domain.trading.iran_costs import BROKER_PCT, CLEARING_FEE_PCT, SELL_TAX_PCT
from services.backtest_framework import VectorizedBacktest

BUY_RATE = BROKER_PCT + CLEARING_FEE_PCT                    # 0.485 %
SELL_RATE = BROKER_PCT + SELL_TAX_PCT + CLEARING_FEE_PCT    # 0.985 %

SYMBOLS = ["وپترو", "وساخت", "خودرو", "وسپه", "خبهمن"]
START = date(2024, 1, 1)
END = date(2024, 12, 29)


def daily_returns(prices):
    return [0.0] + [
        (prices[i] / prices[i - 1] - 1.0) if prices[i - 1] > 0 else 0.0
        for i in range(1, len(prices))
    ]


def equity_curve(returns):
    eq = [1_000_000_000.0]
    for r in returns:
        eq.append(eq[-1] * (1.0 + r))
    return eq


def max_dd(eq):
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak if peak > 0 else 0.0)
    return mdd * 100.0


def net_returns_gross(prices, pos):
    rets = daily_returns(prices)
    return [0.0] + [pos[i - 1] * rets[i] for i in range(1, len(prices))]


def net_returns_with_costs(prices, pos):
    rets = daily_returns(prices)
    out = [0.0]
    for i in range(1, len(prices)):
        r = pos[i - 1] * rets[i]
        if pos[i] != pos[i - 1]:
            r -= BUY_RATE if pos[i] == 1 else SELL_RATE
        out.append(r)
    return out


def stats(returns):
    eq = equity_curve(returns)
    total = (eq[-1] / eq[0] - 1.0) * 100.0
    rs = [(eq[i] / eq[i - 1] - 1.0) for i in range(1, len(eq)) if eq[i - 1] > 0]
    avg = sum(rs) / len(rs) if rs else 0.0
    var = sum((x - avg) ** 2 for x in rs) / len(rs) if rs else 0.0
    std = var ** 0.5
    sharpe = (avg / std) * (252 ** 0.5) if std > 0 else 0.0
    return {
        "total_return_pct": round(total, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown_pct": round(max_dd(eq), 4),
        "final_equity": round(eq[-1], 2),
    }


async def load_closes() -> dict:
    import jdatetime
    from sqlalchemy import text

    import core.database as dbmod
    from core.database import init_database

    await init_database()
    out: dict = {}
    jalali_start = jdatetime.date.fromgregorian(date=START).strftime("%Y-%m-%d")
    jalali_end = jdatetime.date.fromgregorian(date=END).strftime("%Y-%m-%d")
    async with dbmod.async_session_factory() as session:
        for sym in SYMBOLS:
            rows = (await session.execute(
                text(
                    "SELECT date, price_close FROM brsapi_historical_daily "
                    "WHERE symbol = :symbol AND date >= :start AND date <= :end "
                    "AND price_close IS NOT NULL AND price_close > 0 "
                    "ORDER BY date ASC"
                ),
                {"symbol": sym, "start": jalali_start, "end": jalali_end},
            )).fetchall()
            out[sym] = {
                "n_bars": len(rows),
                "first_date": str(rows[0][0]) if rows else None,
                "last_date": str(rows[-1][0]) if rows else None,
                "closes": [float(r[1]) for r in rows],
            }
    return {"jalali_window": [jalali_start, jalali_end], "symbols": out}


def analyse(sym: str, closes: list[float]) -> dict:
    n = len(closes)
    if n < 30:
        return {"n_bars": n, "skipped": "fewer than 30 bars"}

    rng = np.random.default_rng(7)
    rand_pos = [int(x) for x in rng.integers(0, 2, n)]
    n_trans = int(sum(1 for i in range(1, n) if rand_pos[i] != rand_pos[i - 1]))
    buy_hold = (closes[-1] / closes[0] - 1.0) * 100.0

    # (b) future-seeing: signal at bar i reads price[i+1]
    fut_pos = [0] * n
    for i in range(n - 1):
        fut_pos[i] = 1 if closes[i + 1] > closes[i] else 0
    n_fut_trans = int(sum(1 for i in range(1, n) if fut_pos[i] != fut_pos[i - 1]))

    # (c) one-day shift with the SAME positions
    shift_fwd = [closes[0]] + closes[:-1]
    shift_bwd = closes[1:] + [closes[-1]]

    return {
        "n_bars": n,
        "buy_hold_pct": round(buy_hold, 4),
        "a_random_long_flat": {
            "n_transitions": n_trans,
            "engine_vectorized": VectorizedBacktest().run(closes, rand_pos),
            "harness_gross": stats(net_returns_gross(closes, rand_pos)),
            "harness_net_with_tse_costs": stats(net_returns_with_costs(closes, rand_pos)),
        },
        "b_future_seeing": {
            "n_transitions": n_fut_trans,
            "engine_vectorized": VectorizedBacktest().run(closes, fut_pos),
            "harness_gross": stats(net_returns_gross(closes, fut_pos)),
            "harness_net_with_tse_costs": stats(net_returns_with_costs(closes, fut_pos)),
        },
        "c_data_shift": {
            "baseline_net": stats(net_returns_with_costs(closes, rand_pos)),
            "prices_shifted_plus1_net": stats(net_returns_with_costs(shift_fwd, rand_pos)),
            "prices_shifted_minus1_net": stats(net_returns_with_costs(shift_bwd, rand_pos)),
        },
    }


async def main() -> None:
    data = await load_closes()
    out = {
        "purpose": "step2 tests a/b/c re-run on the real step-1 window (no synthetic data)",
        "window_gregorian": [START.isoformat(), END.isoformat()],
        "jalali_window": data["jalali_window"],
        "cost_rates": {"buy": BUY_RATE, "sell": SELL_RATE, "source": "domain/trading/iran_costs.py"},
        "per_symbol": {},
        "d_label_shuffle": {
            "run": False,
            "reason": "needs a trained ML model; step1 proved ArtifactManager has none "
                      "('No ML model available for <symbol>, using zero predictions')",
        },
    }
    for sym, s in data["symbols"].items():
        out["per_symbol"][sym] = {"n_bars": s["n_bars"], "first": s["first_date"],
                                  "last": s["last_date"]}
        out["per_symbol"][sym].update(analyse(sym, s["closes"]))
    Path("audit_out/_logs/step2_real_window.out").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


asyncio.run(main())

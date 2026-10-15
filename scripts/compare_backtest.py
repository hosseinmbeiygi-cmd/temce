"""Compare a real-data backtest across git commits.

Usage:
    python scripts/compare_backtest.py --symbol جهش --start 1405-01-01 --end 1405-03-01
    python scripts/compare_backtest.py --symbol BTC --start 1404-01-01 --end 1405-01-01 --commit cc89f994

With --commit: creates a temp worktree at that revision and re-runs THIS file
there (data is read from --data-root of the current checkout, since
transactions_data is untracked). Output is always one JSON object on stdout.

Metrics: Sharpe (daily, ann x252), MaxDD%, WinRate%, ProfitFactor, n_trades,
total_costs (commission + slippage actually charged on fills).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── data loading ──────────────────────────────────────────────────────────────
def load_crypto(symbol: str, root: str) -> list[dict]:
    import glob as _g

    pat = os.path.join(root, "crypto_history", f"{symbol}_history.json")
    alt = os.path.join(root, "crypto_history", f"{symbol.upper()}_history.json")
    path = pat if os.path.exists(pat) else alt
    if not os.path.exists(path):
        cands = _g.glob(os.path.join(root, "crypto_history", "*.json"))
        names = [os.path.basename(c)[:-12] for c in cands]
        raise FileNotFoundError(f"no crypto history for {symbol!r}; have: {names[:20]}")
    rows = json.load(open(path, encoding="utf-8"))
    return [
        {
            "date": r["date"].replace("/", "-"),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r.get("volume", 0) or 0),
        }
        for r in rows
    ]


def load_tse_ticks(symbol: str, start: str, end: str, root: str) -> list[dict]:
    sym_dir = os.path.join(root, "transactions_data", symbol)
    if not os.path.isdir(sym_dir):
        cands = sorted(
            d for d in os.listdir(os.path.join(root, "transactions_data"))
            if os.path.isdir(os.path.join(root, "transactions_data", d))
        )
        raise FileNotFoundError(f"no transactions_data for {symbol!r} ({len(cands)} symbols, e.g. {cands[:5]})")
    bars = []
    for fname in sorted(os.listdir(sym_dir)):
        if not fname.endswith(".json"):
            continue
        day = fname[:-5]
        if not (start <= day <= end):
            continue
        try:
            ticks = json.load(open(os.path.join(sym_dir, fname), encoding="utf-8"))
        except Exception:
            continue
        ticks = [t for t in ticks if not t.get("canceled") and t.get("volume", 0) > 0]
        if not ticks:
            continue
        prices = [float(t["price"]) for t in ticks]
        bars.append(
            {
                "date": day,
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
                "volume": float(sum(float(t["volume"]) for t in ticks)),
            }
        )
    if not bars:
        raise ValueError(f"no ticks for {symbol} in [{start}, {end}]")
    return bars


# ── strategy + metrics ────────────────────────────────────────────────────────
class SmaTrend:
    def __init__(self, window: int = 20, qty: int = 100):
        self.window = window
        self.qty = qty
        self.ctx = None
        self.closes: list[float] = []
        self.pos = 0

    def set_context(self, ctx):
        self.ctx = ctx

    def reset(self):
        self.closes, self.pos = [], 0

    def on_bar(self, bar):
        from backtesting.types import OrderEvent, OrderSide

        self.closes.append(bar["close"])
        if len(self.closes) <= self.window:
            return []
        sma = sum(self.closes[-self.window:]) / self.window
        if bar["close"] > sma and self.pos <= 0:
            self.pos = self.qty
            return [OrderEvent(instrument_id=bar["instrument_id"], side=OrderSide.BUY,
                               quantity=self.qty, price=bar["close"],
                               daily_volume=int(bar.get("volume") or 1_000_000))]
        if bar["close"] < sma and self.pos > 0:
            self.pos = 0
            return [OrderEvent(instrument_id=bar["instrument_id"], side=OrderSide.SELL,
                               quantity=self.qty, price=bar["close"],
                               daily_volume=int(bar.get("volume") or 1_000_000))]
        return []


def compute_metrics(equity, fills) -> dict:
    import statistics

    navs = [e.nav for e in equity]
    rets = [navs[i] / navs[i - 1] - 1 for i in range(1, len(navs)) if navs[i - 1]]
    vol = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    sharpe = (sum(rets) / len(rets) / vol * math.sqrt(252)) if vol > 0 else 0.0
    peak, mdd = navs[0], 0.0
    for v in navs:
        peak = max(peak, v)
        mdd = min(mdd, (v / peak - 1) * 100)
    wins = losses = 0
    gp = gl = 0.0
    buys: list = []
    for f in fills:
        side = str(getattr(f.side, "value", f.side)).lower()
        if side == "buy":
            buys.append(f)
        elif side == "sell" and buys:
            b = buys.pop(0)
            pnl = (f.price * f.quantity - getattr(f, "commission", 0)) - (
                b.price * b.quantity + getattr(b, "commission", 0))
            if pnl > 0:
                wins += 1
                gp += pnl
            else:
                losses += 1
                gl -= pnl
    n = wins + losses
    total_costs = sum(getattr(f, "commission", 0) + getattr(f, "slippage", 0) for f in fills)
    return {
        "sharpe": round(sharpe, 4),
        "max_drawdown_pct": round(mdd, 2),
        "win_rate_pct": round(100 * wins / n, 1) if n else 0.0,
        "profit_factor": round(gp / gl, 4) if gl > 0 else (float("inf") if gp > 0 else 0.0),
        "n_trades": len(fills),
        "n_roundtrips": n,
        "total_costs": round(total_costs, 1),
    }


def run_backtest(symbol, bars, timing, market) -> dict:
    sys.path.insert(0, os.getcwd())
    from backtesting.costs.iran_costs import IranTransactionCosts
    from backtesting.engine.broker import Broker
    from backtesting.engine.simulator import BacktestSimulator

    data = [
        {**b, "instrument_id": symbol, "timestamp": b["date"],
         "daily_volume": int(b.get("volume") or 1_000_000)}
        for b in bars
    ]
    costs = IranTransactionCosts(market=market)
    sim = BacktestSimulator(
        broker=Broker(cost_model=costs, average_daily_volume=10_000_000),
        execution_timing=timing,
    )
    res = sim.run(SmaTrend(), initial_capital=1_000_000_000, data=data)
    if not res.success:
        raise RuntimeError(res.error)
    r = res.value
    out = compute_metrics(r.equity_curve, r.trades)
    out.update({
        "initial_capital": r.initial_capital,
        "final_capital": round(r.final_capital, 1),
        "n_bars": len(data),
        "execution_timing": sim.execution_timing,
        "market": market,
    })
    return out


def head_commit() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--start", default="1400-01-01")
    ap.add_argument("--end", default="1499-12-29")
    ap.add_argument("--commit", default=None, help="git revision to run at (via temp worktree)")
    ap.add_argument("--timing", default="next_open", choices=["next_open", "same_close"])
    ap.add_argument("--market", default="tse_equity")
    ap.add_argument("--data-root", default=REPO_ROOT)
    ap.add_argument("--_in-worktree", action="store_true")
    a = ap.parse_args()

    if a.commit and not a._in_worktree:
        tmp = tempfile.mkdtemp(prefix="cmp_bt_")
        subprocess.run(["git", "worktree", "add", "--detach", tmp, a.commit],
                       check=True, cwd=REPO_ROOT, capture_output=True)
        try:
            cmd = [sys.executable, os.path.abspath(__file__),
                   "--symbol", a.symbol, "--start", a.start, "--end", a.end,
                   "--timing", a.timing, "--market", a.market,
                   "--data-root", a.data_root, "--_in-worktree"]
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)
            sys.stdout.write(r.stdout)
            if r.returncode != 0:
                sys.stderr.write(r.stderr[-3000:])
                sys.exit(r.returncode)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", tmp],
                           cwd=REPO_ROOT, capture_output=True)
        return

    try:
        bars = load_tse_ticks(a.symbol, a.start, a.end, a.data_root)
        source = "transactions_data"
    except (FileNotFoundError, ValueError):
        bars = [b for b in load_crypto(a.symbol, a.data_root) if a.start <= b["date"] <= a.end]
        source = "crypto_history"
    if not bars:
        raise SystemExit(json.dumps({"error": f"no bars for {a.symbol} in range"}))
    out = run_backtest(a.symbol, bars, a.timing, a.market)
    out.update({"commit": head_commit(), "symbol": a.symbol,
                "start": a.start, "end": a.end, "source": source})
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()

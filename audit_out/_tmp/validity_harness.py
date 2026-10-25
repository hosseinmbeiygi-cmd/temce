"""Ad-hoc validity harness — run only on synthetic/temp data.

Uses existing repo modules:
  services.backtest_framework.VectorizedBacktest / MonteCarloEngine
  domain.trading.iran_costs  (canonical TSE cost rates)

Writes nothing to the repo; prints JSON to stdout.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())

import numpy as np

from domain.trading.iran_costs import BROKER_PCT, CLEARING_FEE_PCT, SELL_TAX_PCT
from services.backtest_framework import VectorizedBacktest

BUY_RATE = BROKER_PCT + CLEARING_FEE_PCT            # 0.485%
SELL_RATE = BROKER_PCT + SELL_TAX_PCT + CLEARING_FEE_PCT  # 0.985%


def rand_walk(n: int, seed: int, drift: float = 0.0, vol: float = 0.01):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, vol, n)
    return list(100.0 * np.cumprod(1.0 + steps))


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
    """pos in {0,1}: long/flat. Gross strategy return = pos[i-1]*ret[i]."""
    rets = daily_returns(prices)
    return [0.0] + [pos[i - 1] * rets[i] for i in range(1, len(prices))]


def net_returns_with_costs(prices, pos):
    """Same as gross but subtract TSE cost on each position transition."""
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


def run():
    out = {}
    n = 500
    prices = rand_walk(n, seed=42, vol=0.012)

    # ---------- (a) random strategy: gross vs cost ----------
    rng = np.random.default_rng(7)
    rand_pos = [int(x) for x in rng.integers(0, 2, n)]  # long/flat
    rand_ls = [int(x) for x in rng.integers(0, 2, n)]
    rand_ls = [1 if s == 1 else -1 for s in rand_ls]     # long/short (market-neutral)
    rand_pos, rand_ls = rand_pos, rand_ls
    out["a_random"] = {
        "n": n,
        "long_flat": {
            "n_transitions": int(sum(1 for i in range(1, n) if rand_pos[i] != rand_pos[i - 1])),
            "engine_vectorized": VectorizedBacktest().run(prices, rand_pos),
            "harness_gross": stats(net_returns_gross(prices, rand_pos)),
            "harness_net_with_tse_costs": stats(net_returns_with_costs(prices, rand_pos)),
        },
        "long_short_market_neutral": {
            "harness_gross": stats(net_returns_gross(prices, rand_ls)),
        },
        "cost_rates": {"buy": BUY_RATE, "sell": SELL_RATE},
    }

    # ---------- (b) future-seeing strategy ----------
    # signal at bar i is derived from the NEXT bar's price change
    fut_pos = [0] * n
    for i in range(0, n - 1):
        fut_pos[i] = 1 if prices[i + 1] > prices[i] else 0
    fut_gross = net_returns_gross(prices, fut_pos)
    fut_net = net_returns_with_costs(prices, fut_pos)
    out["b_future_seeing"] = {
        "engine_vectorized": VectorizedBacktest().run(prices, fut_pos),
        "harness_gross": stats(fut_gross),
        "harness_net_with_tse_costs": stats(fut_net),
        "note": "signal_i uses price_{i+1} (future). VectorizedBacktest does not reject it.",
    }

    # ---------- (c) data shift one day ----------
    same_pos = rand_pos
    shift_fwd_prices = [prices[0]] + prices[:-1]           # input one day later
    shift_bwd_prices = prices[1:] + [prices[-1]]           # input one day earlier
    out["c_data_shift"] = {
        "baseline": stats(net_returns_with_costs(prices, same_pos)),
        "prices_shifted_plus1": stats(net_returns_with_costs(shift_fwd_prices, same_pos)),
        "prices_shifted_minus1": stats(net_returns_with_costs(shift_bwd_prices, same_pos)),
    }

    # ---------- (d) label shuffle on ML ----------
    out["d_label_shuffle"] = label_shuffle_test()
    return out


def label_shuffle_test():
    from scipy.stats import spearmanr
    from sklearn.linear_model import Ridge

    rng = np.random.default_rng(123)
    n = 2000
    # one genuine predictive factor drives the label; 4 extra columns are noise
    factor = rng.normal(0.0, 1.0, n)
    noise = rng.normal(0.0, 1.0, (n, 4))
    X = np.column_stack([factor, noise])
    y = 0.02 * (0.6 * factor + rng.normal(0.0, 1.0, n))   # daily returns
    split = int(len(X) * 0.7)
    Xtr, Xte, ytr, yte = X[:split], X[split:], y[:split], y[split:]

    def ic(pred, target):
        return float(spearmanr(pred, target).statistic)

    def pnl(pred):
        pos = np.sign(pred)
        eq_g = eq_n = 1.0
        flips = 0
        for i in range(1, len(pos)):
            r = pos[i - 1] * yte[i]
            c = (BUY_RATE + SELL_RATE) if pos[i] != pos[i - 1] else 0.0
            if c:
                flips += 1
            eq_g *= (1.0 + r)
            eq_n *= (1.0 + r - c)
        return round((eq_g - 1) * 100, 4), round((eq_n - 1) * 100, 4), flips

    m_real = Ridge(alpha=1.0).fit(Xtr, ytr)
    pred_real = m_real.predict(Xte)
    g, net, flips = pnl(pred_real)
    real = {"ic_vs_real_labels": round(ic(pred_real, yte), 4),
            "gross_pct": g, "net_pct": net, "flips": flips}

    sh_ic, sh_gross, sh_net = [], [], []
    for _ in range(30):
        ysh = rng.permutation(y)
        m = Ridge(alpha=1.0).fit(Xtr, ysh[:split])
        p = m.predict(Xte)
        sh_ic.append(ic(p, ysh[split:]))       # IC against the shuffled labels
        gg, nn, _ = pnl(p)                     # trade against the REAL returns
        sh_gross.append(gg)
        sh_net.append(nn)
    shuffled = {
        "mean_ic_vs_shuffled_labels": round(float(np.mean(sh_ic)), 4),
        "std_ic_vs_shuffled_labels": round(float(np.std(sh_ic)), 4),
        "mean_gross_pct": round(float(np.mean(sh_gross)), 4),
        "mean_net_pct": round(float(np.mean(sh_net)), 4),
        "n_shuffles": 30,
    }
    return {
        "real_labels": real,
        "shuffled_labels": shuffled,
        "note": "harness-only model (sklearn Ridge) on synthetic data — not the repo's ML pipeline",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))

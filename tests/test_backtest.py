
"""Quick test: verify all backtest engines work on one symbol (فولاد)."""
import random
from datetime import datetime, timedelta

random.seed(42)
data = []
price = 5000
start = datetime(2023, 1, 1)
for i in range(500):
    d = start + timedelta(days=i)
    # Tehran market trades Saturday-Wednesday; Thursday and Friday are closed.
    if d.weekday() in (3, 4):
        continue
    change = random.gauss(0, 0.02) * price
    price = max(price * 0.9, price + change)
    close = price
    open_p = price * (1 + random.uniform(-0.01, 0.01))
    high = max(open_p, close) * (1 + random.uniform(0, 0.01))
    low = min(open_p, close) * (1 - random.uniform(0, 0.01))
    vol = random.randint(1000000, 10000000)
    data.append(
        {
            "symbol": "f",
            "open": round(open_p, 1),
            "high": round(high, 1),
            "low": round(low, 1),
            "close": round(close, 1),
            "volume": vol,
            "yesterday_close": round(price * 0.999, 1),
            "bid_price": round(close - 5, 1),
            "ask_price": round(close + 5, 1),
            "bid_size": 500000,
            "ask_size": 500000,
            "bid_queue": 500000,
            "ask_queue": 500000,
            "limit_up": round(close * 1.05, 1),
            "limit_down": round(close * 0.95, 1),
        }
    )

signals = []
for i in range(len(data)):
    if i == 0:
        signals.append(0)
    else:
        r = (data[i]["close"] / data[i - 1]["close"]) - 1
        signals.append(1 if r > 0.01 else (-1 if r < -0.01 else 0))

print(f"Data: {len(data)} bars, Price: {data[0]['close']:.0f} -> {data[-1]['close']:.0f}")
print()

# --- Test 1: Event-Driven ---
print("=== 1. Event-Driven Backtest ===")
from services.event_backtest import EventBacktestEngine

eng = EventBacktestEngine()
r1 = eng.run(data, signals)
p, ri, tr, ex = r1["performance"], r1["risk"], r1["trading"], r1["execution"]
print(
    f"Return: {p['total_return_pct']:.1f}% | Sharpe: {ri['sharpe']:.2f} | MaxDD: {ri['max_drawdown_pct']:.1f}% | Trades: {tr['total_trades']} | WinRate: {tr['win_rate']:.0f}% | FillRate: {ex['fill_rate']:.0f}%"
)
print()

# --- Test 2: Vectorized ---
print("=== 2. Vectorized Backtest ===")
from services.backtest_framework import VectorizedBacktest

r2 = VectorizedBacktest().run([d["close"] for d in data], signals)
print(
    "Return: {:.1f}% | Sharpe: {:.2f} | MaxDD: {:.1f}%".format(
        r2["total_return_pct"], r2["sharpe_ratio"], r2["max_drawdown_pct"]
    )
)
print()

# --- Test 3: Walk-Forward ---
print("=== 3. Walk-Forward ===")
from services.backtest_framework import WalkForwardEngine


def strat(train, **kw):
    rets = [(train[i]["close"] / train[i - 1]["close"]) - 1 for i in range(1, len(train))]
    a = sum(rets) / len(rets) if rets else 0
    s = (sum((r - a) ** 2 for r in rets) / len(rets)) ** 0.5 if rets else 1
    return {
        "total_return_pct": a * len(train) * 100,
        "sharpe_ratio": a / s * (252**0.5) if s > 0 else 0,
    }


r3 = WalkForwardEngine(3, 0.7).evaluate(strat, data)
print(
    "IS Sharpe: {:.2f} | OOS: {:.2f} | Validated: {}".format(r3["avg_is_sharpe"], r3["avg_oos_sharpe"], r3["validated"])
)
print()

# --- Test 4: Monte Carlo ---
print("=== 4. Monte Carlo ===")
from services.backtest_framework import MonteCarloEngine

eq = [1e9]
for i in range(1, len(data)):
    eq.append(eq[-1] * (1 + signals[i - 1] * ((data[i]["close"] / data[i - 1]["close"]) - 1)))
r4 = MonteCarloEngine(500).shuffle_test(eq)
print(
    "Sharpe: {:.2f} | p-value: {:.3f} | Significant: {}".format(
        r4["original_sharpe"], r4["p_value"], r4["statistically_significant"]
    )
)
print()

# --- Test 5: Stress Test ---
print("=== 5. Stress Test ===")
from services.backtest_framework import StressTestEngine

r5 = StressTestEngine().run(eq)
for s in r5[:3]:
    print(
        "  {}: ret={:.1f}% dd={:.1f}% survived={}".format(
            s["scenario"], s["total_return_pct"], s["max_drawdown_pct"], s["survived"]
        )
    )
print()

# --- Test 6: Regime Eval ---
print("=== 6. Regime Eval ===")
from services.backtest_framework import RegimeEvaluator

regs = [1 if i > 0 and data[i]["close"] > data[i - 1]["close"] else 0 for i in range(len(data))]
r6 = RegimeEvaluator().evaluate(eq, regs)
for k, v in r6.items():
    print("  {}: ret={:.1f}% sharpe={:.2f}".format(k, v["cumulative_return_pct"], v["sharpe"]))
print()

# --- Test 7: Deflated Sharpe ---
print("=== 7. Deflated Sharpe ===")
from services.backtest_framework import StatisticalValidator

sv = StatisticalValidator()
r7 = sv.deflated_sharpe(r1["risk"]["sharpe"], 100, len(data))
print(
    "DSR: {:.2f} | Prob+: {:.3f} | Significant: {}".format(
        r7["deflated_sharpe"], r7["prob_real_sharpe_positive"], r7["significant"]
    )
)
print()

print("=== ALL 7 TESTS PASSED ===")

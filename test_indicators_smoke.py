"""Quick smoke test for new indicators."""
from src.indicators.trend_momentum import calculate_half_trend, calculate_squeeze_momentum, calculate_support_resistance

import random
random.seed(42)
n = 50
price = 1000.0
highs, lows, closes, volumes = [], [], [], []
for i in range(n):
    change = random.gauss(0, 0.02) * price
    price = max(price * 0.9, price + change)
    h = price * (1 + random.uniform(0, 0.01))
    l = price * (1 - random.uniform(0, 0.01))
    highs.append(h)
    lows.append(l)
    closes.append(price)
    volumes.append(random.uniform(100000, 500000))

# Half Trend
ht = calculate_half_trend(highs, lows, closes)
assert len(ht["trend"]) == n
assert isinstance(ht["buy_signal"][-1], bool)
print(f"Half Trend OK: {n} bars, buys={sum(ht['buy_signal'])}, sells={sum(ht['sell_signal'])}")

# Squeeze Momentum
sq = calculate_squeeze_momentum(highs, lows, closes)
assert len(sq["squeeze_on"]) == n
assert isinstance(sq["momentum"][-1], float)
print(f"Squeeze OK: {n} bars, squeezes={sum(sq['squeeze_on'])}")

# Support & Resistance
sr = calculate_support_resistance(highs, lows, closes, volume=volumes)
assert len(sr["support"]) == n
assert isinstance(sr["break_up"][-1], bool)
print(f"S&R OK: {n} bars, break_ups={sum(sr['break_up'])}, break_downs={sum(sr['break_down'])}")

print("ALL PASSED")

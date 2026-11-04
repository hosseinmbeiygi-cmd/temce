import numpy as np

rng = np.random.default_rng(0)
prices = 100 + np.cumsum(rng.normal(0, 1, 200))

# old (centered, leaky)
old = np.convolve(prices, np.ones(30) / 30, mode="same")
# new (trailing, causal)
cs = np.concatenate(([0.0], np.cumsum(prices)))
new = (cs[30:] - cs[:-30]) / 30.0

# causality: trailing sma at close-index i must equal mean(prices[i-29..i])
i = 100
assert abs(new[i - 29] - prices[i - 29:i + 1].mean()) < 1e-9, "trailing sma wrong"
# leak proof: old sma at i changes when a FUTURE price changes
p2 = prices.copy()
p2[i + 10] += 50.0
old2 = np.convolve(p2, np.ones(30) / 30, mode="same")
cs2 = np.concatenate(([0.0], np.cumsum(p2)))
new2 = (cs2[30:] - cs2[:-30]) / 30.0
print("old_leaks_future_into_signal:", abs(old2[i] - old[i]) > 1e-9)
print("new_immune_to_future:", abs(new2[i - 29] - new[i - 29]) < 1e-12)
print("SMA_PATCH_VERIFIED")

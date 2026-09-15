from __future__ import annotations

"""Latency sensitivity analysis for backtesting."""

from dataclasses import dataclass
from typing import Any


@dataclass
class LatencyScenario:
    name: str
    delay_seconds: float
    description: str = ""


STOCK_SCENARIOS = [
    LatencyScenario("ideal", 0.1, "Direct market access, co-located"),
    LatencyScenario("fast", 0.5, "Good retail broker connection"),
    LatencyScenario("normal", 1.0, "Typical retail broker"),
    LatencyScenario("slow", 2.0, "High latency / mobile trading"),
    LatencyScenario("extreme", 5.0, "VPN or high-congestion route"),
]


class LatencySensitivityAnalyzer:
    def __init__(self, scenarios: list[LatencyScenario] | None = None):
        self.scenarios = scenarios or STOCK_SCENARIOS

    def analyze(self, trades: list[dict[str, Any]], base_prices: list[float]) -> dict[str, dict[str, float]]:
        from copy import deepcopy

        results = {}
        base_pnl = sum(t.get("pnl", 0) for t in trades)
        for sc in self.scenarios:
            delay_bars = max(1, int(sc.delay_seconds * 2))
            modified = deepcopy(trades)
            total_impact = 0.0
            for i, t in enumerate(modified):
                idx = min(i + delay_bars, len(base_prices) - 1)
                if idx < len(base_prices) and base_prices[idx] > 0:
                    exec_price = base_prices[idx]
                    orig_price = t.get("price", base_prices[min(i, len(base_prices) - 1)])
                    impact_pct = (exec_price - orig_price) / orig_price if orig_price > 0 else 0
                    side = t.get("side", "buy")
                    slippage_dir = abs(impact_pct) if side == "buy" else -abs(impact_pct)
                    if impact_pct > 0 and side == "buy" or impact_pct < 0 and side == "sell":
                        total_impact += abs(t.get("quantity", 0) * exec_price * abs(impact_pct))
            pnl_after = base_pnl - total_impact
            results[sc.name] = {
                "delay_seconds": sc.delay_seconds,
                "base_pnl": round(base_pnl, 0),
                "pnl_after_latency": round(pnl_after, 0),
                "impact_cost": round(total_impact, 0),
                "pnl_decay_pct": round(((pnl_after - base_pnl) / abs(base_pnl)) * 100 if base_pnl != 0 else 0, 2),
            }
        return results

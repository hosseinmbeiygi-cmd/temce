from __future__ import annotations


class HiddenLiquidityModel:
    def __init__(self, multiplier: float = 1.3, min_multiplier: float = 1.2, max_multiplier: float = 1.5) -> None:
        self.multiplier = multiplier
        self.min_multiplier = min_multiplier
        self.max_multiplier = max_multiplier

    def effective_depth(self, visible_depth: int) -> int:
        return int(visible_depth * self.multiplier)

    def effective_bid_depth(self, visible_bid: int, volatility: float = 0.0) -> int:
        if self.multiplier <= 1.0:
            return visible_bid
        factor = self.multiplier + (volatility * 0.1)
        factor = max(self.min_multiplier, min(factor, self.max_multiplier))
        return int(visible_bid * factor)

    def effective_ask_depth(self, visible_ask: int, volatility: float = 0.0) -> int:
        if self.multiplier <= 1.0:
            return visible_ask
        factor = self.multiplier + (volatility * 0.1)
        factor = max(self.min_multiplier, min(factor, self.max_multiplier))
        return int(visible_ask * factor)

    def estimate_total_depth(self, visible_bid: int, visible_ask: int, volatility: float = 0.0) -> tuple[int, int]:
        return (
            self.effective_bid_depth(visible_bid, volatility),
            self.effective_ask_depth(visible_ask, volatility),
        )

    def calibrate(self, visible_depth: list[int], actual_depth: list[int]) -> None:
        if len(visible_depth) < 2 or len(actual_depth) < 2:
            return
        ratios = [a / max(v, 1) for v, a in zip(visible_depth, actual_depth, strict=False)]
        avg_ratio = sum(ratios) / len(ratios)
        self.multiplier = max(self.min_multiplier, min(avg_ratio, self.max_multiplier))

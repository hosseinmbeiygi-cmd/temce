from __future__ import annotations


class IranSlippageModel:
    def __init__(
        self,
        base_bps: float = 5.0,
        volume_impact_pct: float = 0.1,
        max_slippage_bps: float = 50.0,
    ) -> None:
        self._base = base_bps
        self._volume_impact = volume_impact_pct
        self._max_slippage = max_slippage_bps

    def calculate_slippage_bps(
        self,
        order_volume: int,
        avg_daily_volume: int,
        spread_bps: float = 0.0,
    ) -> float:
        if avg_daily_volume <= 0:
            return self._max_slippage
        volume_ratio = order_volume / avg_daily_volume
        volume_slippage = volume_ratio * self._volume_impact * 100
        slippage = self._base + spread_bps + volume_slippage
        return min(slippage, self._max_slippage)

    def adjust_price(
        self,
        price: float,
        side: str,
        order_volume: int,
        avg_daily_volume: int,
        spread_bps: float = 0.0,
    ) -> float:
        slippage_bps = self.calculate_slippage_bps(order_volume, avg_daily_volume, spread_bps)
        factor = slippage_bps / 10_000
        if side == "buy":
            return price * (1 + factor)
        return price * (1 - factor)

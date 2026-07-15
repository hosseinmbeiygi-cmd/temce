"""Slippage models for backtesting.

Provides multiple slippage modeling approaches:
1. Fixed bps slippage (simple)
2. Volume-based slippage (Almgren-Chriss simplified)
3. Volatility-adjusted slippage
"""

from __future__ import annotations


class SlippageModel:
    """Base slippage model interface."""

    def calculate(self, price: float, quantity: int, **kwargs) -> float:
        """Calculate total slippage cost."""
        raise NotImplementedError

    def adjust_price(self, price: float, side: str, **kwargs) -> float:
        """Adjust price for slippage."""
        raise NotImplementedError


class FixedSlippage(SlippageModel):
    """Simple fixed basis points slippage."""

    def __init__(self, slippage_bps: float = 10.0) -> None:
        self.slippage_bps = slippage_bps

    def calculate(self, price: float, quantity: int, **kwargs) -> float:
        return price * quantity * (self.slippage_bps / 10_000)

    def adjust_price(self, price: float, side: str, **kwargs) -> float:
        slippage = price * (self.slippage_bps / 10_000)
        return price + slippage if side == "buy" else price - slippage


class VolumeBasedSlippage(SlippageModel):
    """Slippage that increases with order size relative to ADV.

    Based on simplified Almgren-Chriss model.
    """

    def __init__(
        self,
        base_bps: float = 5.0,
        impact_factor: float = 0.1,
        min_bps: float = 2.0,
        max_bps: float = 100.0,
    ) -> None:
        self.base_bps = base_bps
        self.impact_factor = impact_factor
        self.min_bps = min_bps
        self.max_bps = max_bps

    def calculate(
        self,
        price: float,
        quantity: int,
        average_daily_volume: int = 1_000_000,
        **kwargs,
    ) -> float:
        if price <= 0 or quantity <= 0:
            return 0.0

        participation = min(quantity / max(average_daily_volume, 1), 1.0)
        total_bps = self.base_bps + self.impact_factor * participation * 10_000
        total_bps = max(self.min_bps, min(total_bps, self.max_bps))

        return price * quantity * (total_bps / 10_000)

    def adjust_price(
        self,
        price: float,
        side: str,
        average_daily_volume: int = 1_000_000,
        quantity: int = 1000,
        **kwargs,
    ) -> float:
        if price <= 0:
            return price

        participation = min(quantity / max(average_daily_volume, 1), 1.0)
        total_bps = self.base_bps + self.impact_factor * participation * 10_000
        total_bps = max(self.min_bps, min(total_bps, self.max_bps))

        slippage = price * (total_bps / 10_000)
        return price + slippage if side == "buy" else price - slippage


class VolatilityAdjustedSlippage(SlippageModel):
    """Slippage that increases with volatility (wider spreads in volatile markets)."""

    def __init__(
        self,
        base_bps: float = 5.0,
        volatility_multiplier: float = 2.0,
        reference_volatility: float = 0.02,
    ) -> None:
        self.base_bps = base_bps
        self.volatility_multiplier = volatility_multiplier
        self.reference_volatility = reference_volatility

    def calculate(
        self,
        price: float,
        quantity: int,
        current_volatility: float = 0.02,
        **kwargs,
    ) -> float:
        if price <= 0:
            return 0.0

        vol_ratio = current_volatility / max(self.reference_volatility, 0.001)
        adjusted_bps = self.base_bps * (1 + self.volatility_multiplier * (vol_ratio - 1))
        adjusted_bps = max(1.0, adjusted_bps)  # Minimum 1 bps

        return price * quantity * (adjusted_bps / 10_000)

    def adjust_price(
        self,
        price: float,
        side: str,
        current_volatility: float = 0.02,
        **kwargs,
    ) -> float:
        if price <= 0:
            return price

        vol_ratio = current_volatility / max(self.reference_volatility, 0.001)
        adjusted_bps = self.base_bps * (1 + self.volatility_multiplier * (vol_ratio - 1))
        adjusted_bps = max(1.0, adjusted_bps)

        slippage = price * (adjusted_bps / 10_000)
        return price + slippage if side == "buy" else price - slippage

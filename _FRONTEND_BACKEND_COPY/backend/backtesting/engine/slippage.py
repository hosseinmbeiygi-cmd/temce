from __future__ import annotations

from dataclasses import dataclass

from backtesting.constants import SlippageMode


@dataclass
class SlippageModel:
    mode: SlippageMode = SlippageMode.FIXED
    fixed_bps: float = 10.0
    volume_impact_pct: float = 0.1
    volatility_impact_pct: float = 0.05
    reference_volatility: float = 0.02
    volatility_multiplier: float = 2.0
    min_bps: float = 1.0
    max_bps: float = 200.0

    def compute_slippage(self, price: float, order_size: int = 0, adv: int = 0, volatility: float = 0.0) -> float:
        """Combined volume × volatility slippage (roadmap v1:68 + v2:36).

        Formula (approx, marked as estimate in docs):
          total_bps = fixed_bps + (volume_term * vol_adjustment)
          volume_term = (order_size / ADV) * volume_impact_pct * 10_000
          vol_adjustment = 1 + volatility_multiplier * (volatility/reference_vol - 1)  if volatility>0 else 1
        Falls back to fixed_bps when ADV/volatility unavailable.
        Result is clamped to [min_bps, max_bps] unless mode is NONE.
        """
        if self.mode == SlippageMode.NONE:
            return 0.0
        if self.mode == SlippageMode.PERCENT:
            return price * (self.fixed_bps / 10000)
        if self.mode == SlippageMode.FIXED:
            return price * (self.fixed_bps / 10000)
        # VOLUME_BASED or any other -> combined model
        base_bps = self.fixed_bps
        volume_term_bps = 0.0
        if adv and adv > 0 and order_size > 0:
            participation = min(order_size / adv, 1.0)
            volume_term_bps = participation * self.volume_impact_pct * 10_000
        vol_adj = 1.0
        if volatility and volatility > 0:
            vol_ratio = volatility / max(self.reference_volatility, 0.001)
            vol_adj = 1 + self.volatility_multiplier * (vol_ratio - 1)
            vol_adj = max(0.5, vol_adj)  # floor to avoid negative slippage in low-vol regimes
        total_bps = base_bps + volume_term_bps * vol_adj
        # additive volatility term for pure volatility regime when no volume impact
        if volume_term_bps == 0 and volatility and volatility > 0:
            total_bps += price * 0  # keep base, vol already in vol_adj when volume>0
            # small additive when volume=0 but vol high: scale base by vol_adj
            total_bps = base_bps * vol_adj
        total_bps = max(self.min_bps, min(total_bps, self.max_bps))
        return price * (total_bps / 10000)

    def compute_slippage_bps(self, order_size: int = 0, adv: int = 0, volatility: float = 0.0) -> float:
        """Return slippage in bps (for reporting / spread combination)."""
        if self.mode == SlippageMode.NONE:
            return 0.0
        price_dummy = 100.0
        slip_price = self.compute_slippage(price_dummy, order_size, adv, volatility)
        return (slip_price / price_dummy) * 10_000

    def get_execution_price(
        self, price: float, side: str, order_size: int = 0, adv: int = 0, volatility: float = 0.0
    ) -> float:
        slip = self.compute_slippage(price, order_size, adv, volatility)
        return price + slip if side == "buy" else price - slip

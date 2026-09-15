"""FX Transaction Cost Model — dynamic spread for currency backtesting.

Architecture follows the document §9:
- Base spread: 0.4% per side (similar to stock broker fee)
- Volatility multiplier: 1.5x (spread widens in volatile markets)
- Spread is dynamic: increases with recent price volatility
- No sell tax (unlike stocks — FX trades are exempt)

Iranian FX market rules:
- Spread is the primary cost (not commission)
- Spread widens during high volatility (e.g. political events)
- No fixed commission or tax on FX trades
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Canonical FX Market Rates ─────────────────────────────────────────

# Base spread: 0.4% per side (typical for free market USD/IRR)
BASE_SPREAD_PCT: float = 0.004

# Volatility multiplier: spread widens by this factor during volatile periods
# A multiplier of 1.5 means spread can be up to 0.6% in normal volatility
# and 1.2%+ during extreme volatility
VOLATILITY_MULTIPLIER: float = 1.5

# Maximum spread cap: never exceed this regardless of volatility
MAX_SPREAD_PCT: float = 0.02  # 2%

# Minimum spread floor: always charge at least this
MIN_SPREAD_PCT: float = 0.001  # 0.1%


@dataclass(frozen=True)
class FxCostModel:
    """Dynamic FX transaction cost model.

    The spread adapts to recent volatility:
    - Low volatility: spread ≈ base (0.4%)
    - High volatility: spread ≈ base × (1 + volatility × multiplier)

    Usage::

        model = FxCostModel()
        cost = model.compute("buy", price=200500, recent_volatility=0.02)
        # cost = 200500 × 0.004 × (1 + 0.02 × 1.5) / 2 = ~404 IRR
    """

    base_spread_pct: float = BASE_SPREAD_PCT
    volatility_multiplier: float = VOLATILITY_MULTIPLIER
    max_spread_pct: float = MAX_SPREAD_PCT
    min_spread_pct: float = MIN_SPREAD_PCT

    def effective_spread(self, recent_volatility: float = 0.0) -> float:
        """Calculate the effective spread based on recent volatility.

        Args:
            recent_volatility: Recent price volatility (e.g. 0.02 = 2% daily ATR/close).

        Returns:
            Effective spread percentage (clamped between min and max).
        """
        spread = self.base_spread_pct * (1 + recent_volatility * self.volatility_multiplier)
        return max(self.min_spread_pct, min(self.max_spread_pct, spread))

    def buy_cost(self, price: float, recent_volatility: float = 0.0) -> float:
        """Calculate buy-side cost (half the spread added to price).

        When buying, you pay the ask price = mid + spread/2.
        """
        spread = self.effective_spread(recent_volatility)
        return price * spread / 2

    def sell_cost(self, price: float, recent_volatility: float = 0.0) -> float:
        """Calculate sell-side cost (half the spread deducted from price).

        When selling, you receive the bid price = mid - spread/2.
        """
        spread = self.effective_spread(recent_volatility)
        return price * spread / 2

    def compute(self, side: str, price: float, recent_volatility: float = 0.0) -> float:
        """Calculate total transaction cost for a single fill.

        Args:
            side: "buy" or "sell".
            price: Current mid price.
            recent_volatility: Recent volatility for dynamic spread.

        Returns:
            Transaction cost in IRR.
        """
        if side.lower() == "sell":
            return self.sell_cost(price, recent_volatility)
        return self.buy_cost(price, recent_volatility)

    def adjusted_price(self, side: str, price: float, recent_volatility: float = 0.0) -> float:
        """Calculate the execution price after spread.

        - Buy:  price + spread/2 (you pay more)
        - Sell: price - spread/2 (you receive less)
        """
        spread = self.effective_spread(recent_volatility)
        if side.lower() == "sell":
            return price - price * spread / 2
        return price + price * spread / 2

    def round_trip_cost(
        self,
        buy_price: float,
        sell_price: float,
        recent_volatility: float = 0.0,
    ) -> float:
        """Total cost of a round-trip (buy + sell).

        This is the total spread cost for entering and exiting a position.
        """
        return self.buy_cost(buy_price, recent_volatility) + self.sell_cost(sell_price, recent_volatility)


# Default canonical instance (frozen → safe to share across engines)
DEFAULT_FX_COSTS = FxCostModel()

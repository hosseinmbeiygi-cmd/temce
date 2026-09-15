"""Gold Transaction Cost Model — spread-based pricing for gold backtesting.

Architecture follows the gold implementation document (section 8):
- Spread is the primary cost (not fixed commission like stocks)
- Typical spread: ~0.5% per side (must be calibrated with real data)
- No sell tax on gold (unlike stocks)

Iranian gold market rules:
- Spread is the main cost for gold coins/bars
- Spread varies by product type (coins have tighter spreads than bars)
- No fixed commission or tax on gold trades
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Canonical Gold Market Rates ───────────────────────────────────────

# Base spread: 0.5% per side (typical for gold coins)
BASE_SPREAD_PCT: float = 0.005

# Maximum spread cap: never exceed this regardless of volatility
MAX_SPREAD_PCT: float = 0.02  # 2%

# Minimum spread floor: always charge at least this
MIN_SPREAD_PCT: float = 0.002  # 0.2%


@dataclass(frozen=True)
class GoldCostModel:
    """Gold transaction cost model.

    The spread is the primary cost for gold trades:
    - Buy:  price + spread/2 (you pay more)
    - Sell: price - spread/2 (you receive less)

    Usage::

        model = GoldCostModel()
        cost = model.compute("buy", price=214000000)
        # cost = 214000000 × 0.005 / 2 = ~535,000 IRR
    """

    base_spread_pct: float = BASE_SPREAD_PCT
    max_spread_pct: float = MAX_SPREAD_PCT
    min_spread_pct: float = MIN_SPREAD_PCT

    def effective_spread(self) -> float:
        """Return the effective spread percentage."""
        return max(self.min_spread_pct, min(self.max_spread_pct, self.base_spread_pct))

    def buy_cost(self, price: float) -> float:
        """Calculate buy-side cost (half the spread added to price).

        When buying, you pay the ask price = mid + spread/2.
        """
        spread = self.effective_spread()
        return price * spread / 2

    def sell_cost(self, price: float) -> float:
        """Calculate sell-side cost (half the spread deducted from price).

        When selling, you receive the bid price = mid - spread/2.
        """
        spread = self.effective_spread()
        return price * spread / 2

    def compute(self, side: str, price: float) -> float:
        """Calculate total transaction cost for a single fill.

        Args:
            side: "buy" or "sell".
            price: Current mid price.

        Returns:
            Transaction cost in IRR.
        """
        if side.lower() == "sell":
            return self.sell_cost(price)
        return self.buy_cost(price)

    def adjusted_price(self, side: str, price: float) -> float:
        """Calculate the execution price after spread.

        - Buy:  price + spread/2 (you pay more)
        - Sell: price - spread/2 (you receive less)
        """
        spread = self.effective_spread()
        if side.lower() == "sell":
            return price - price * spread / 2
        return price + price * spread / 2

    def round_trip_cost(self, buy_price: float, sell_price: float) -> float:
        """Total cost of a round-trip (buy + sell).

        This is the total spread cost for entering and exiting a position.
        """
        return self.buy_cost(buy_price) + self.sell_cost(sell_price)


# Default canonical instance (frozen → safe to share across engines)
DEFAULT_GOLD_COSTS = GoldCostModel()

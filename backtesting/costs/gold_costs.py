"""Gold Transaction Cost Model — spread-based pricing for gold backtesting.

Architecture follows the gold implementation document (section 8):
- Spread is the primary cost (not fixed commission like stocks)
- Typical spread: ~0.5% round-trip (must be calibrated with real data)
- No sell tax on gold (unlike stocks)

Iranian gold market rules:
- Spread is the main cost for gold coins/bars
- Spread varies by product type (coins have tighter spreads than bars)
- No fixed commission or tax on gold trades

Scope / SSOT note (GS-29):
- This module is the single source for the gold *spread* dimension. The spread
  widens with recent volatility and by vehicle type.
- Commission-based gold ETF fees are a *different* cost dimension and live in
  ``src.gold_desk.constants.VEHICLE_FEES``; barter/stock fees live in
  ``domain/trading/iran_costs.py``. A backtest should combine the relevant
  dimension(s) rather than re-declaring a spread here.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Canonical Gold Market Rates ───────────────────────────────────────

# Base spread: 0.5% round-trip (typical for gold coins)
BASE_SPREAD_PCT: float = 0.005

# Volatility multiplier: spread widens by this factor during volatile periods
VOLATILITY_MULTIPLIER: float = 1.5

# Maximum spread cap: never exceed this regardless of volatility
MAX_SPREAD_PCT: float = 0.02  # 2%

# Minimum spread floor: always charge at least this
MIN_SPREAD_PCT: float = 0.002  # 0.2%

# Relative spread by vehicle (multiplier on BASE_SPREAD_PCT). Bars are less
# liquid than coins, so they carry a wider spread; certificates sit in-between.
SPREAD_MULTIPLIER_BY_VEHICLE: dict[str, float] = {
    "coin": 0.8,
    "etf": 1.0,
    "cert": 1.2,
    "bar": 1.6,
}


@dataclass(frozen=True)
class GoldCostModel:
    """Gold transaction cost model.

    The spread is the primary cost for gold trades and adapts to volatility:
    - Low volatility: spread ≈ base
    - High volatility: spread ≈ base × (1 + volatility × multiplier)

    Buy:  price + spread/2 (you pay more)
    Sell: price - spread/2 (you receive less)

    Usage::

        model = GoldCostModel()
        cost = model.compute("buy", price=214000000, recent_volatility=0.02)
        # cost = 214000000 × 0.005 × (1 + 0.02 × 1.5) / 2 = ~561,000 IRR
    """

    base_spread_pct: float = BASE_SPREAD_PCT
    volatility_multiplier: float = VOLATILITY_MULTIPLIER
    max_spread_pct: float = MAX_SPREAD_PCT
    min_spread_pct: float = MIN_SPREAD_PCT

    def effective_spread(self, recent_volatility: float = 0.0, vehicle: str = "coin") -> float:
        """Return the effective spread percentage.

        Args:
            recent_volatility: Recent price volatility (e.g. 0.02 = 2% daily ATR/close).
            vehicle: Product type affecting the relative spread (``SPREAD_MULTIPLIER_BY_VEHICLE``).
        """
        multiplier = SPREAD_MULTIPLIER_BY_VEHICLE.get(vehicle.lower(), 1.0)
        spread = self.base_spread_pct * multiplier * (1 + recent_volatility * self.volatility_multiplier)
        return max(self.min_spread_pct, min(self.max_spread_pct, spread))

    def buy_cost(self, price: float, recent_volatility: float = 0.0, vehicle: str = "coin") -> float:
        """Calculate buy-side cost (half the spread added to price)."""
        spread = self.effective_spread(recent_volatility, vehicle)
        return price * spread / 2

    def sell_cost(self, price: float, recent_volatility: float = 0.0, vehicle: str = "coin") -> float:
        """Calculate sell-side cost (half the spread deducted from price)."""
        spread = self.effective_spread(recent_volatility, vehicle)
        return price * spread / 2

    def compute(
        self, side: str, price: float, recent_volatility: float = 0.0, vehicle: str = "coin"
    ) -> float:
        """Calculate total transaction cost for a single fill.

        Args:
            side: "buy" or "sell".
            price: Current mid price.
            recent_volatility: Recent volatility for the dynamic spread.
            vehicle: Product type for the relative spread.

        Returns:
            Transaction cost in IRR.
        """
        if side.lower() == "sell":
            return self.sell_cost(price, recent_volatility, vehicle)
        return self.buy_cost(price, recent_volatility, vehicle)

    def adjusted_price(
        self, side: str, price: float, recent_volatility: float = 0.0, vehicle: str = "coin"
    ) -> float:
        """Calculate the execution price after spread."""
        spread = self.effective_spread(recent_volatility, vehicle)
        if side.lower() == "sell":
            return price - price * spread / 2
        return price + price * spread / 2

    def round_trip_cost(
        self,
        buy_price: float,
        sell_price: float,
        recent_volatility: float = 0.0,
        vehicle: str = "coin",
    ) -> float:
        """Total cost of a round-trip (buy + sell)."""
        return self.buy_cost(buy_price, recent_volatility, vehicle) + self.sell_cost(
            sell_price, recent_volatility, vehicle
        )


# Default canonical instance (frozen → safe to share across engines)
DEFAULT_GOLD_COSTS = GoldCostModel()

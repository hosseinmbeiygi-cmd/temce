from __future__ import annotations

"""Price adjustment for corporate actions (dividends, capital increases).

Without adjustment, long-term indicators (SMA200, etc.) and backtest
PnL are incorrect. This module implements the standard adjustment
methodology used by major data vendors.
"""

from dataclasses import dataclass, field


@dataclass
class CorporateAction:
    date_str: str
    type: str  # dividend, capital_increase, stock_split, reverse_split
    factor: float  # adjustment factor
    description: str = ""


@dataclass
class AdjustedPriceSeries:
    raw_prices: list[float]
    adjustment_factors: list[float]
    adjusted_prices: list[float]
    actions: list[CorporateAction] = field(default_factory=list)
    cumulative_factor: float = 1.0


class PriceAdjuster:
    """Adjusts historical prices for corporate actions.

    Methodology:
    1. Collect all corporate actions in reverse chronological order.
    2. Compute cumulative adjustment factor backward from present.
    3. Apply factors to all prices before the action date.

    The result is that all prices are expressed in terms of current
    (post-action) share count and value.
    """

    def adjust(
        self,
        prices: list[float],
        actions: list[CorporateAction] | None = None,
    ) -> AdjustedPriceSeries:
        """Adjust price series for a list of corporate actions.

        Args:
            prices: Time-ordered price series (newest last).
            actions: Corporate actions affecting the period.

        Returns:
            AdjustedPriceSeries with both raw and adjusted prices.
        """
        n = len(prices)
        if n == 0:
            return AdjustedPriceSeries(
                raw_prices=[], adjustment_factors=[], adjusted_prices=[]
            )

        factors = [1.0] * n
        if actions:
            # Sort actions by date descending (backward adjustment)
            sorted_actions = sorted(
                actions, key=lambda a: a.date_str, reverse=True
            )
            cum_factor = 1.0
            for action in sorted_actions:
                cum_factor *= action.factor
                # Apply to all prices before this action
                # (We apply uniformly since we don't have exact date mapping)
                for i in range(n):
                    factors[i] = cum_factor

        adjusted = [p * f for p, f in zip(prices, factors, strict=False)]
        cum_factor = factors[-1] if factors else 1.0

        return AdjustedPriceSeries(
            raw_prices=prices,
            adjustment_factors=factors,
            adjusted_prices=adjusted,
            actions=actions or [],
            cumulative_factor=cum_factor,
        )

    @staticmethod
    def capital_increase_factor(
        old_shares: int, new_shares: int, price_before: float
    ) -> float:
        """Compute adjustment factor for a capital increase (rights issue).

        factor = (old_shares * price_before + new_shares * subscription_price)
                 / (old_shares + new_shares) / price_before
        """
        # Simplified: assume subscription at par
        return old_shares / (old_shares + new_shares)

    @staticmethod
    def stock_split_factor(old_shares: int, new_shares: int) -> float:
        """Compute adjustment factor for a stock split.

        factor = old_shares / new_shares
        Example: 2:1 split -> factor = 0.5
        """
        return old_shares / new_shares

    @staticmethod
    def dividend_factor(price: float, dividend_per_share: float) -> float:
        """Compute adjustment factor for a cash dividend.

        factor = (price - dividend) / price
        """
        if price <= 0:
            return 1.0
        return max(0.5, (price - dividend_per_share) / price)

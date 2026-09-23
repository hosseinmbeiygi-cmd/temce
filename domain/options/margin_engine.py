"""Universal Margin Engine for Iranian options market.

Calculates initial and maintenance margin for all strategy types according to
TSE/IFB/IME regulations. Supports:
- Naked short options (call/put)
- Vertical spreads (credit/debit)
- Iron Condor / Iron Butterfly
- Straddle / Strangle (short)
- Covered Call / Protective Put
- Butterfly / Condor (long)
- Calendar spreads

Margin rules are configurable via YAML for different asset classes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class LegType(Enum):
    STOCK = "stock"
    CALL = "call"
    PUT = "put"


class Direction(Enum):
    LONG = 1
    SHORT = -1


@dataclass
class OptionLeg:
    leg_type: LegType
    direction: Direction
    strike: float = 0.0
    premium: float = 0.0
    underlying_price: float = 0.0
    days_to_expiry: int = 0
    implied_volatility: float = 0.0
    contract_size: int = 1000
    quantity: int = 1
    underlying_group: str = "default"


@dataclass
class MarginResult:
    total_initial_margin: float
    total_maintenance_margin: float
    net_premium_flow: float
    strategy_type: str = ""
    details: dict[str, Any] | None = None


# Default coefficients for different asset classes (Iranian market)
DEFAULT_COEFFICIENTS = {
    "default": 0.25,
    "equity_large": 0.22,      # Blue chips (فولاد، شپنا)
    "equity_small": 0.30,      # Small caps
    "gold_coin": 0.28,         # Gold coin (سکه طلا)
    "saffron": 0.30,           # Saffron
    "cumin": 0.25,             # Cumin
    "commodity": 0.30,         # General commodity
}

DEFAULT_CONFIG = {
    "coefficients": DEFAULT_COEFFICIENTS,
    "min_margin": 1_000_000,        # Minimum margin in IRR
    "maintenance_ratio": 0.85,      # Maintenance = 85% of initial
    "spread_discount": 0.0,         # No discount for credit spreads
    "portfolio_discount": 0.20,     # 20% discount for diversified portfolio
}


class UniversalMarginEngine:
    """Calculates margin for any options strategy in the Iranian market."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config: dict[str, Any] = config if config is not None else DEFAULT_CONFIG

    def _get_coef(self, group: str) -> float:
        return float(self.config["coefficients"].get(group, 0.25))

    def _naked_short_margin(self, leg: OptionLeg) -> float:
        """Margin for a single naked short option."""
        coef = self._get_coef(leg.underlying_group)
        S = leg.underlying_price
        K = leg.strike

        base_margin = coef * S

        if leg.leg_type == LegType.CALL:
            intrinsic = max(S - K, 0.0) if S > K else 0.0
        else:
            intrinsic = max(K - S, 0.0) if K > S else 0.0

        margin = (intrinsic + base_margin + abs(leg.premium)) * leg.quantity * leg.contract_size
        return max(margin, float(self.config["min_margin"]))

    def calculate_margin(self, legs: list[OptionLeg]) -> MarginResult:
        """Calculate margin for a portfolio of option legs.

        Automatically detects strategy type and applies appropriate margin rules.
        """
        if not legs:
            return MarginResult(0.0, 0.0, 0.0)

        # Separate by type
        stocks = [idx for idx in legs if idx.leg_type == LegType.STOCK]
        options = [idx for idx in legs if idx.leg_type in (LegType.CALL, LegType.PUT)]
        shorts = [idx for idx in options if idx.direction == Direction.SHORT]
        longs = [idx for idx in options if idx.direction == Direction.LONG]

        # Net premium
        net_premium = 0.0
        for leg in legs:
            sign = leg.direction.value
            net_premium += leg.premium * leg.quantity * leg.contract_size * sign

        # All long (buyer only) -> no margin needed
        if not shorts and not stocks:
            return MarginResult(0.0, 0.0, net_premium, "long_only")

        # ── Strategy Detection ──

        # 1. Covered Call — quantity is shares, so compare shares vs contracts*size
        long_stock_qty = sum(idx.quantity * idx.contract_size for idx in stocks if idx.direction == Direction.LONG)
        short_calls = [idx for idx in shorts if idx.leg_type == LegType.CALL]
        if long_stock_qty > 0 and short_calls:
            total_contracts = sum(idx.quantity for idx in short_calls)
            contract_multiplier = short_calls[0].contract_size
            if long_stock_qty >= total_contracts * contract_multiplier:
                return MarginResult(0.0, 0.0, net_premium, "covered_call")

        # 2. Protective Put (long stock + long put) -> just premium paid
        long_puts = [idx for idx in longs if idx.leg_type == LegType.PUT]
        if long_stock_qty > 0 and long_puts and not shorts:
            return MarginResult(0.0, 0.0, net_premium, "protective_put")

        # 3. Calendar Spread (2 legs, same type, same strike, different expiry)
        #    Must be detected BEFORE vertical spread: a zero-width "vertical"
        #    with different expiries is a calendar, not a credit spread.
        if (
            len(options) == 2
            and options[0].leg_type == options[1].leg_type
            and options[0].strike == options[1].strike
            and options[0].days_to_expiry != options[1].days_to_expiry
        ):
            short_leg = next((lg for lg in options if lg.direction == Direction.SHORT), None)
            long_leg = next((lg for lg in options if lg.direction == Direction.LONG), None)
            if short_leg is not None and long_leg is not None:
                if short_leg.days_to_expiry > long_leg.days_to_expiry:
                    # Short calendar (short far / long near): the long leg
                    # expires first and cannot cap far-horizon risk ->
                    # full naked margin on the short leg, no offset.
                    margin = self._naked_short_margin(short_leg)
                    stype = "short_calendar"
                else:
                    # Long calendar (short near / long far): the long leg's
                    # premium offsets part of the short-leg exposure, capped
                    # at the matched quantity, floored at min_margin.
                    matched_qty = min(short_leg.quantity, long_leg.quantity)
                    offset = long_leg.premium * matched_qty * long_leg.contract_size
                    naked = self._naked_short_margin(short_leg)
                    margin = float(max(naked - offset, float(self.config["min_margin"])))
                    stype = "calendar_spread"
                return MarginResult(
                    margin,
                    margin * float(self.config["maintenance_ratio"]),
                    net_premium,
                    stype,
                )

        # 4. Vertical Spread (2 legs, same type, opposite direction, different strikes)
        if len(options) == 2 and options[0].leg_type == options[1].leg_type:
            sorted_opts = sorted(options, key=lambda x: x.strike)
            if sorted_opts[0].direction != sorted_opts[1].direction:
                short_leg = sorted_opts[0] if sorted_opts[0].direction == Direction.SHORT else sorted_opts[1]
                long_leg = sorted_opts[1] if sorted_opts[0].direction == Direction.SHORT else sorted_opts[0]
                spread_width = abs(long_leg.strike - short_leg.strike)
                net_credit = (short_leg.premium - long_leg.premium) * short_leg.quantity * short_leg.contract_size

                if short_leg.direction == Direction.SHORT:
                    # Credit spread: margin = spread_width * qty * size - net_credit
                    max_loss = spread_width * short_leg.quantity * short_leg.contract_size - net_credit
                    margin = float(max(max_loss, float(self.config["min_margin"])))
                    stype = "bear_call_spread" if short_leg.leg_type == LegType.CALL else "bull_put_spread"
                else:
                    # Debit spread: no additional margin
                    margin = 0.0
                    stype = "bull_call_debit_spread" if short_leg.leg_type == LegType.CALL else "bear_put_debit_spread"

                return MarginResult(margin, margin * float(self.config["maintenance_ratio"]), net_premium, stype)

        # 5. Iron Condor (4 legs: 2 call spread + 2 put spread)
        if len(options) == 4:
            calls = [idx for idx in options if idx.leg_type == LegType.CALL]
            puts = [idx for idx in options if idx.leg_type == LegType.PUT]
            if len(calls) == 2 and len(puts) == 2:
                call_margin = self._spread_margin(calls)
                put_margin = self._spread_margin(puts)
                total = float(max(call_margin, put_margin))
                return MarginResult(total, total * float(self.config["maintenance_ratio"]), net_premium, "iron_condor")

        # 6. Short Straddle/Strangle (2 short legs with different types)
        if len(shorts) == 2 and len(longs) == 0:
            if shorts[0].leg_type != shorts[1].leg_type:
                m1 = self._naked_short_margin(shorts[0])
                m2 = self._naked_short_margin(shorts[1])
                # For straddle/strangle: max(call margin, put margin) + 50% of the other
                total = float(max(m1, m2) + 0.5 * min(m1, m2))
                stype = "short_straddle" if shorts[0].strike == shorts[1].strike else "short_strangle"
                return MarginResult(total, total * float(self.config["maintenance_ratio"]), net_premium, stype)

        # 7. Long Straddle/Strangle (2 long legs) -> no margin
        if len(longs) == 2 and len(shorts) == 0:
            if longs[0].leg_type != longs[1].leg_type:
                return MarginResult(0.0, 0.0, net_premium, "long_straddle")

        # 8. Default: sum of naked margins with portfolio discount
        total_margin = 0.0
        for leg in shorts:
            total_margin += self._naked_short_margin(leg)
        total_margin *= (1 - self.config["portfolio_discount"])

        return MarginResult(
            total_initial_margin=total_margin,
            total_maintenance_margin=total_margin * float(self.config["maintenance_ratio"]),
            net_premium_flow=net_premium,
            strategy_type="multi_leg",
        )

    def _spread_margin(self, spread_legs: list[OptionLeg]) -> float:
        """Calculate margin for a vertical spread (2 legs)."""
        sorted_l = sorted(spread_legs, key=lambda x: x.strike)
        short_leg = sorted_l[0] if sorted_l[0].direction == Direction.SHORT else sorted_l[1]
        long_leg = sorted_l[1] if sorted_l[0].direction == Direction.SHORT else sorted_l[0]

        spread_width = abs(long_leg.strike - short_leg.strike)
        net_credit = (short_leg.premium - long_leg.premium) * short_leg.quantity * short_leg.contract_size
        max_loss = spread_width * short_leg.quantity * short_leg.contract_size - net_credit
        return float(max(max_loss, float(self.config["min_margin"])))

    def check_margin_call(
        self,
        equity: float,
        margin_result: MarginResult,
    ) -> tuple[bool, float]:
        """Check if margin call is triggered.

        Returns (is_margin_call, deficit_amount).
        """
        maintenance = margin_result.total_maintenance_margin
        if equity < maintenance:
            return True, maintenance - equity
        return False, 0.0

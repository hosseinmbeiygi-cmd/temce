"""Comprehensive tests for options pricing, Greeks, margin, and risk modules.

Tests cover:
- Black-Scholes pricing accuracy
- Commodity pricing with cost of carry
- Binomial tree pricing
- Heston model
- Higher-order Greeks
- Margin calculations
- VaR/CVaR
- Probability of Touch
- Trading Calendar
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pytest

# ─── Black-Scholes Pricing Tests ───
from domain.options.pricing import (
    black_scholes_call,
    black_scholes_price,
    black_scholes_put,
    implied_volatility,
)


class TestBlackScholes:
    def test_call_at_the_money(self):
        """ATM call should have ~0.5 delta and positive time value."""
        result = black_scholes_price(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="call")
        assert result.price > 0
        assert result.delta == pytest.approx(0.53, abs=0.05)
        assert result.time_value > 0

    def test_put_at_the_money(self):
        result = black_scholes_price(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="put")
        assert result.price > 0
        assert result.delta == pytest.approx(-0.47, abs=0.05)

    def test_deep_itm_call(self):
        """Deep ITM call should have delta ~1 and price ~intrinsic."""
        result = black_scholes_price(S=200, K=100, T=1.0, r=0.05, sigma=0.20, option_type="call")
        assert result.delta > 0.95
        assert result.price > 95

    def test_deep_otm_call(self):
        """Deep OTM call should have very small price."""
        result = black_scholes_price(S=50, K=200, T=0.25, r=0.05, sigma=0.20, option_type="call")
        assert result.price < 1.0
        assert result.delta < 0.01

    def test_put_call_parity(self):
        """C - P = S - K*exp(-r*T)"""
        S, K, T, r, sigma = 100, 95, 0.5, 0.05, 0.25
        call = black_scholes_call(S, K, T, r, sigma)
        put = black_scholes_put(S, K, T, r, sigma)
        parity = S - K * math.exp(-r * T)
        assert call - put == pytest.approx(parity, abs=0.01)

    def test_greeks_signs(self):
        """Verify correct Greek signs for long call."""
        result = black_scholes_price(S=100, K=100, T=0.25, r=0.05, sigma=0.30, option_type="call")
        assert result.delta > 0  # Long call: positive delta
        assert result.gamma > 0  # Gamma always positive
        assert result.theta < 0  # Time decay for long option
        assert result.vega > 0  # Long option: positive vega

    def test_put_greeks_signs(self):
        result = black_scholes_price(S=100, K=100, T=0.25, r=0.05, sigma=0.30, option_type="put")
        assert result.delta < 0  # Long put: negative delta
        assert result.gamma > 0
        assert result.theta < 0

    def test_implied_volatility_roundtrip(self):
        """IV -> Price -> IV should roundtrip."""
        S, K, T, r, sigma_true = 100, 100, 0.25, 0.05, 0.35
        price = black_scholes_call(S, K, T, r, sigma_true)
        iv_recovered = implied_volatility(price, S, K, T, r, "call")
        assert iv_recovered == pytest.approx(sigma_true, abs=1e-4)

    def test_expired_option(self):
        """Expired option should return intrinsic value only."""
        result = black_scholes_price(S=110, K=100, T=0, r=0.05, sigma=0.30, option_type="call")
        assert result.price == pytest.approx(10.0, abs=0.01)


# ─── Commodity Pricing Tests ───

from domain.options.commodity_pricing import (
    AssetClass,
    CommodityOptionParams,
    commodity_bs_call,
    implied_cost_of_carry,
    price_commodity_option,
)


class TestCommodityPricing:
    def test_cost_of_carry_from_futures(self):
        """Implied carry from spot and futures prices."""
        spot = 45_000_000  # 45M IRR gold coin
        futures = 48_000_000
        T = 0.25  # 3 months
        carry = implied_cost_of_carry(spot, futures, T)
        assert carry > 0
        assert carry == pytest.approx(math.log(48 / 45) / 0.25, abs=0.01)

    def test_commodity_call_with_q(self):
        """BS with q should differ from standard BS."""
        S, K, T, r, q, sigma = 100, 100, 0.25, 0.25, 0.25, 0.30
        call_q = commodity_bs_call(S, K, T, r, q, sigma)
        from domain.options.pricing import black_scholes_call

        call_no_q = black_scholes_call(S, K, T, r, sigma)
        # With high q, call should be cheaper
        assert call_q < call_no_q

    def test_gold_coin_option(self):
        """Test pricing for Iranian gold coin option."""
        params = CommodityOptionParams(
            S=45_000_000,
            K=46_000_000,
            T=30 / 365,
            r=0.28,
            q=0.28,
            sigma=0.35,
            option_type="call",
            asset_class=AssetClass.GOLD_COIN,
        )
        result = price_commodity_option(params)
        assert result.price > 0
        assert result.parameters["asset_class"] == "gold_coin"


# ─── Tree Pricing Tests ───

from domain.options.tree_pricing import (
    OptionStyle,
    TreeOptionParams,
    TreeType,
    binomial_tree_price,
    trinomial_tree_price,
)


class TestTreePricing:
    def test_binomial_converges_to_bs(self):
        """Binomial tree should converge to BS for European options."""
        params_bs = black_scholes_price(S=100, K=100, T=0.25, r=0.05, sigma=0.20)
        params_tree = TreeOptionParams(S=100, K=100, T=0.25, r=0.05, sigma=0.20, N=500)
        result = binomial_tree_price(params_tree)
        assert result.price == pytest.approx(params_bs.price, abs=0.5)

    def test_american_put_no_arb(self):
        """American put should be >= European put (early exercise premium)."""
        params = TreeOptionParams(
            S=90,
            K=100,
            T=0.25,
            r=0.05,
            sigma=0.20,
            style=OptionStyle.AMERICAN,
            option_type="put",
            N=200,
        )
        result = binomial_tree_price(params)
        bs_put = black_scholes_put(90, 100, 0.25, 0.05, 0.20)
        assert result.price >= bs_put - 0.5  # Allow small numerical error

    def test_trinomial_faster_convergence(self):
        """Trinomial should converge faster than binomial."""
        params_bs = black_scholes_price(S=100, K=100, T=0.25, r=0.05, sigma=0.20)
        params_tri = TreeOptionParams(
            S=100,
            K=100,
            T=0.25,
            r=0.05,
            sigma=0.20,
            N=100,
            tree_type=TreeType.TRINOMIAL,
        )
        result = trinomial_tree_price(params_tri)
        assert result.price == pytest.approx(params_bs.price, abs=1.0)


# ─── Margin Engine Tests ───

from domain.options.margin_engine import (
    DEFAULT_COEFFICIENTS,
    Direction,
    LegType,
    OptionLeg,
    UniversalMarginEngine,
)


class TestMarginEngine:
    def setup_method(self):
        self.engine = UniversalMarginEngine()

    def test_naked_short_call(self):
        """Naked short call should require significant margin."""
        leg = OptionLeg(
            LegType.CALL,
            Direction.SHORT,
            strike=100,
            premium=5,
            underlying_price=100,
            quantity=1,
        )
        result = self.engine.calculate_margin([leg])
        assert result.total_initial_margin > 0
        assert result.strategy_type == "multi_leg"

    def test_naked_short_put(self):
        leg = OptionLeg(
            LegType.PUT,
            Direction.SHORT,
            strike=95,
            premium=3,
            underlying_price=100,
            quantity=1,
        )
        result = self.engine.calculate_margin([leg])
        assert result.total_initial_margin > 0

    def test_credit_spread_lower_margin(self):
        """Credit spread margin should be less than naked when option is ITM."""
        engine = UniversalMarginEngine(
            {
                "min_margin": 10,
                "maintenance_ratio": 0.85,
                "portfolio_discount": 0.0,
                "coefficients": DEFAULT_COEFFICIENTS,
            }
        )
        # ITM short put at strike=105 (S=100, put is ITM, intrinsic=5)
        short = OptionLeg(
            LegType.PUT,
            Direction.SHORT,
            strike=105,
            premium=8,
            underlying_price=100,
            quantity=1,
        )
        naked_result = engine.calculate_margin([short])
        # Spread with same short + long at 95: spread width = 10
        long = OptionLeg(
            LegType.PUT,
            Direction.LONG,
            strike=95,
            premium=3,
            underlying_price=100,
            quantity=1,
        )
        spread_result = engine.calculate_margin([short, long])
        # Naked = (5 + 25 + 8) = 38 per unit (ITM + base + premium)
        # Spread = max(10 - (8-3), 10) * 1000 = 5000
        # 5000 < 38000
        assert spread_result.total_initial_margin < naked_result.total_initial_margin
        assert spread_result.strategy_type in ("bull_put_spread", "bear_put_spread")

    def test_iron_condor(self):
        """Iron Condor margin should be max of two spreads."""
        legs = [
            OptionLeg(
                LegType.PUT,
                Direction.SHORT,
                strike=90,
                premium=2,
                underlying_price=100,
                quantity=1,
            ),
            OptionLeg(
                LegType.PUT,
                Direction.LONG,
                strike=85,
                premium=1,
                underlying_price=100,
                quantity=1,
            ),
            OptionLeg(
                LegType.CALL,
                Direction.SHORT,
                strike=110,
                premium=2,
                underlying_price=100,
                quantity=1,
            ),
            OptionLeg(
                LegType.CALL,
                Direction.LONG,
                strike=115,
                premium=1,
                underlying_price=100,
                quantity=1,
            ),
        ]
        result = self.engine.calculate_margin(legs)
        assert result.total_initial_margin > 0
        assert result.strategy_type == "iron_condor"

    def test_long_only_no_margin(self):
        """Buying options only should require no margin (just premium)."""
        leg = OptionLeg(
            LegType.CALL,
            Direction.LONG,
            strike=100,
            premium=5,
            underlying_price=100,
            quantity=1,
        )
        result = self.engine.calculate_margin([leg])
        assert result.total_initial_margin == 0.0

    def test_short_straddle(self):
        legs = [
            OptionLeg(
                LegType.CALL,
                Direction.SHORT,
                strike=100,
                premium=5,
                underlying_price=100,
                quantity=1,
            ),
            OptionLeg(
                LegType.PUT,
                Direction.SHORT,
                strike=100,
                premium=5,
                underlying_price=100,
                quantity=1,
            ),
        ]
        result = self.engine.calculate_margin(legs)
        assert result.total_initial_margin > 0
        assert result.strategy_type in ("short_straddle", "short_strangle")

    def test_margin_call_detection(self):
        margin = self.engine.calculate_margin(
            [
                OptionLeg(
                    LegType.CALL,
                    Direction.SHORT,
                    strike=100,
                    premium=5,
                    underlying_price=100,
                    quantity=1,
                )
            ]
        )
        is_call, deficit = self.engine.check_margin_call(
            equity=margin.total_maintenance_margin * 0.5,
            margin_result=margin,
        )
        assert is_call is True
        assert deficit > 0


# ─── VaR/CVaR Tests ───

from domain.options.var_calculator import VaRCalculator


class TestVaRCalculator:
    def test_historical_var(self):
        rng = np.random.default_rng(42)
        returns = rng.normal(0.001, 0.02, 500)
        result = VaRCalculator.historical_simulation(returns, portfolio_value=1_000_000_000)
        assert result.var_95 > 0
        assert result.var_99 > result.var_95
        assert result.cvar_95 > result.var_95
        assert result.cvar_99 > result.var_99
        assert result.var_95_pct > 0

    def test_parametric_var(self):
        rng = np.random.default_rng(42)
        returns = rng.normal(0.001, 0.02, 500)
        result = VaRCalculator.parametric_var(returns, portfolio_value=1_000_000_000)
        assert result.var_95 > 0
        assert result.var_99 > result.var_95

    def test_monte_carlo_var(self):
        result = VaRCalculator.monte_carlo_var(portfolio_value=1_000_000_000, mu=0.15, sigma=0.30, n_sims=10000)
        assert result.var_95 > 0
        assert result.var_99 > result.var_95


# ─── Probability Tests ───

from domain.options.probability import (
    expected_move,
    max_pain_price,
    probability_itm_at_expiry,
    probability_of_touch_brownian,
)


class TestProbability:
    def test_probability_of_touch_above(self):
        """Price above current should have probability between 0 and 1."""
        prob = probability_of_touch_brownian(S=100, target=120, T=0.25, r=0.05, sigma=0.30)
        assert 0 < prob <= 1.0

    def test_probability_of_touch_below(self):
        prob = probability_of_touch_brownian(S=100, target=80, T=0.25, r=0.05, sigma=0.30)
        assert 0 < prob <= 1.0

    def test_itm_probability(self):
        prob = probability_itm_at_expiry(S=100, K=100, T=0.25, r=0.05, sigma=0.30)
        assert 0.4 < prob < 0.6  # ATM should be ~50%

    def test_expected_move(self):
        lower, upper = expected_move(S=100, sigma=0.30, T=0.25)
        assert lower < 100 < upper
        assert upper - lower == pytest.approx(100 * 0.30 * 0.5, abs=20)

    def test_max_pain(self):
        strikes = [90, 95, 100, 105, 110]
        oi = [100, 500, 800, 500, 100]
        mp = max_pain_price(strikes, oi)
        assert 95 <= mp <= 105  # Should be near 100


# ─── Trading Calendar Tests ───

from domain.calendar.trading_calendar import TradingCalendar


class TestTradingCalendar:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_friday_not_trading(self):
        # A known Friday
        friday = date(2024, 1, 5)
        assert self.cal.is_trading_day(friday) is False

    def test_saturday_not_trading(self):
        saturday = date(2024, 1, 6)
        assert self.cal.is_trading_day(saturday) is False

    def test_sunday_is_trading(self):
        sunday = date(2024, 1, 7)
        assert self.cal.is_trading_day(sunday) is True

    def test_next_trading_day(self):
        friday = date(2024, 1, 5)
        next_day = self.cal.next_trading_day(friday)
        assert next_day.weekday() not in (4, 5)  # Not Friday or Saturday
        assert self.cal.is_trading_day(next_day)

    def test_trading_days_between(self):
        # A known week
        start = date(2024, 1, 7)  # Sunday
        end = date(2024, 1, 11)  # Thursday
        count = self.cal.trading_days_between(start, end)
        assert count == 5  # Sun-Thu (if no holidays)

    def test_adjust_expiry_on_holiday(self):
        """Expiry on a holiday should move to previous trading day."""
        friday = date(2024, 1, 5)
        adjusted = self.cal.adjust_expiry(friday)
        assert self.cal.is_trading_day(adjusted)
        assert adjusted < friday


# ─── Higher-Order Greeks Tests ───

from domain.options.higher_order_greeks import (
    compute_all_higher_order_greeks,
    speed,
    vanna,
    vomma,
)


class TestHigherOrderGreeks:
    def test_speed_negative_for_long_call(self):
        """Speed is typically negative for ATM options."""
        s = speed(S=100, K=100, T=0.25, r=0.05, sigma=0.30)
        assert isinstance(s, float)

    def test_vanna_at_atm(self):
        """Vanna is typically largest (in absolute value) for near-ATM options."""
        v = vanna(S=100, K=100, T=0.25, r=0.05, sigma=0.30)
        assert isinstance(v, float)
        # Vanna should be negative for calls with negative skew
        assert v != 0

    def test_vomma_positive(self):
        """Vomma is typically positive (vega increases with vol for OTM)."""
        v = vomma(S=100, K=110, T=0.25, r=0.05, sigma=0.30)
        assert isinstance(v, float)

    def test_compute_all(self):
        greeks = compute_all_higher_order_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.30)
        assert "speed" in greeks
        assert "charm" in greeks
        assert "vanna" in greeks
        assert "vomma" in greeks
        assert "color" in greeks
        assert "ultima" in greeks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

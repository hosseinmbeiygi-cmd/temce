"""Regression guards for commodity option pricing (IME gold/commodity path).

Guards added after audit: invalid S/K/futures inputs used to raise
ZeroDivisionError (math.log / gamma denominator) instead of returning a
safe result, and degenerate-but-valid params could push greeks to inf/nan
which then broke JSON serialization downstream.
"""

from __future__ import annotations

import math

import pytest

from domain.options.commodity_pricing import (
    AssetClass,
    CommodityOptionParams,
    implied_vol_commodity_option,
    price_commodity_option,
)


def _params(**overrides) -> CommodityOptionParams:
    base: dict = {
        "S": 45_000_000.0,
        "K": 46_000_000.0,
        "T": 30 / 365,
        "r": 0.28,
        "q": 0.28,
        "sigma": 0.35,
        "option_type": "call",
        "asset_class": AssetClass.GOLD_COIN,
    }
    base.update(overrides)
    return CommodityOptionParams(**base)


class TestInvalidInputGuards:
    def test_zero_spot_returns_safe_zero(self):
        result = price_commodity_option(_params(S=0.0))
        assert result.price == 0.0
        assert result.parameters.get("error") == "invalid_inputs"

    def test_zero_strike_returns_safe_zero(self):
        result = price_commodity_option(_params(K=0.0))
        assert result.price == 0.0
        assert result.parameters.get("error") == "invalid_inputs"

    def test_negative_strike_returns_safe_zero(self):
        result = price_commodity_option(_params(K=-1.0))
        assert result.price == 0.0

    def test_black76_zero_futures_returns_safe_zero(self):
        """Black-76 path must guard the futures price too (log(F/K))."""
        result = price_commodity_option(_params(futures_price=0.0))
        assert result.price == 0.0
        assert result.parameters.get("error") == "invalid_inputs"

    def test_black76_negative_futures_returns_safe_zero(self):
        result = price_commodity_option(_params(futures_price=-100.0))
        assert result.price == 0.0


class TestDegenerateFiniteOutputs:
    def test_tiny_vol_and_time_keep_greeks_finite(self):
        """Degenerate-but-valid params must never emit inf/nan greeks."""
        params = _params(S=1.0, K=1.0, r=0.0, T=1e-4, sigma=1e-6)
        result = price_commodity_option(params)
        for name in ("price", "delta", "gamma", "theta", "vega", "rho"):
            value = getattr(result, name)
            assert math.isfinite(value), f"{name} is not finite: {value}"

    def test_atm_tiny_vol_greeks_finite(self):
        params = _params(S=100.0, K=100.0, r=0.0, T=1 / 365, sigma=1e-4)
        result = price_commodity_option(params)
        assert math.isfinite(result.gamma)
        assert math.isfinite(result.vega)
        assert math.isfinite(result.theta)


class TestHappyPathUnchanged:
    def test_valid_gold_coin_option_still_prices(self):
        result = price_commodity_option(_params())
        assert result.price > 0
        assert math.isfinite(result.price)
        assert result.parameters.get("asset_class") == "gold_coin"


class TestImpliedVolGuards:
    def test_invalid_spot_returns_initial_guess(self):
        sigma = implied_vol_commodity_option(
            market_price=1_000_000.0, S=0.0, K=46_000_000.0, T=30 / 365, r=0.28
        )
        assert sigma == pytest.approx(0.3)

    def test_zero_maturity_returns_initial_guess(self):
        sigma = implied_vol_commodity_option(
            market_price=1_000_000.0, S=45_000_000.0, K=46_000_000.0, T=0.0, r=0.28
        )
        assert sigma == pytest.approx(0.3)

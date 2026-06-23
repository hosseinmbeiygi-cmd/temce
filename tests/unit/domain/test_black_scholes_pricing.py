from __future__ import annotations

import math

import pytest


# ---------------------------------------------------------------------------
# Fixtures: common test parameters
# ---------------------------------------------------------------------------

@pytest.fixture
def atm_params() -> dict:
    """At-the-money call option: S = K = 100, T = 1 year, r = 5%, sigma = 20%."""
    return {"S": 100.0, "K": 100.0, "T": 1.0, "r": 0.05, "sigma": 0.2}


@pytest.fixture
def itm_call_params() -> dict:
    """In-the-money call: S=110, K=100."""
    return {"S": 110.0, "K": 100.0, "T": 1.0, "r": 0.05, "sigma": 0.2}


@pytest.fixture
def otm_call_params() -> dict:
    """Out-of-the-money call: S=90, K=100."""
    return {"S": 90.0, "K": 100.0, "T": 1.0, "r": 0.05, "sigma": 0.2}


# ---------------------------------------------------------------------------
# _d1 / _d2
# ---------------------------------------------------------------------------

class TestD1D2:
    def test_d1_atm(self, atm_params):
        from domain.options.pricing import _d1

        p = atm_params
        # d1 = (ln(100/100) + (0.05 + 0.5*0.04)*1) / (0.2 * 1)
        #     = (0 + 0.07) / 0.2 = 0.35
        d1 = _d1(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        assert d1 == pytest.approx(0.35, abs=1e-12)

    def test_d2_atm(self, atm_params):
        from domain.options.pricing import _d1, _d2

        p = atm_params
        d1 = _d1(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        d2 = _d2(d1, p["sigma"], p["T"])
        # d2 = 0.35 - 0.2 = 0.15
        assert d2 == pytest.approx(0.15, abs=1e-12)

    def test_d1_deep_itm(self):
        from domain.options.pricing import _d1

        # S >> K → large positive d1
        d1 = _d1(200.0, 100.0, 1.0, 0.05, 0.3)
        assert d1 > 2.0

    def test_d1_deep_otm(self):
        from domain.options.pricing import _d1

        # S << K → large negative d1
        d1 = _d1(50.0, 100.0, 1.0, 0.05, 0.3)
        assert d1 < -1.0


# ---------------------------------------------------------------------------
# black_scholes_call
# ---------------------------------------------------------------------------

class TestBlackScholesCall:
    def test_call_atm_price(self, atm_params):
        from domain.options.pricing import black_scholes_call

        p = atm_params
        price = black_scholes_call(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        # ATM call ≈ 10.45 (known reference)
        assert price == pytest.approx(10.45, abs=0.1)

    def test_call_itm(self, itm_call_params):
        from domain.options.pricing import black_scholes_call

        p = itm_call_params
        price = black_scholes_call(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        # ITM call should be worth more than ATM (~10.45) and less than S
        assert 10.0 < price < 110.0
        # Should exceed lower bound from put-call parity: C >= S - K*exp(-rT)
        lower_bound = p["S"] - p["K"] * math.exp(-p["r"] * p["T"])
        assert price > lower_bound

    def test_call_otm(self, otm_call_params):
        from domain.options.pricing import black_scholes_call

        p = otm_call_params
        price = black_scholes_call(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        # OTM call should be worth less than ATM
        assert price < 10.0
        assert price > 0.0

    def test_call_zero_vol(self, atm_params):
        from domain.options.pricing import black_scholes_call

        p = atm_params
        price = black_scholes_call(p["S"], p["K"], p["T"], p["r"], 0.0)
        # sigma=0 → intrinsic value
        assert price == max(0.0, p["S"] - p["K"])

    def test_call_zero_time(self, atm_params):
        from domain.options.pricing import black_scholes_call

        p = atm_params
        price = black_scholes_call(p["S"], p["K"], 0.0, p["r"], p["sigma"])
        # T=0 → intrinsic value
        assert price == max(0.0, p["S"] - p["K"])

    def test_call_negative_time(self, atm_params):
        from domain.options.pricing import black_scholes_call

        p = atm_params
        price = black_scholes_call(p["S"], p["K"], -1.0, p["r"], p["sigma"])
        assert price == max(0.0, p["S"] - p["K"])

    def test_call_zero_strike(self, atm_params):
        from domain.options.pricing import black_scholes_call

        p = atm_params
        # K=0 → call = S (you get the asset for free)
        price = black_scholes_call(p["S"], 0.0, p["T"], p["r"], p["sigma"])
        assert price == pytest.approx(p["S"], abs=1e-6)

    def test_call_zero_underlying(self, atm_params):
        from domain.options.pricing import black_scholes_call

        p = atm_params
        price = black_scholes_call(0.0, p["K"], p["T"], p["r"], p["sigma"])
        assert price == 0.0


# ---------------------------------------------------------------------------
# black_scholes_put
# ---------------------------------------------------------------------------

class TestBlackScholesPut:
    def test_put_atm_price(self, atm_params):
        from domain.options.pricing import black_scholes_put

        p = atm_params
        price = black_scholes_put(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        # ATM put ≈ 5.57 (known reference)
        assert price == pytest.approx(5.57, abs=0.1)

    def test_put_itm(self):
        from domain.options.pricing import black_scholes_put

        # S=90, K=100 → ITM put
        price = black_scholes_put(90.0, 100.0, 1.0, 0.05, 0.2)
        assert price > 5.0

    def test_put_otm(self):
        from domain.options.pricing import black_scholes_put

        # S=110, K=100 → OTM put
        price = black_scholes_put(110.0, 100.0, 1.0, 0.05, 0.2)
        assert price < 5.0
        assert price > 0.0

    def test_put_zero_vol(self, atm_params):
        from domain.options.pricing import black_scholes_put

        p = atm_params
        price = black_scholes_put(p["S"], p["K"], p["T"], p["r"], 0.0)
        assert price == max(0.0, p["K"] - p["S"])

    def test_put_zero_time(self, atm_params):
        from domain.options.pricing import black_scholes_put

        p = atm_params
        price = black_scholes_put(p["S"], p["K"], 0.0, p["r"], p["sigma"])
        assert price == max(0.0, p["K"] - p["S"])

    def test_put_zero_underlying(self, atm_params):
        from domain.options.pricing import black_scholes_put

        p = atm_params
        # S=0 triggers edge case check (S <= 0) → returns intrinsic value K - S
        price = black_scholes_put(0.0, p["K"], p["T"], p["r"], p["sigma"])
        assert price == p["K"]  # intrinsic = K - 0


# ---------------------------------------------------------------------------
# Put-Call parity
# ---------------------------------------------------------------------------

class TestPutCallParity:
    """Verify C - P = S - K * exp(-rT) for all test cases."""

    def test_atm_parity(self, atm_params):
        from domain.options.pricing import black_scholes_call, black_scholes_put

        p = atm_params
        c = black_scholes_call(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        pu = black_scholes_put(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        lhs = c - pu
        rhs = p["S"] - p["K"] * math.exp(-p["r"] * p["T"])
        assert lhs == pytest.approx(rhs, abs=1e-10)

    def test_itm_parity(self, itm_call_params):
        from domain.options.pricing import black_scholes_call, black_scholes_put

        p = itm_call_params
        c = black_scholes_call(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        pu = black_scholes_put(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        lhs = c - pu
        rhs = p["S"] - p["K"] * math.exp(-p["r"] * p["T"])
        assert lhs == pytest.approx(rhs, abs=1e-10)

    def test_otm_parity(self, otm_call_params):
        from domain.options.pricing import black_scholes_call, black_scholes_put

        p = otm_call_params
        c = black_scholes_call(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        pu = black_scholes_put(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        lhs = c - pu
        rhs = p["S"] - p["K"] * math.exp(-p["r"] * p["T"])
        assert lhs == pytest.approx(rhs, abs=1e-10)

    def test_high_vol_parity(self):
        from domain.options.pricing import black_scholes_call, black_scholes_put

        c = black_scholes_call(100, 100, 1, 0.05, 0.8)
        pu = black_scholes_put(100, 100, 1, 0.05, 0.8)
        lhs = c - pu
        rhs = 100 - 100 * math.exp(-0.05)
        assert lhs == pytest.approx(rhs, abs=1e-10)


# ---------------------------------------------------------------------------
# black_scholes_price (full pricing with Greeks)
# ---------------------------------------------------------------------------

class TestBlackScholesPrice:
    def test_price_call(self, atm_params):
        from domain.options.pricing import black_scholes_price

        p = atm_params
        result = black_scholes_price(p["S"], p["K"], p["T"], p["r"], p["sigma"], option_type="call")
        assert result.model == "black_scholes"
        assert result.price == pytest.approx(10.45, abs=0.1)
        assert result.intrinsic_value == 0.0  # ATM
        assert result.time_value == pytest.approx(result.price, abs=1e-6)

    def test_price_put(self, atm_params):
        from domain.options.pricing import black_scholes_price

        p = atm_params
        result = black_scholes_price(p["S"], p["K"], p["T"], p["r"], p["sigma"], option_type="put")
        assert result.model == "black_scholes"
        assert result.price == pytest.approx(5.57, abs=0.1)
        assert result.intrinsic_value == 0.0  # ATM

    def test_call_delta_range(self, atm_params):
        from domain.options.pricing import black_scholes_price

        p = atm_params
        result = black_scholes_price(p["S"], p["K"], p["T"], p["r"], p["sigma"], option_type="call")
        # Call delta between 0 and 1
        assert 0.0 < result.delta < 1.0

    def test_put_delta_range(self, atm_params):
        from domain.options.pricing import black_scholes_price

        p = atm_params
        result = black_scholes_price(p["S"], p["K"], p["T"], p["r"], p["sigma"], option_type="put")
        # Put delta between -1 and 0
        assert -1.0 < result.delta < 0.0

    def test_gamma_non_negative(self, atm_params):
        from domain.options.pricing import black_scholes_price

        p = atm_params
        result = black_scholes_price(p["S"], p["K"], p["T"], p["r"], p["sigma"], option_type="call")
        # Gamma is always non-negative
        assert result.gamma >= 0.0

        result_put = black_scholes_price(p["S"], p["K"], p["T"], p["r"], p["sigma"], option_type="put")
        assert result_put.gamma == pytest.approx(result.gamma, abs=1e-12)

    def test_vega_positive(self, atm_params):
        from domain.options.pricing import black_scholes_price

        p = atm_params
        result = black_scholes_price(p["S"], p["K"], p["T"], p["r"], p["sigma"], option_type="call")
        # Vega is positive for both calls and puts
        assert result.vega > 0.0

    def test_itm_call_intrinsic(self, itm_call_params):
        from domain.options.pricing import black_scholes_price

        p = itm_call_params
        result = black_scholes_price(p["S"], p["K"], p["T"], p["r"], p["sigma"], option_type="call")
        assert result.intrinsic_value == p["S"] - p["K"]
        assert result.time_value > 0.0

    def test_price_edge_case_zero_time(self, atm_params):
        from domain.options.pricing import black_scholes_price

        p = atm_params
        result = black_scholes_price(p["S"], p["K"], 0.0, p["r"], p["sigma"], option_type="call")
        assert result.price == 0.0  # ATM at expiry
        assert result.time_value == 0.0

    def test_price_parameters_stored(self, atm_params):
        from domain.options.pricing import black_scholes_price

        p = atm_params
        result = black_scholes_price(p["S"], p["K"], p["T"], p["r"], p["sigma"], option_type="call")
        assert result.parameters["S"] == p["S"]
        assert result.parameters["K"] == p["K"]
        assert result.parameters["option_type"] == "call"


# ---------------------------------------------------------------------------
# implied_volatility (Newton-Raphson)
# ---------------------------------------------------------------------------

class TestImpliedVolatility:
    def test_iv_recovers_input_vol(self, atm_params):
        from domain.options.pricing import black_scholes_call, implied_volatility

        p = atm_params
        known_price = black_scholes_call(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        iv = implied_volatility(known_price, p["S"], p["K"], p["T"], p["r"], option_type="call")
        assert iv == pytest.approx(p["sigma"], abs=1e-4)

    def test_iv_put_recovers_input_vol(self, atm_params):
        from domain.options.pricing import black_scholes_put, implied_volatility

        p = atm_params
        known_price = black_scholes_put(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        iv = implied_volatility(known_price, p["S"], p["K"], p["T"], p["r"], option_type="put")
        assert iv == pytest.approx(p["sigma"], abs=1e-4)

    def test_iv_high_vol(self):
        from domain.options.pricing import black_scholes_call, implied_volatility

        price = black_scholes_call(100, 100, 1, 0.05, 0.6)
        iv = implied_volatility(price, 100, 100, 1, 0.05, option_type="call")
        assert iv == pytest.approx(0.6, abs=1e-3)

    def test_iv_low_vol(self):
        from domain.options.pricing import black_scholes_call, implied_volatility

        price = black_scholes_call(100, 100, 1, 0.05, 0.05)
        iv = implied_volatility(price, 100, 100, 1, 0.05, option_type="call")
        assert iv == pytest.approx(0.05, abs=1e-4)

    def test_iv_itm(self, itm_call_params):
        from domain.options.pricing import black_scholes_call, implied_volatility

        p = itm_call_params
        price = black_scholes_call(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        iv = implied_volatility(price, p["S"], p["K"], p["T"], p["r"], option_type="call")
        assert iv == pytest.approx(p["sigma"], abs=1e-4)

    def test_iv_different_initial_guess(self, atm_params):
        from domain.options.pricing import black_scholes_call, implied_volatility

        p = atm_params
        price = black_scholes_call(p["S"], p["K"], p["T"], p["r"], p["sigma"])
        # Start with a wildly different guess
        iv = implied_volatility(price, p["S"], p["K"], p["T"], p["r"], option_type="call", initial_guess=0.8)
        assert iv == pytest.approx(p["sigma"], abs=1e-3)

    def test_iv_zero_vega_limit(self, atm_params):
        """When T=0, vega approaches 0 and IV should handle gracefully."""
        from domain.options.pricing import implied_volatility

        p = atm_params
        iv = implied_volatility(5.0, p["S"], p["K"], 0.001, p["r"], option_type="call")
        # Should not crash, returns some sigma value
        assert iv >= 0.0

"""Unit tests for Black-76 pricing, analytical Greeks and implied volatility.

Benchmarks are computed independently from the Black-76 definition:

    d1 = (ln(F/K) + 0.5σ²T) / (σ√T)
    d2 = d1 - σ√T
    C  = e^(-rT) [F N(d1) - K N(d2)]
    P  = e^(-rT) [K N(-d2) - F N(-d1)]
    θ  = ∂V/∂t = -∂V/∂T = -F e^(-rT) φ(d1) σ/(2√T) + r·V   (call and put alike)

Pure math only — no DB, no network.
"""

from __future__ import annotations

import math

import pytest

from services.gold.black76_engine import (
    black76_price,
    calculate_greeks,
    implied_volatility,
)

# Independent reference values (Black-76 definition, scipy norm).
BENCH_CALL = 12.6499787281
BENCH_PUT = 2.7988593320
BENCH_DELTA_CALL = 0.7419251180
BENCH_DELTA_PUT = -0.2431868216
BENCH_GAMMA = 0.0175897191
BENCH_VEGA = 21.9871489164
# Audit FIN-01: these two constants used to hold -3.6505112369 / -6.3103134738,
# which were the output of the old (wrong) theta expression — the engine added
# an extra +r·F·e^{-rT}·N(d1) on calls and used -r·V on puts. The values below
# are θ = -∂V/∂T and agree with a central finite difference of black76_price to
# ~1e-9 (see tests/unit/services/test_black76_theta_derivative.py).
BENCH_THETA_CALL = -5.1172878673
BENCH_THETA_PUT = -5.4128214491

PARITY_CASES = [
    (100.0, 100.0, 1.0, 0.05, 0.20),
    (100.0, 90.0, 0.5, 0.03, 0.25),
    (120.0, 100.0, 0.25, 0.02, 0.35),
    (80.0, 100.0, 2.0, 0.00, 0.40),
    (1_000.0, 1_200.0, 0.1, 0.15, 0.60),
]


class TestBlack76Price:
    def test_call_benchmark(self):
        assert black76_price(100.0, 90.0, 0.5, 0.03, 0.25, "call") == pytest.approx(
            BENCH_CALL, abs=1e-9
        )

    def test_put_benchmark(self):
        assert black76_price(100.0, 90.0, 0.5, 0.03, 0.25, "put") == pytest.approx(
            BENCH_PUT, abs=1e-9
        )

    def test_second_benchmark(self):
        assert black76_price(120.0, 100.0, 0.25, 0.02, 0.35, "call") == pytest.approx(
            21.3632287210, abs=1e-9
        )
        assert black76_price(120.0, 100.0, 0.25, 0.02, 0.35, "put") == pytest.approx(
            1.4629791371, abs=1e-9
        )

    @pytest.mark.parametrize("F,K,T,r,sigma", PARITY_CASES)
    def test_put_call_parity(self, F, K, T, r, sigma):
        call = black76_price(F, K, T, r, sigma, "call")
        put = black76_price(F, K, T, r, sigma, "put")
        assert call - put == pytest.approx(math.exp(-r * T) * (F - K), abs=1e-9)

    def test_zero_maturity_returns_discounted_intrinsic(self):
        assert black76_price(110.0, 100.0, 0.0, 0.05, 0.2, "call") == pytest.approx(
            10.0
        )
        assert black76_price(90.0, 100.0, 0.0, 0.05, 0.2, "call") == pytest.approx(0.0)
        assert black76_price(90.0, 100.0, 0.0, 0.05, 0.2, "put") == pytest.approx(10.0)
        assert black76_price(110.0, 100.0, 0.0, 0.05, 0.2, "put") == pytest.approx(0.0)

    def test_tiny_maturity_converges_to_discounted_intrinsic(self):
        T, r = 1e-6, 0.03
        discounted_intrinsic = (110.0 - 100.0) * math.exp(-r * T)
        value = black76_price(110.0, 100.0, T, r, 0.25, "call")
        assert value == pytest.approx(discounted_intrinsic, abs=1e-6)
        assert value >= discounted_intrinsic

    def test_deep_in_the_money_call_approaches_forward_minus_strike(self):
        T, r = 0.5, 0.03
        call = black76_price(100.0, 1.0, T, r, 0.2, "call")
        assert call == pytest.approx(math.exp(-r * T) * (100.0 - 1.0), abs=1e-6)

    def test_deep_out_of_the_money_call_is_effectively_zero(self):
        assert black76_price(100.0, 1_000_000.0, 0.5, 0.03, 0.2, "call") == (
            pytest.approx(0.0, abs=1e-12)
        )

    def test_prices_respect_no_arbitrage_bounds(self):
        F, K, T, r, sigma = 100.0, 105.0, 0.75, 0.04, 0.3
        call = black76_price(F, K, T, r, sigma, "call")
        put = black76_price(F, K, T, r, sigma, "put")
        df = math.exp(-r * T)
        assert 0.0 <= call <= df * F
        assert 0.0 <= put <= df * K

    def test_call_increases_with_forward(self):
        values = [
            black76_price(F, 100.0, 0.5, 0.03, 0.25, "call")
            for F in (80.0, 90.0, 100.0, 110.0, 120.0)
        ]
        assert values == sorted(values)
        assert len(set(values)) == len(values)

    def test_put_decreases_with_forward(self):
        values = [
            black76_price(F, 100.0, 0.5, 0.03, 0.25, "put")
            for F in (80.0, 90.0, 100.0, 110.0, 120.0)
        ]
        assert values == sorted(values, reverse=True)

    def test_call_and_put_increase_with_volatility(self):
        calls = [black76_price(100.0, 100.0, 0.5, 0.03, s, "call") for s in (0.1, 0.3, 0.6)]
        puts = [black76_price(100.0, 100.0, 0.5, 0.03, s, "put") for s in (0.1, 0.3, 0.6)]
        assert calls == sorted(calls)
        assert puts == sorted(puts)

    def test_option_type_is_case_insensitive(self):
        assert black76_price(100.0, 90.0, 0.5, 0.03, 0.25, "CALL") == pytest.approx(
            BENCH_CALL
        )
        assert black76_price(100.0, 90.0, 0.5, 0.03, 0.25, " Put ") == pytest.approx(
            BENCH_PUT
        )

    def test_zero_rate_is_allowed(self):
        call = black76_price(100.0, 90.0, 0.5, 0.0, 0.25, "call")
        put = black76_price(100.0, 90.0, 0.5, 0.0, 0.25, "put")
        assert call - put == pytest.approx(10.0)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"F": 0.0, "K": 100.0, "T": 0.5, "r": 0.03, "sigma": 0.2},
            {"F": -1.0, "K": 100.0, "T": 0.5, "r": 0.03, "sigma": 0.2},
            {"F": 100.0, "K": 0.0, "T": 0.5, "r": 0.03, "sigma": 0.2},
            {"F": 100.0, "K": 100.0, "T": -0.1, "r": 0.03, "sigma": 0.2},
            {"F": 100.0, "K": 100.0, "T": 0.5, "r": -0.01, "sigma": 0.2},
            {"F": 100.0, "K": 100.0, "T": 0.5, "r": 0.03, "sigma": 0.0},
            {"F": 100.0, "K": 100.0, "T": 0.5, "r": 0.03, "sigma": -0.2},
            {"F": 100.0, "K": 100.0, "T": 0.5, "r": 0.03, "sigma": float("nan")},
        ],
    )
    def test_invalid_inputs_raise(self, kwargs):
        with pytest.raises(ValueError):
            black76_price(
                kwargs["F"],
                kwargs["K"],
                kwargs["T"],
                kwargs["r"],
                kwargs["sigma"],
                "call",
            )

    def test_invalid_option_type_raises(self):
        with pytest.raises(ValueError, match="option_type"):
            black76_price(100.0, 100.0, 0.5, 0.03, 0.2, "straddle")


class TestGreeks:
    def test_benchmark_greeks(self):
        g = calculate_greeks(100.0, 90.0, 0.5, 0.03, 0.25, "call")
        assert g["delta"] == pytest.approx(BENCH_DELTA_CALL, abs=1e-9)
        assert g["gamma"] == pytest.approx(BENCH_GAMMA, abs=1e-9)
        assert g["vega"] == pytest.approx(BENCH_VEGA, abs=1e-9)
        assert g["theta"] == pytest.approx(BENCH_THETA_CALL, abs=1e-9)

    def test_put_benchmark_greeks(self):
        g = calculate_greeks(100.0, 90.0, 0.5, 0.03, 0.25, "put")
        assert g["delta"] == pytest.approx(BENCH_DELTA_PUT, abs=1e-9)
        assert g["theta"] == pytest.approx(BENCH_THETA_PUT, abs=1e-9)

    def test_delta_bounds(self):
        call = calculate_greeks(100.0, 100.0, 0.5, 0.03, 0.25, "call")
        put = calculate_greeks(100.0, 100.0, 0.5, 0.03, 0.25, "put")
        assert 0.0 < call["delta"] < 1.0
        assert -1.0 < put["delta"] < 0.0

    def test_delta_call_minus_delta_put_is_discount_factor(self):
        for F, K, T, r, sigma in PARITY_CASES:
            call = calculate_greeks(F, K, T, r, sigma, "call")
            put = calculate_greeks(F, K, T, r, sigma, "put")
            assert call["delta"] - put["delta"] == pytest.approx(
                math.exp(-r * T), abs=1e-12
            )

    def test_call_delta_increases_with_forward(self):
        deltas = [
            calculate_greeks(F, 100.0, 0.5, 0.03, 0.25, "call")["delta"]
            for F in (80.0, 90.0, 100.0, 110.0, 120.0)
        ]
        assert deltas == sorted(deltas)

    def test_gamma_and_vega_are_positive_and_type_independent(self):
        call = calculate_greeks(100.0, 105.0, 0.5, 0.03, 0.25, "call")
        put = calculate_greeks(100.0, 105.0, 0.5, 0.03, 0.25, "put")
        assert call["gamma"] > 0
        assert call["gamma"] == pytest.approx(put["gamma"], rel=1e-12)
        assert call["vega"] > 0
        assert call["vega"] == pytest.approx(put["vega"], rel=1e-12)

    def test_gamma_peaks_at_the_money(self):
        atm = calculate_greeks(100.0, 100.0, 0.5, 0.03, 0.25, "call")["gamma"]
        otm = calculate_greeks(100.0, 140.0, 0.5, 0.03, 0.25, "call")["gamma"]
        itm = calculate_greeks(100.0, 60.0, 0.5, 0.03, 0.25, "call")["gamma"]
        assert atm > otm
        assert atm > itm

    def test_vega_pct_is_one_percent_scale(self):
        g = calculate_greeks(100.0, 90.0, 0.5, 0.03, 0.25, "call")
        assert g["vega_pct"] == pytest.approx(g["vega"] / 100.0)

    def test_theta_is_negative_and_daily_scaled(self):
        for option_type in ("call", "put"):
            g = calculate_greeks(100.0, 100.0, 0.5, 0.03, 0.25, option_type)
            assert g["theta"] < 0
            assert g["theta_daily"] == pytest.approx(g["theta"] / 365.0)

    def test_rho_is_minus_maturity_times_price(self):
        T, r = 0.5, 0.03
        call_price = black76_price(100.0, 90.0, T, r, 0.25, "call")
        put_price = black76_price(100.0, 90.0, T, r, 0.25, "put")
        assert calculate_greeks(100.0, 90.0, T, r, 0.25, "call")["rho"] == pytest.approx(
            -T * call_price
        )
        assert calculate_greeks(100.0, 90.0, T, r, 0.25, "put")["rho"] == pytest.approx(
            -T * put_price
        )

    def test_zero_maturity_greeks_are_degenerate(self):
        itm_call = calculate_greeks(110.0, 100.0, 0.0, 0.05, 0.2, "call")
        assert itm_call["delta"] == pytest.approx(1.0)
        assert itm_call["gamma"] == pytest.approx(0.0)
        assert itm_call["vega"] == pytest.approx(0.0)
        assert itm_call["theta"] == pytest.approx(0.0)
        assert itm_call["theta_daily"] == pytest.approx(0.0)
        assert itm_call["rho"] == pytest.approx(0.0)

        otm_call = calculate_greeks(90.0, 100.0, 0.0, 0.05, 0.2, "call")
        assert otm_call["delta"] == pytest.approx(0.0)

        itm_put = calculate_greeks(90.0, 100.0, 0.0, 0.05, 0.2, "put")
        assert itm_put["delta"] == pytest.approx(-1.0)

        otm_put = calculate_greeks(110.0, 100.0, 0.0, 0.05, 0.2, "put")
        assert otm_put["delta"] == pytest.approx(0.0)

    def test_all_greeks_are_finite(self):
        for option_type in ("call", "put"):
            g = calculate_greeks(100.0, 100.0, 1e-8, 0.03, 2.5, option_type)
            assert all(math.isfinite(v) for v in g.values())

    def test_invalid_option_type_raises(self):
        with pytest.raises(ValueError, match="option_type"):
            calculate_greeks(100.0, 100.0, 0.5, 0.03, 0.2, "butterfly")

    def test_invalid_sigma_raises(self):
        with pytest.raises(ValueError):
            calculate_greeks(100.0, 100.0, 0.5, 0.03, 0.0, "call")

    def test_invalid_maturity_raises(self):
        with pytest.raises(ValueError):
            calculate_greeks(100.0, 100.0, -0.5, 0.03, 0.2, "call")


IV_CASES = [
    (100.0, 90.0, 0.5, 0.03, 0.25, "call"),
    (100.0, 90.0, 0.5, 0.03, 0.25, "put"),
    (120.0, 100.0, 0.25, 0.02, 0.35, "call"),
    (80.0, 100.0, 2.0, 0.00, 0.40, "put"),
    (100.0, 100.0, 1.0, 0.05, 0.20, "call"),
    (100.0, 130.0, 0.1, 0.02, 0.60, "call"),  # deep OTM
    (100.0, 70.0, 0.1, 0.02, 0.60, "put"),  # deep OTM
]


class TestImpliedVolatility:
    @pytest.mark.parametrize("F,K,T,r,sigma,option_type", IV_CASES)
    def test_round_trip_recovers_sigma(self, F, K, T, r, sigma, option_type):
        price = black76_price(F, K, T, r, sigma, option_type)
        assert implied_volatility(price, F, K, T, r, option_type) == pytest.approx(
            sigma, rel=1e-6, abs=1e-8
        )

    def test_recovered_iv_reprices_the_option(self):
        F, K, T, r, sigma = 100.0, 90.0, 0.5, 0.03, 0.25
        price = black76_price(F, K, T, r, sigma, "call")
        iv = implied_volatility(price, F, K, T, r, "call")
        assert black76_price(F, K, T, r, iv, "call") == pytest.approx(price, rel=1e-9)

    def test_price_at_lower_bound_raises(self):
        F, K, T, r = 100.0, 90.0, 0.5, 0.03
        intrinsic = math.exp(-r * T) * (F - K)
        with pytest.raises(ValueError, match="lower arbitrage bound"):
            implied_volatility(intrinsic, F, K, T, r, "call")

    def test_price_below_lower_bound_raises(self):
        with pytest.raises(ValueError, match="lower arbitrage bound"):
            implied_volatility(1.0, 100.0, 90.0, 0.5, 0.03, "call")

    def test_price_above_upper_bound_raises(self):
        F, T, r = 100.0, 0.5, 0.03
        with pytest.raises(ValueError, match="upper arbitrage bound"):
            implied_volatility(math.exp(-r * T) * F * 1.5, F, 100.0, T, r, "call")

    def test_zero_maturity_raises(self):
        with pytest.raises(ValueError):
            implied_volatility(5.0, 100.0, 100.0, 0.0, 0.03, "call")

    @pytest.mark.parametrize("bad_price", [0.0, -1.0])
    def test_non_positive_market_price_raises(self, bad_price):
        with pytest.raises(ValueError):
            implied_volatility(bad_price, 100.0, 100.0, 0.5, 0.03, "call")

    def test_invalid_option_type_raises(self):
        with pytest.raises(ValueError, match="option_type"):
            implied_volatility(5.0, 100.0, 100.0, 0.5, 0.03, "swaption")

    @pytest.mark.parametrize(
        "market_price,F,K,T,r",
        [
            (5.0, 0.0, 100.0, 0.5, 0.03),
            (5.0, 100.0, 0.0, 0.5, 0.03),
            (5.0, 100.0, 100.0, -0.5, 0.03),
            (5.0, 100.0, 100.0, 0.5, -0.01),
        ],
    )
    def test_invalid_inputs_raise(self, market_price, F, K, T, r):
        with pytest.raises(ValueError):
            implied_volatility(market_price, F, K, T, r, "call")

    def test_bisection_fallback_when_brentq_fails(self, monkeypatch):
        import services.gold.black76_engine as engine

        F, K, T, r, sigma = 100.0, 90.0, 0.5, 0.03, 0.25
        price = black76_price(F, K, T, r, sigma, "call")

        def boom(*args, **kwargs):
            raise RuntimeError("brentq unavailable")

        monkeypatch.setattr(engine, "brentq", boom)
        iv = engine.implied_volatility(price, F, K, T, r, "call")
        assert iv == pytest.approx(sigma, rel=1e-6)

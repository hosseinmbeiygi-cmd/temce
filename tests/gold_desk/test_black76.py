"""تست Black-76."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from src.gold_desk.black76 import (
    IRAN_RISK_FREE_RATE,
    black76_greeks,
    black76_price,
    price_option,
    protective_collar,
    years_to_expiry,
)

# مقادیر مرجع: Hull, "Options, Futures, and Other Derivatives", Example 17.1
# S=42, K=40, T=0.5, r=0.10, sigma=0.20
# Call ≈ 4.76, Put ≈ 0.81


def test_black76_atm():
    """ATM call نزدیک به فرمول Black-Scholes."""
    F, K, T, r, sigma = 100.0, 100.0, 0.5, 0.10, 0.20
    call, put, d1, d2 = black76_price(F, K, T, sigma, r)
    # d1 = 0.5*0.04*0.5 / (0.20 * sqrt(0.5)) = 0.01 / 0.1414 ≈ 0.0707
    # d2 = 0.0707 - 0.1414 = -0.0707
    # N(0.07) ≈ 0.528, N(-0.07) ≈ 0.472
    # Call = e^(-0.05) * (100*0.528 - 100*0.472) = 0.951 * 5.6 ≈ 5.32
    assert 5.0 < call < 6.0


def test_put_call_parity():
    """Put-Call Parity: C - P = e^(-rT) × (F - K)"""
    F, K, T, r, sigma = 100.0, 95.0, 0.5, 0.10, 0.25
    call, put, _, _ = black76_price(F, K, T, sigma, r)
    parity_lhs = call - put
    parity_rhs = math.exp(-r * T) * (F - K)
    assert abs(parity_lhs - parity_rhs) < 0.01


def test_invalid_inputs():
    with pytest.raises(ValueError):
        black76_price(0, 100, 0.5)
    with pytest.raises(ValueError):
        black76_price(100, 0, 0.5)
    with pytest.raises(ValueError):
        black76_price(100, 100, 0)
    with pytest.raises(ValueError):
        black76_price(100, 100, 0.5, iv=0)


def test_years_to_expiry():
    expiry = date.today() + timedelta(days=180)
    t = years_to_expiry(expiry)
    assert 0.48 < t < 0.51


def test_years_to_expiry_past():
    """تاریخ گذشته = حداقل 1 روز."""
    expiry = date.today() - timedelta(days=10)
    t = years_to_expiry(expiry)
    assert t > 0


def test_price_option():
    expiry = date.today() + timedelta(days=90)
    result = price_option(
        forward=100.0,
        strike=100.0,
        expiry=expiry,
        iv=0.25,
        rate=0.30,  # ایران
    )
    # ATM با نرخ ایران و ۹۰ روز
    assert result.call > 0
    assert result.put > 0
    # ATM forward=strike: call = put (symmetric)
    assert abs(result.call - result.put) < 0.01


def test_price_option_itm_call():
    """Call ITM (K < F) گران‌تر از put OTM."""
    expiry = date.today() + timedelta(days=90)
    result = price_option(forward=110.0, strike=100.0, expiry=expiry, iv=0.25, rate=0.30)
    assert result.call > result.put


def test_greeks_call_delta():
    """Call delta بین 0 و 1، Put delta بین -1 و 0."""
    g = black76_greeks(100, 100, 0.5, 0.20, 0.10)
    assert 0 < g.delta < 1


def test_greeks_gamma_positive():
    """Gamma همیشه مثبت (برای Call و Put یکسان)."""
    g = black76_greeks(100, 100, 0.5, 0.20, 0.10)
    assert g.gamma > 0


def test_greeks_vega_positive():
    g = black76_greeks(100, 100, 0.5, 0.20, 0.10)
    assert g.vega > 0


def test_greeks_theta_negative():
    """Theta معمولاً منفی (زمان به ضرر خریدار)."""
    g = black76_greeks(100, 100, 0.5, 0.20, 0.10)
    # ممکنه در ITM call مثبت باشه ولی ATM معمولاً منفی
    assert g.theta < 0


def test_collar_basic():
    """Protective Collar: cost ≈ 0، floor < spot < cap."""
    spot = 100.0
    expiry = date.today() + timedelta(days=90)
    collar = protective_collar(
        spot=spot,
        put_strike=95.0,
        call_strike=110.0,
        expiry=expiry,
    )
    assert collar.floor < spot < collar.cap
    # cost می‌تواند مثبت یا منفی باشد (بسته به IV و strikes)
    assert abs(collar.cost) < 5.0  # cost کم


def test_collar_floor_cap():
    """floor و cap درست تنظیم می‌شوند."""
    collar = protective_collar(100, 95, 110, date.today() + timedelta(days=90))
    assert collar.floor == 95
    assert collar.cap == 110


def test_iran_rate():
    """نرخ ایران > نرخ جهانی."""
    assert IRAN_RISK_FREE_RATE > 0.10

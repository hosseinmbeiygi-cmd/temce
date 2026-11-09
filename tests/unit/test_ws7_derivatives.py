"""WS7: Derivatives — implied volatility solver + protective_collar correctness.

RED (before fixes):
  1. src.gold_desk.black76 has no implied_volatility() — ImportError on name.
  2. protective_collar() unpacks black76_price() as (put_price, _, _, _) on the
     first call and (_, call_price, _, _) on the second, but black76_price()
     returns (call, put, d1, d2).  The labels are swapped:
       collar.put_premium  ← call price at put_strike   (WRONG)
       collar.call_premium ← put  price at call_strike  (WRONG)
  3. No BRSAPI_OPTIONS_DEFERRED flag documents the live-data gap.

GREEN (after fixes):
  1. implied_volatility(market_price, forward, strike, time_years, rate,
     option_type) added to src.gold_desk.black76; Newton-Raphson with
     bisection fallback; raises ValueError for bad inputs.
  2. protective_collar() unpack order corrected:
       _, put_price, _, _ = black76_price(spot, put_strike, …)
       call_price, _, _, _ = black76_price(spot, call_strike, …)
  3. BRSAPI_OPTIONS_DEFERRED = True added to src.gold_desk.black76.

WS7 scope: BrsApi live options chain is not confirmed (high risk).  Only the
mathematical layer is implemented.  BRSAPI_OPTIONS_DEFERRED documents the gap.
"""
from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── 1. Import check ─────────────────────────────────────────────────────────

def test_import_implied_volatility():
    """implied_volatility must be importable from src.gold_desk.black76.

    RED: name does not exist in the module.
    GREEN: function added.
    """
    from src.gold_desk.black76 import implied_volatility  # noqa: F401


def test_import_brsapi_deferred_flag():
    """BRSAPI_OPTIONS_DEFERRED constant must exist to document the live-data gap.

    RED: name does not exist.
    GREEN: BRSAPI_OPTIONS_DEFERRED = True added to module.
    """
    from src.gold_desk.black76 import BRSAPI_OPTIONS_DEFERRED
    assert BRSAPI_OPTIONS_DEFERRED is True, (
        "BRSAPI_OPTIONS_DEFERRED must be True to document the deferred gap"
    )


# ─── 2. implied_volatility — round-trip ──────────────────────────────────────

def test_implied_volatility_round_trip_call():
    """IV round-trip: price_call → implied_volatility → recovered_iv == original_iv.

    RED: function does not exist.
    GREEN: Newton-Raphson or bisection recovers σ to within 1e-6 relative error.
    """
    from src.gold_desk.black76 import black76_price, implied_volatility

    F, K, T, r, sigma = 100.0, 100.0, 0.5, 0.30, 0.25
    call, _, _, _ = black76_price(F, K, T, sigma, r)
    recovered = implied_volatility(call, F, K, T, r, option_type="call")
    assert recovered == pytest.approx(sigma, rel=1e-5, abs=1e-7)


def test_implied_volatility_round_trip_put():
    """IV round-trip for put option.

    RED: function does not exist.
    GREEN: recovered σ matches original to within 1e-5 rel.
    """
    from src.gold_desk.black76 import black76_price, implied_volatility

    F, K, T, r, sigma = 100.0, 95.0, 0.25, 0.30, 0.20
    _, put, _, _ = black76_price(F, K, T, sigma, r)
    recovered = implied_volatility(put, F, K, T, r, option_type="put")
    assert recovered == pytest.approx(sigma, rel=1e-5, abs=1e-7)


def test_implied_volatility_otm_call():
    """IV round-trip for a deep OTM call (harder numerics).

    RED: function does not exist.
    GREEN: solver converges for σ=0.60 OTM call.
    """
    from src.gold_desk.black76 import black76_price, implied_volatility

    F, K, T, r, sigma = 100.0, 130.0, 0.25, 0.30, 0.60
    call, _, _, _ = black76_price(F, K, T, sigma, r)
    recovered = implied_volatility(call, F, K, T, r, option_type="call")
    assert recovered == pytest.approx(sigma, rel=1e-4, abs=1e-6)


def test_implied_volatility_reprices_correctly():
    """implied_volatility output must reprice the option to the input price.

    RED: function does not exist.
    GREEN: price(recovered_iv) ≈ market_price to 1e-9 relative.
    """
    from src.gold_desk.black76 import black76_price, implied_volatility

    F, K, T, r, sigma = 100.0, 90.0, 0.5, 0.30, 0.25
    call, _, _, _ = black76_price(F, K, T, sigma, r)
    iv = implied_volatility(call, F, K, T, r, option_type="call")
    repriced_call, _, _, _ = black76_price(F, K, T, iv, r)
    assert repriced_call == pytest.approx(call, rel=1e-9)


# ─── 3. implied_volatility — input validation ────────────────────────────────

def test_implied_volatility_raises_for_zero_maturity():
    """implied_volatility with T=0 must raise ValueError.

    RED: function does not exist.
    GREEN: raises ValueError immediately on T <= 0.
    """
    from src.gold_desk.black76 import implied_volatility

    with pytest.raises(ValueError):
        implied_volatility(5.0, 100.0, 100.0, 0.0, 0.30, option_type="call")


def test_implied_volatility_raises_for_non_positive_price():
    """implied_volatility with market_price <= 0 must raise ValueError.

    RED: function does not exist.
    GREEN: raises ValueError for price <= 0.
    """
    from src.gold_desk.black76 import implied_volatility

    with pytest.raises(ValueError):
        implied_volatility(0.0, 100.0, 100.0, 0.5, 0.30, option_type="call")
    with pytest.raises(ValueError):
        implied_volatility(-1.0, 100.0, 100.0, 0.5, 0.30, option_type="put")


def test_implied_volatility_raises_for_invalid_option_type():
    """implied_volatility with unknown option_type must raise ValueError.

    RED: function does not exist.
    GREEN: raises ValueError with 'option_type' in message.
    """
    from src.gold_desk.black76 import implied_volatility

    with pytest.raises(ValueError, match="option_type"):
        implied_volatility(5.0, 100.0, 100.0, 0.5, 0.30, option_type="straddle")


# ─── 4. protective_collar — call/put swap bug ────────────────────────────────

def test_collar_put_premium_equals_true_put():
    """collar.put_premium must equal the PUT price at put_strike, not the call price.

    RED: protective_collar unpacks black76_price() as
         ``put_price, _, _, _ = black76_price(spot, put_strike, …)``
         but black76_price returns (call, put, d1, d2), so put_price ← call price.
    GREEN: unpack order corrected to
         ``_, put_price, _, _ = black76_price(spot, put_strike, …)``.
    """
    from src.gold_desk.black76 import black76_price, protective_collar, years_to_expiry

    spot, put_strike, call_strike = 100.0, 90.0, 110.0
    expiry = date.today() + timedelta(days=180)
    t = years_to_expiry(expiry)

    _, true_put, _, _ = black76_price(spot, put_strike, t)
    collar = protective_collar(
        spot=spot, put_strike=put_strike, call_strike=call_strike, expiry=expiry
    )
    assert collar.put_premium == pytest.approx(true_put, rel=1e-9), (
        f"put_premium={collar.put_premium:.6f} but true put={true_put:.6f}; "
        f"unpack order in protective_collar may be (call, put, …) not (put, call, …)"
    )


def test_collar_call_premium_equals_true_call():
    """collar.call_premium must equal the CALL price at call_strike, not the put price.

    RED: protective_collar unpacks black76_price() as
         ``_, call_price, _, _ = black76_price(spot, call_strike, …)``
         but black76_price returns (call, put, d1, d2), so call_price ← put price.
    GREEN: unpack order corrected to
         ``call_price, _, _, _ = black76_price(spot, call_strike, …)``.
    """
    from src.gold_desk.black76 import black76_price, protective_collar, years_to_expiry

    spot, put_strike, call_strike = 100.0, 90.0, 110.0
    expiry = date.today() + timedelta(days=180)
    t = years_to_expiry(expiry)

    true_call, _, _, _ = black76_price(spot, call_strike, t)
    collar = protective_collar(
        spot=spot, put_strike=put_strike, call_strike=call_strike, expiry=expiry
    )
    assert collar.call_premium == pytest.approx(true_call, rel=1e-9), (
        f"call_premium={collar.call_premium:.6f} but true call={true_call:.6f}; "
        f"unpack order in protective_collar may be (call, put, …) not (put, call, …)"
    )


def test_collar_cost_equals_put_minus_call_premium():
    """collar.cost must equal put_premium - call_premium (buy put, sell call).

    RED: depends on the fixed unpack in tests above.
    GREEN: cost = put_premium - call_premium after unpack fix.
    """
    from src.gold_desk.black76 import protective_collar

    spot, put_strike, call_strike = 100.0, 90.0, 110.0
    expiry = date.today() + timedelta(days=180)
    collar = protective_collar(
        spot=spot, put_strike=put_strike, call_strike=call_strike, expiry=expiry
    )
    expected_cost = collar.put_premium - collar.call_premium
    assert collar.cost == pytest.approx(expected_cost, abs=1e-12)


def test_collar_otm_premium_signs_are_sensible():
    """For OTM put (K<F) and OTM call (K>F), both premiums are positive and < spot price.

    RED: buggy premiums (call at put_strike, put at call_strike) are both larger
         than the OTM values and may violate bounds.
    GREEN: both premiums are positive but smaller than the ATM options.
    """
    from src.gold_desk.black76 import black76_price, protective_collar, years_to_expiry

    spot, put_strike, call_strike = 100.0, 90.0, 110.0
    expiry = date.today() + timedelta(days=180)
    t = years_to_expiry(expiry)
    collar = protective_collar(
        spot=spot, put_strike=put_strike, call_strike=call_strike, expiry=expiry
    )

    # OTM options must be strictly positive and less than ATM
    atm_call, atm_put, _, _ = black76_price(spot, spot, t)
    assert 0 < collar.put_premium < atm_put * 2, (
        f"OTM put premium {collar.put_premium:.4f} outside expected range"
    )
    assert 0 < collar.call_premium < atm_call * 2, (
        f"OTM call premium {collar.call_premium:.4f} outside expected range"
    )

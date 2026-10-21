"""ماتریس اختیار معامله — نسبت Put/Call، Max Pain و غنی‌سازی زنجیره.

هر قرارداد یک ``dict`` ساده است::

    {
        "strike": 100.0,
        "option_type": "call" | "put",
        "market_price": 5.2,
        "open_interest": 1200,
        "volume": 80,
        "days_to_expiry": 30,   # اختیاری؛ در غیر این صورت پارامتر تابع
    }

همهٔ توابع pure هستند: ورودی mutate نمی‌شود و هیچ I/O انجام نمی‌گیرد.
"""

from __future__ import annotations

import math
from typing import Any

from services.gold.black76_engine import (
    calculate_greeks,
    implied_volatility,
)

_OPTION_TYPES = ("call", "put")
DAYS_PER_YEAR = 365.0


def _contract_type(contract: dict[str, Any]) -> str:
    raw = contract.get("option_type", "")
    option_type = str(raw).strip().lower() if raw is not None else ""
    if option_type not in _OPTION_TYPES:
        raise ValueError(
            f"option_type must be 'call' or 'put', got {raw!r}"
        )
    return option_type


def _strike(contract: dict[str, Any]) -> float:
    if "strike" not in contract:
        raise ValueError("contract missing strike")
    strike = float(contract["strike"])
    if not math.isfinite(strike) or strike <= 0:
        raise ValueError(f"strike must be a finite positive number, got {strike!r}")
    return strike


def _non_negative_field(contract: dict[str, Any], name: str) -> float:
    value = contract.get(name, 0)
    if value is None:
        return 0.0
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number, got {value!r}")
    return value


def _market_price(contract: dict[str, Any]) -> float:
    value = contract.get("market_price")
    if value is None:
        raise ValueError("contract missing market_price")
    return float(value)


def calculate_pcr(options_chain: list[dict[str, Any]]) -> dict[str, Any]:
    """نسبت Put/Call بر پایهٔ حجم و موقعیت باز (Open Interest).

    اگر حجم/موقعیت باز Call صفر باشد، تقسیم انجام نمی‌شود و مقدار
    ``None`` برگردانده می‌شود تا مصرف‌کننده بتواند «بی‌نهایت» را از
    «دادهٔ ناموجود» تفکیک کند.
    """
    call_volume = put_volume = call_oi = put_oi = 0.0

    for contract in options_chain:
        option_type = _contract_type(contract)
        volume = _non_negative_field(contract, "volume")
        oi = _non_negative_field(contract, "open_interest")
        if option_type == "call":
            call_volume += volume
            call_oi += oi
        else:
            put_volume += volume
            put_oi += oi

    return {
        "pcr_volume": (put_volume / call_volume) if call_volume > 0 else None,
        "pcr_oi": (put_oi / call_oi) if call_oi > 0 else None,
        "total_call_volume": call_volume,
        "total_put_volume": put_volume,
        "total_call_oi": call_oi,
        "total_put_oi": put_oi,
        "call_volume_zero": call_volume == 0,
        "call_oi_zero": call_oi == 0,
        "contracts": len(options_chain),
    }


def calculate_max_pain(options_chain: list[dict[str, Any]]) -> float:
    """Max Pain — قیمت تسویه‌ای که کل سود خریداران را کمینه می‌کند.

    برای هر کران استرایک موجود::

        payout(S) = Σ max(0, S - K_call) * OI_call
                  + Σ max(0, K_put - S) * OI_put

    استرایکی با کمترین payout برمی‌گردد؛ در حالت تساوی، استرایک
    کوچک‌تر (اولین در ترتیب صعودی) انتخاب می‌شود.
    """
    if not options_chain:
        raise ValueError("options_chain must not be empty")

    contracts: list[tuple[str, float, float]] = []
    for contract in options_chain:
        contracts.append(
            (
                _contract_type(contract),
                _strike(contract),
                _non_negative_field(contract, "open_interest"),
            )
        )

    strikes = sorted({strike for _, strike, _ in contracts})
    best_strike = strikes[0]
    best_payout = math.inf

    for settlement in strikes:
        payout = 0.0
        for option_type, strike, oi in contracts:
            if option_type == "call":
                payout += max(0.0, settlement - strike) * oi
            else:
                payout += max(0.0, strike - settlement) * oi
        if payout < best_payout:
            best_payout = payout
            best_strike = settlement

    return best_strike


def enrich_options_chain(
    options_chain: list[dict[str, Any]],
    forward_price: float,
    risk_free_rate: float,
    days_to_expiry: float,
) -> list[dict[str, Any]]:
    """محاسبهٔ IV، یونانی‌ها و Moneyness برای تمام قراردادهای زنجیره.

    ``days_to_expiry`` پارامتر پیش‌فرض است؛ اگر خود قرارداد
    ``days_to_expiry`` داشته باشد، همان اولویت دارد. ورودی تغییر
    نمی‌کند و برای هر قرارداد یک dict جدید ساخته می‌شود.
    """
    if not math.isfinite(forward_price) or forward_price <= 0:
        raise ValueError(
            f"forward_price must be a finite positive number, got {forward_price!r}"
        )
    if not math.isfinite(risk_free_rate) or risk_free_rate < 0:
        raise ValueError(
            f"risk_free_rate must be a finite non-negative number, got {risk_free_rate!r}"
        )
    if not math.isfinite(days_to_expiry) or days_to_expiry < 0:
        raise ValueError(
            f"days_to_expiry must be a finite non-negative number, got {days_to_expiry!r}"
        )

    enriched: list[dict[str, Any]] = []

    for contract in options_chain:
        strike = _strike(contract)
        option_type = _contract_type(contract)
        market_price = _market_price(contract)

        contract_days = contract.get("days_to_expiry", days_to_expiry)
        contract_days = float(contract_days)
        if not math.isfinite(contract_days) or contract_days < 0:
            raise ValueError(
                f"days_to_expiry must be a finite non-negative number, "
                f"got {contract_days!r}"
            )

        time_to_expiry = contract_days / DAYS_PER_YEAR
        rate = float(risk_free_rate)

        iv = implied_volatility(
            market_price,
            forward_price,
            strike,
            time_to_expiry,
            rate,
            option_type,
        )
        greeks = calculate_greeks(
            forward_price, strike, time_to_expiry, rate, iv, option_type
        )

        discount = math.exp(-rate * time_to_expiry)
        if option_type == "call":
            intrinsic = max(0.0, forward_price - strike) * discount
            is_itm = forward_price > strike
        else:
            intrinsic = max(0.0, strike - forward_price) * discount
            is_itm = forward_price < strike

        enriched.append(
            {
                **contract,
                "iv": iv,
                "time_to_expiry_years": time_to_expiry,
                "moneyness": forward_price / strike,
                "intrinsic_value": intrinsic,
                "is_itm": is_itm,
                **greeks,
            }
        )

    return enriched

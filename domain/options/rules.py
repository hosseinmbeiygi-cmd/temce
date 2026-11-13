from __future__ import annotations

from datetime import datetime


def validate_option_type(option_type: str) -> bool:
    return option_type.lower() in ("call", "put")


def validate_strike_price(strike: float) -> bool:
    return strike > 0


def validate_expiration(expiration_date: str | None) -> bool:
    """Return True only when expiration_date is a parseable date string."""
    if expiration_date is None or not isinstance(expiration_date, str):
        return False
    value = expiration_date.strip()
    if not value:
        return False
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def is_itm_call(strike: float, underlying_price: float) -> bool:
    return underlying_price > strike


def is_itm_put(strike: float, underlying_price: float) -> bool:
    return underlying_price < strike


def validate_option_style(style: str) -> bool:
    return style.lower() in ("european", "american", "bermuda")

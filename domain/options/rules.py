from __future__ import annotations


def validate_option_type(option_type: str) -> bool:
    return option_type.lower() in ("call", "put")


def validate_strike_price(strike: float) -> bool:
    return strike > 0


def validate_expiration(expiration_date: str | None) -> bool:
    if expiration_date is None:
        return True
    return True


def is_itm_call(strike: float, underlying_price: float) -> bool:
    return underlying_price > strike


def is_itm_put(strike: float, underlying_price: float) -> bool:
    return underlying_price < strike


def validate_option_style(style: str) -> bool:
    return style.lower() in ("european", "american", "bermuda")

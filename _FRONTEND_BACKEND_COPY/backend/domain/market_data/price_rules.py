from __future__ import annotations


def validate_price(price: float) -> bool:
    return price >= 0


def validate_volume(volume: int) -> bool:
    return volume >= 0


def validate_quote(
    price_close: float,
    price_open: float,
    price_high: float,
    price_low: float,
    price_yesterday: float,
) -> list[str]:
    errors: list[str] = []
    if price_close < 0:
        errors.append("price_close must be >= 0")
    if price_open < 0:
        errors.append("price_open must be >= 0")
    if price_high < price_low:
        errors.append("price_high must be >= price_low")
    if price_high < 0:
        errors.append("price_high must be >= 0")
    if price_low < 0:
        errors.append("price_low must be >= 0")
    if price_yesterday < 0:
        errors.append("price_yesterday must be >= 0")
    return errors


def adjusted_price(price: float, adjustment_factor: float) -> float:
    return price / adjustment_factor if adjustment_factor != 0 else price

from __future__ import annotations


def validate_contract_price(price: float) -> bool:
    return price >= 0


def validate_contract_volume(volume: int) -> bool:
    return volume >= 0


def validate_delivery_dates(last_trade: str | None, delivery: str | None) -> bool:
    if last_trade is None or delivery is None:
        return True
    return last_trade < delivery


def validate_tick_size(tick_size: float) -> bool:
    return tick_size > 0

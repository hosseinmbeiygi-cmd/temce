from __future__ import annotations


def validate_trade_price(price: float) -> bool:
    return price >= 0


def validate_trade_volume(volume: int) -> bool:
    return volume > 0


def validate_trade_side(side: str) -> bool:
    return side in ("buy", "sell", "unknown")


def is_buy_trade(side: str) -> bool:
    return side == "buy"


def is_sell_trade(side: str) -> bool:
    return side == "sell"

"""تست Portfolio service — pure functions."""

from __future__ import annotations

from src.gold_desk.portfolio import get_current_prices


def test_get_current_prices_empty():
    assert get_current_prices(None) == {}


def test_get_current_prices_coins():
    snap = {
        "coins": {
            "coin_emami": {"symbol": "IR_COIN_EMAMI", "market_price": 53_000_000},
            "coin_half": {"symbol": "IR_COIN_HALF", "market_price": 27_000_000},
        },
        "gold": {
            "gold_18k": {"symbol": "IR_GOLD_18K", "market_price": 4_550_000},
        },
    }
    prices = get_current_prices(snap)
    assert prices["IR_COIN_EMAMI"] == 53_000_000
    assert prices["IR_COIN_HALF"] == 27_000_000
    assert prices["IR_GOLD_18K"] == 4_550_000
    assert len(prices) == 3


def test_get_current_prices_zero_included():
    """قیمت 0 ذخیره می‌شود (فراخوانی بعد حذف می‌کند)."""
    snap = {
        "coins": {
            "a": {"symbol": "A", "market_price": 100},
            "b": {"symbol": "B", "market_price": 200},
        }
    }
    prices = get_current_prices(snap)
    assert prices["A"] == 100
    assert prices["B"] == 200
    assert len(prices) == 2

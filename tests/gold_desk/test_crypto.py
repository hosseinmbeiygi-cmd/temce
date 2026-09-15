"""تست Crypto — pure functions."""

from __future__ import annotations

from src.gold_desk.crypto import (
    COINGECKO_IDS,
    FX_SYMBOLS,
    _name_fa,
    calc_bubble_from_history,
)


def test_coingecko_ids_complete():
    """حداقل ۵ ارز اصلی."""
    assert len(COINGECKO_IDS) >= 5
    assert "BTC" in COINGECKO_IDS
    assert "ETH" in COINGECKO_IDS


def test_fx_symbols_complete():
    assert "EUR" in FX_SYMBOLS
    assert "GBP" in FX_SYMBOLS
    assert "AED" in FX_SYMBOLS


def test_name_fa_btc():
    assert _name_fa("BTC") == "بیت‌کوین"


def test_name_fa_eur():
    assert _name_fa("EUR") == "یورو"


def test_name_fa_unknown():
    assert _name_fa("XYZ") == "XYZ"


def test_calc_bubble_short():
    """کمتر از 30 داده → None."""
    assert calc_bubble_from_history([100, 101, 102]) is None


def test_calc_bubble_above_ma():
    """قیمت بالای MA → bubble مثبت."""
    prices = [100] * 30 + [110] * 1
    bubble = calc_bubble_from_history(prices)
    assert bubble is not None
    assert bubble > 0


def test_calc_bubble_below_ma():
    """قیمت پایین MA → bubble منفی."""
    prices = [100] * 30 + [85] * 1
    bubble = calc_bubble_from_history(prices)
    assert bubble is not None
    assert bubble < 0

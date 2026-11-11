"""Price response schemas must expose toman (TMN) alongside the raw rial values.

The migration is deliberately additive: the existing rial fields keep their
names and scales so current consumers do not silently start reading a number
ten times smaller, while ``*_toman`` fields plus an explicit ``currency`` marker
give users the unit the product actually talks in.
"""

from __future__ import annotations

import pytest

from schemas.api.currency import CurrencyCode
from schemas.api.historical_ohlcv import OhlcvResponse
from schemas.api.options import OptionResponse
from schemas.api.realtime_quotes import RealtimeQuoteResponse
from schemas.api.screener_filter import FilteredItem
from schemas.api.symbol_detail import SymbolDetailResponse

RIAL_PRICE = 1_234_500.0
TOMAN_PRICE = 123_450.0


def test_realtime_quote_reports_both_units() -> None:
    quote = RealtimeQuoteResponse(symbol="فولاد", last_price=RIAL_PRICE, value=RIAL_PRICE * 100)
    assert quote.currency == "TMN"
    assert quote.last_price == RIAL_PRICE  # raw rial field untouched
    assert quote.last_price_toman == TOMAN_PRICE
    assert quote.value_toman == TOMAN_PRICE * 100
    dumped = quote.model_dump()
    assert dumped["currency"] == "TMN"
    assert dumped["last_price_toman"] == TOMAN_PRICE


def test_symbol_detail_reports_closing_price_in_toman() -> None:
    detail = SymbolDetailResponse(symbol="فولاد", last_price=10_000, closing_price=9_870)
    assert detail.last_price_toman == 1_000
    assert detail.closing_price_toman == 987
    assert detail.currency == "TMN"


def test_screener_filter_item_converts_price_and_market_value() -> None:
    item = FilteredItem(symbol="خودرو", last_price=RIAL_PRICE, market_value=None)
    assert item.last_price_toman == TOMAN_PRICE
    # A missing market value must stay missing, not become 0 toman.
    assert item.market_value_toman is None


def test_option_response_marks_the_unit_once() -> None:
    option = OptionResponse(id="1", symbol="ضفولاد", strike_price=50_000, last_price=12_000)
    assert option.currency == "TMN"
    assert option.strike_price_toman == 5_000
    assert option.last_price_toman == 1_200


def test_ohlcv_close_converted_from_rial() -> None:
    candle = OhlcvResponse(date="1404-01-01", close=875_000, value=1_000_000_000)
    assert candle.close_toman == 87_500
    assert candle.value_toman == 100_000_000


def test_defaults_are_zero_and_still_labelled_toman() -> None:
    quote = RealtimeQuoteResponse()
    assert quote.last_price_toman == 0.0
    assert quote.currency == "TMN"


def test_currency_literal_covers_both_units() -> None:
    # The marker is typed, so a typo like "TOMAN" is rejected at validation.
    assert CurrencyCode is not None
    with pytest.raises(Exception):
        RealtimeQuoteResponse(currency="TOMAN")  # type: ignore[arg-type]

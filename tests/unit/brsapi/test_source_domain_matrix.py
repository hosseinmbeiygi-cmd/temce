"""Stale / out-of-domain source matrix.

Three layers own one question each, and this file pins the boundary between
them so a stale value can never pass silently:

1. **Transport** (``BrsApiClient``): HTTP status → failure code. Covered by
   ``test_client_status_handling.py``.
2. **Parser** (this file): the provider's raw ``date`` is preserved untouched;
   only candlesticks build a Gregorian column, and only inside the Jalali
   domain (1200..1599). An out-of-domain value yields ``None`` — never a
   silently shifted date. A parser never invents a market date; the single
   documented exception is an intraday bar, which carries no date at all and is
   stamped with today's Jalali date so the chart has a timestamp.
3. **Ingestion** (``history_fetch_service``): normalises the raw date and
   quarantines unparsable dates / invalid OHLC bars — covered by
   ``test_history_fetch_quality.py``.

Numeric fields follow the same rule: an absent or unreadable price stays
``None`` on a nullable column instead of being published as a real ``0``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import jdatetime
import pytest

from brsapi.parsers import (
    CommodityParser,
    CurrencyParser,
    GoldCoinParser,
    GoldCurrencyProParser,
    TsetmcParser,
)
from brsapi.quality import jalali_to_gregorian

# A Gregorian date, a month outside 1..12, a day outside the month, an
# impossible leap day (1404 is not a leap year) and plain garbage.
OUT_OF_DOMAIN_DATES = [
    "2026-09-14",
    "1404-13-01",
    "1404-12-30",
    "1405-06-32",
    "garbage",
]


# ── Candlestick: the only parser with a derived date column ────────────────


def _candle_payload(raw_date: Any) -> dict[str, Any]:
    candle: dict[str, Any] = {"open": 10, "high": 12, "low": 9, "close": 11, "volume": 5}
    if raw_date is not None:
        candle["date"] = raw_date
    return {"candle_daily": [candle]}


@pytest.mark.parametrize(
    ("raw", "expected_shamsi"),
    [
        ("1404-05-18", "1404-05-18"),
        ("1404/05/18", "1404-05-18"),
        ("۱۴۰۴/۰۵/۱۸", "1404-05-18"),
        ("1404.5.8", "1404-05-08"),
    ],
)
def test_candlestick_in_domain_dates_are_converted(raw: str, expected_shamsi: str) -> None:
    (row,) = TsetmcParser.parse_candlesticks(_candle_payload(raw))

    assert row["shamsi_date"] == expected_shamsi
    assert row["gregorian_date"] == jalali_to_gregorian(expected_shamsi)
    assert isinstance(row["gregorian_date"], date)
    assert row["date"] == raw, "the raw provider string is kept for audit"


@pytest.mark.parametrize("raw", OUT_OF_DOMAIN_DATES)
def test_candlestick_out_of_domain_dates_are_not_shifted(raw: str) -> None:
    (row,) = TsetmcParser.parse_candlesticks(_candle_payload(raw))

    assert row["gregorian_date"] is None
    assert row["shamsi_date"] is None
    assert row["date"] == raw


def test_candlestick_intraday_bar_is_stamped_with_today() -> None:
    today = jdatetime.date.today().strftime("%Y-%m-%d")
    payload = {"candle_intraday": [{"time": "09:02", "open": 1, "close": 2}]}

    (row,) = TsetmcParser.parse_candlesticks(payload)

    assert row["date"] == today
    assert row["gregorian_date"] == jalali_to_gregorian(today)


def test_candlestick_missing_numbers_are_null_not_zero() -> None:
    payload = {"candle_daily": [{"date": "1404-05-18"}]}

    (row,) = TsetmcParser.parse_candlesticks(payload)

    assert row["open"] is None
    assert row["high"] is None
    assert row["low"] is None
    assert row["close"] is None
    assert row["volume"] is None
    assert row["count"] is None


# ── History parsers: raw date passthrough, no invented date ────────────────

HistoryParser = Callable[[Any], list[dict[str, Any]]]

PASSTHROUGH_PARSERS: list[tuple[str, HistoryParser, Callable[[str], Any]]] = [
    (
        "Tsetmc/HistoryPrice",
        TsetmcParser.parse_history_price,
        lambda d: [{"tno": 1, "date": d}],
    ),
    (
        "Tsetmc/HistoryRealLegal",
        TsetmcParser.parse_history_real_legal,
        lambda d: [{"date": d}],
    ),
    (
        "Commodity",
        CommodityParser.parse,
        lambda d: {"metal_precious": [{"symbol": "XAU", "date": d}]},
    ),
    (
        "GoldCoin/History",
        GoldCoinParser.parse_history,
        lambda d: [{"symbol": "SEKEEEE", "date": d}],
    ),
    (
        "Currency/History",
        CurrencyParser.parse_history,
        lambda d: [{"symbol": "USD", "date": d}],
    ),
    (
        "GoldCurrencyPro/history_daily",
        GoldCurrencyProParser.parse_daily_history,
        lambda d: [{"symbol": "XAUUSD", "date": d}],
    ),
]


@pytest.mark.parametrize(
    ("label", "parser", "build"),
    PASSTHROUGH_PARSERS,
    ids=[p[0] for p in PASSTHROUGH_PARSERS],
)
@pytest.mark.parametrize(
    "raw",
    ["1404-05-18", "1404/05/18", "۱۴۰۴/۰۵/۱۸", "2026-09-14", ""],
)
def test_history_parsers_keep_the_raw_source_date(
    label: str, parser: HistoryParser, build: Callable[[str], Any], raw: str
) -> None:
    rows = parser(build(raw))

    assert rows, f"{label}: the row must survive parsing"
    assert rows[0]["date"] == raw, (
        f"{label}: the parser must not rewrite or invent the market date; "
        "normalisation/quarantine belongs to ingestion"
    )


@pytest.mark.parametrize(
    ("label", "parser", "build"),
    PASSTHROUGH_PARSERS,
    ids=[p[0] for p in PASSTHROUGH_PARSERS],
)
def test_history_parsers_do_not_invent_a_date_when_absent(
    label: str, parser: HistoryParser, build: Callable[[str], Any]
) -> None:
    row = parser(build(""))[0]

    assert row["date"] == "", f"{label}: an absent date must stay absent"


# ── Unreadable prices stay None on nullable columns ───────────────────────


def test_history_price_does_not_zero_fill_an_absent_close() -> None:
    (row,) = TsetmcParser.parse_history_price([{"date": "1404-05-18", "tvol": "۱۲۳"}])

    assert row["price_close"] is None
    assert row["trade_volume"] == 123


def test_gold_currency_pro_history_does_not_zero_fill_an_absent_close() -> None:
    (row,) = GoldCurrencyProParser.parse_daily_history(
        [{"symbol": "XAUUSD", "date": "1404-05-18"}]
    )

    assert row["price_close"] is None

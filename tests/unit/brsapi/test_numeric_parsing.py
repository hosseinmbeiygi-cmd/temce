"""Missing numbers must stay missing, not become zero.

Audit DS-05. The BrsApi parsers collapsed ``None``/unreadable values to
``0``/``0.0``, which published fabricated zero prices; Persian/Arabic
separators (``٬``/``٫``) also parsed as zero.
"""

from __future__ import annotations

from brsapi.parsers.numeric import parse_float, parse_int
from brsapi.parsers.tsetmc import TsetmcParser


def test_missing_and_unreadable_values_are_none() -> None:
    assert parse_float(None) is None
    assert parse_float("") is None
    assert parse_float("   ") is None
    assert parse_float("abc") is None
    assert parse_int(None) is None
    assert parse_int("abc") is None


def test_a_real_zero_stays_zero() -> None:
    assert parse_float(0) == 0.0
    assert parse_float("0") == 0.0
    assert parse_int("0") == 0


def test_separators_and_persian_digits_parse() -> None:
    assert parse_float("1٬234") == 1234.0
    assert parse_float("۱۲٫۵") == 12.5
    assert parse_int("۱,۲۳۴") == 1234


def test_both_parsers_share_the_same_rules() -> None:
    assert TsetmcParser._float(None) is None
    assert TsetmcParser._float("bad") is None
    assert TsetmcParser._int("1.9") == 1


def test_null_price_in_the_payload_does_not_become_zero() -> None:
    records = TsetmcParser.parse_all_symbols(
        [{"id": 1, "l18": "AAA", "l30": "الف", "pl": None, "pc": "1,000"}]
    )

    assert records[0]["price_last"] is None
    assert records[0]["price_close"] == 1000.0

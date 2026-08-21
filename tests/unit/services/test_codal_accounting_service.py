"""Unit tests for the Codal accounting-service number parser.

Covers ``_normalize_number`` — the helper that converts raw spreadsheet
cells (openpyxl values / Persian-formatted strings) into floats for
financial-statement tables.

Regression targets:
  * numeric cells (openpyxl returns int/float for numeric values)
  * Persian/Arabic digits and thousands separators (``,`` and ``٬``)
  * ASCII/Persian minus signs, trailing-minus and parenthesized negatives
  * garbage/empty input must never raise
"""

from __future__ import annotations

import pytest

from services.codal_accounting_service import _normalize_number

# ════════════════════════════════════════════════════════════════
# Basic ASCII input
# ════════════════════════════════════════════════════════════════


class TestAsciiNumbers:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0", 0.0),
            ("123", 123.0),
            ("1,250", 1250.0),
            ("1,250,000", 1250000.0),
            ("  42  ", 42.0),
            ("-12", -12.0),
        ],
    )
    def test_parses(self, raw: str, expected: float) -> None:
        assert _normalize_number(raw) == expected


# ════════════════════════════════════════════════════════════════
# Persian / Arabic digits and separators
# ════════════════════════════════════════════════════════════════


class TestPersianDigits:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("۱۲۳", 123.0),
            ("۰", 0.0),
            ("۱٬۲۵۰", 1250.0),
            ("۲٬۵۰۰٬۰۰۰", 2500000.0),
            ("۱٬۲۵۰،۵۰۰", 1250500.0),  # mixed separators
        ],
    )
    def test_persian_digits_and_separators(self, raw: str, expected: float) -> None:
        assert _normalize_number(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("١٢٣", 123.0),
            ("٥٥٥", 555.0),
            ("٠", 0.0),
        ],
    )
    def test_arabic_digits(self, raw: str, expected: float) -> None:
        assert _normalize_number(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("۱۲۳", 123.0),
            ("123", 123.0),
        ],
    )
    def test_mixed_ascii_persian_digits(self, raw: str, expected: float) -> None:
        assert _normalize_number(raw) == expected


# ════════════════════════════════════════════════════════════════
# Negative numbers (financial-statement conventions)
# ════════════════════════════════════════════════════════════════


class TestNegatives:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("-12", -12.0),
            ("−۱۲", -12.0),  # Unicode minus + Persian digits
            ("(۱۲)", -12.0),  # accounting parentheses
            ("(1,250)", -1250.0),
            ("12-", -12.0),  # trailing minus
            ("-", 0.0),  # bare minus → no digits
        ],
    )
    def test_parses(self, raw: str, expected: float) -> None:
        assert _normalize_number(raw) == expected


# ════════════════════════════════════════════════════════════════
# Numeric cells (openpyxl returns int/float for numeric values)
# ════════════════════════════════════════════════════════════════


class TestNumericCells:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (4500, 4500.0),
            (4500.5, 4500.5),
            (0, 0.0),
            (True, 1.0),
            (False, 0.0),
        ],
    )
    def test_numeric_values(self, raw: int | float | bool, expected: float) -> None:
        assert _normalize_number(raw) == expected


# ════════════════════════════════════════════════════════════════
# Empty / garbage input — must never raise, never return junk
# ════════════════════════════════════════════════════════════════


class TestEdgeCases:
    @pytest.mark.parametrize("raw", [None, "", "   ", "abc", "-", "(", ")"])
    def test_returns_zero(self, raw: object) -> None:
        assert _normalize_number(raw) == 0.0

    @pytest.mark.parametrize("raw", [None, "", "abc", "---", "(abc)"])
    def test_never_raises(self, raw: object) -> None:
        _normalize_number(raw)  # must not raise

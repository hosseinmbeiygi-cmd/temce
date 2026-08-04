"""
Unit tests for Jalali (Shamsi) date conversion in BrsApi sync.

BrsApi TSETMC endpoints (e.g. /Tsetmc/Transaction.php) expect the ``date``
parameter in the Persian calendar (1404-02-22), NOT Gregorian (2026-08-04).
``sync_transactions`` previously passed Gregorian dates through unchanged,
causing HTTP 400 responses. These tests lock the conversion behavior.
"""

from __future__ import annotations

from brsapi.services.sync_service import _to_jalali_date


class TestToJalaliDate:
    def test_gregorian_to_jalali(self) -> None:
        assert _to_jalali_date("2026-08-04") == "1405-05-13"

    def test_gregorian_previous_trading_day(self) -> None:
        assert _to_jalali_date("2026-08-03") == "1405-05-12"

    def test_already_jalali_passthrough(self) -> None:
        assert _to_jalali_date("1404-02-22") == "1404-02-22"
        assert _to_jalali_date("1405-05-12") == "1405-05-12"

    def test_none_and_empty(self) -> None:
        assert _to_jalali_date(None) is None
        assert _to_jalali_date("") == ""

    def test_whitespace_stripped(self) -> None:
        assert _to_jalali_date(" 2026-08-04 ") == "1405-05-13"

    def test_invalid_passthrough(self) -> None:
        # Unparseable values pass through unchanged (no crash)
        assert _to_jalali_date("not-a-date") == "not-a-date"

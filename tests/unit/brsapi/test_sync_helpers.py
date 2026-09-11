"""Tests for BrsApi sync_service pure helpers.

These helpers drive the date and symbol transformations that gate every
BrsApi sync. A regression in digit/Persian normalization would silently
drop or duplicate funds, wasting API quota and corrupting the cache.
"""

from __future__ import annotations

from brsapi.services.sync_service import (
    _dedupe_symbols,
    _normalize_codal_date,
    _normalize_persian,
    _to_jalali_date,
)


def test_to_jalali_passes_through_jalali() -> None:
    """A Jalali-looking date (year 1200-1500) must be returned unchanged."""
    assert _to_jalali_date("1404-02-22") == "1404-02-22"
    assert _to_jalali_date("  1404-02-22  ") == "1404-02-22"


def test_to_jalali_converts_gregorian() -> None:
    """A Gregorian date is converted to Jalali."""
    # 2026-08-04 → 1405-05-13
    assert _to_jalali_date("2026-08-04") == "1405-05-13"


def test_to_jalali_handles_invalid_input() -> None:
    """Unparseable input is returned unchanged (best-effort, not a hard error)."""
    assert _to_jalali_date("not-a-date") == "not-a-date"
    assert _to_jalali_date("") == ""
    assert _to_jalali_date(None) is None


def test_normalize_codal_date_translates_persian_digits() -> None:
    """Codal-style Persian/Arabic-Indic digits are converted to ASCII."""
    assert _normalize_codal_date("۱۴۰۵/۰۵/۰۳") == "1405-05-03"
    assert _normalize_codal_date("٠١٢٣") == "0123"
    # Mixed-digit input normalizes fully.
    assert _normalize_codal_date("1۴۰۵/۰۵/۰۳") == "1405-05-03"


def test_normalize_codal_date_handles_empty() -> None:
    """None/empty/non-string become empty string for safe comparison."""
    assert _normalize_codal_date(None) == ""
    assert _normalize_codal_date("") == ""
    # Pure whitespace collapses to empty after strip.
    assert _normalize_codal_date("   ") == ""


def test_normalize_persian_letters() -> None:
    """Arabic yeh/kaf become Persian so equivalent spellings compare equal."""
    assert _normalize_persian("بيدار") == "بیدار"
    assert _normalize_persian("ك") == "ک"
    # Persian letters pass through.
    assert _normalize_persian("بیدار") == "بیدار"


def test_dedupe_symbols_preserves_order() -> None:
    """Duplicates are removed but the first occurrence's order is kept."""
    assert _dedupe_symbols(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_dedupe_symbols_strips_and_skips_empty() -> None:
    """Whitespace-only and empty entries are dropped."""
    assert _dedupe_symbols(["a", "  ", "", "b", " a "]) == ["a", "b"]
    # Handles None gracefully.
    assert _dedupe_symbols([None, "a", "", "b"]) == ["a", "b"]


def test_dedupe_symbols_empty_input() -> None:
    assert _dedupe_symbols([]) == []

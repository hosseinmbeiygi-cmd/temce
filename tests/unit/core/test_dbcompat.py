"""Unit tests for :mod:`core.dbcompat` — the shared compatibility layer
for the three recurring DB traps (session report 2026-09-19 §6).

Pure-python tests (no DB): every helper is a boundary conversion whose
failure signatures are documented from real production bugs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.dbcompat import as_bigint_id, as_text_id, naive_utc


class TestNaiveUtc:
    def test_aware_converts_to_naive_utc(self):
        aware = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
        assert naive_utc(aware) == datetime(2026, 9, 19, 12, 0)
        assert naive_utc(aware).tzinfo is None

    def test_non_utc_offset_is_shifted(self):
        from datetime import timezone as _timezone

        shifted = datetime(2026, 9, 19, 15, 30, tzinfo=_timezone(timedelta(hours=3, minutes=30)))
        assert naive_utc(shifted) == datetime(2026, 9, 19, 12, 0)

    def test_naive_passes_through(self):
        naive = datetime(2026, 9, 19, 12, 0)
        assert naive_utc(naive) is naive  # untouched, same object


class TestAsBigintId:
    def test_str_and_int(self):
        assert as_bigint_id("42") == 42
        assert as_bigint_id(7) == 7
        assert as_bigint_id(" 42 ") == 42

    def test_rejects_non_numeric(self):
        with pytest.raises(ValueError):
            as_bigint_id("fund_3ac46666")

    def test_rejects_bool_and_none(self):
        with pytest.raises(ValueError):
            as_bigint_id(True)
        with pytest.raises(ValueError):
            as_bigint_id(None)  # type: ignore[arg-type]

    def test_rejects_float(self):
        with pytest.raises(ValueError):
            as_bigint_id(1.5)  # type: ignore[arg-type]


class TestAsTextId:
    def test_int_and_str(self):
        assert as_text_id(42) == "42"
        assert as_text_id("fund_3ac46666") == "fund_3ac46666"

    def test_bytes_decoded(self):
        assert as_text_id(b"fund_1") == "fund_1"

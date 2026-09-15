"""Tests for the basic raw-data validator (no technical computation)."""

from __future__ import annotations

from datetime import UTC, datetime

from ingestion.raw_validation import RawQuoteValidator


def _row(symbol: str = "فولاد", **overrides) -> dict:
    row = {
        "symbol": symbol,
        "ins_id": "12345",
        "price_last": 5000.0,
        "price_close": 4950.0,
        "price_yesterday": 4900.0,
        "trade_volume": 1_000_000,
        "trade_value": 5_000_000_000.0,
        "trade_count": 900,
        "fetched_at": datetime.now(UTC).replace(microsecond=0, tzinfo=None),
    }
    row.update(overrides)
    return row


def test_accepts_clean_rows() -> None:
    report = RawQuoteValidator().validate([_row("فولاد"), _row("خودرو")])
    assert report.accepted_count == 2
    assert report.rejected_count == 0
    assert report.duplicate_symbols == 0


def test_rejects_missing_symbol() -> None:
    report = RawQuoteValidator().validate([_row(symbol="")])
    assert report.accepted_count == 0
    assert report.rejected_count == 1
    assert "missing symbol" in report.rejected[0].reason


def test_rejects_non_mapping_rows() -> None:
    report = RawQuoteValidator().validate(["not-a-row", None])
    assert report.rejected_count == 2
    assert all("not a mapping" in item.reason for item in report.rejected)


def test_rejects_non_numeric_price() -> None:
    report = RawQuoteValidator().validate([_row(price_last="n/a")])
    assert report.rejected_count == 1
    assert "price_last is not numeric" in report.rejected[0].reason


def test_rejects_negative_price() -> None:
    report = RawQuoteValidator().validate([_row(price_close=-1.0)])
    assert report.rejected_count == 1
    assert "negative" in report.rejected[0].reason


def test_rejects_missing_fetched_at() -> None:
    report = RawQuoteValidator().validate([_row(fetched_at=None)])
    assert report.rejected_count == 1
    assert "fetched_at" in report.rejected[0].reason


def test_dedupes_symbols_within_batch() -> None:
    report = RawQuoteValidator().validate([_row("فولاد"), _row("فولاد")])
    assert report.accepted_count == 1
    assert report.duplicate_symbols == 1
    assert report.total_seen == 2


def test_report_serializes_reasons() -> None:
    report = RawQuoteValidator().validate([_row(price_last="bad")])
    payload = report.as_dict()
    assert payload["rejected"] == 1
    assert payload["rejection_reasons"][0]["symbol"] == "فولاد"

"""Unit tests for ``brsapi.quality`` — history/NAV data-quality rules.

Everything here is offline and pure: no database, no BrsApi call. The fixture is
a captured *shape* of ``Gold_Currency_Pro.php?history=2`` (not live data).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from brsapi.quality import (
    ISSUE_CLOSE_OUTSIDE_RANGE,
    ISSUE_HIGH_BELOW_LOW,
    ISSUE_MISSING_CLOSE,
    ISSUE_NON_POSITIVE,
    ISSUE_OPEN_OUTSIDE_RANGE,
    NAV_HISTORY_TABLES,
    OHLC_HISTORY_TABLES,
    daily_bar_issues,
    history_quality_queries,
    is_valid_daily_bar,
    jalali_to_gregorian,
    normalize_jalali_date,
)

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "brsapi" / "history_ohlc_mixed.json"


# ── Jalali date parsing ───────────────────────────────────────────────


class TestNormalizeJalaliDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1405-06-23", "1405-06-23"),
            ("1405/06/23", "1405-06-23"),  # ISSUE-127: slash rows exist in the table
            ("۱۴۰۵/۰۶/۲۳", "1405-06-23"),  # Persian digits
            ("١٤٠٥-٠٦-٢٣", "1405-06-23"),  # Arabic-Indic digits
            (" 1405.6.3 ", "1405-06-03"),  # whitespace + dots + zero padding
            ("1405-6-3", "1405-06-03"),
            (date(1405, 6, 23), "1405-06-23"),
        ],
    )
    def test_accepts_provider_formats(self, raw: object, expected: str) -> None:
        assert normalize_jalali_date(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            None,
            "",
            "   ",
            "1405-13-05",  # month 13
            "1405-06-32",  # day 32
            "2026-09-14",  # Gregorian year — must NOT be treated as Jalali
            "1405-06",  # truncated
            "not-a-date",
            "1405/06/23/01",
        ],
    )
    def test_rejects_non_dates(self, raw: object) -> None:
        assert normalize_jalali_date(raw) is None

    def test_missing_date_is_never_defaulted_to_today(self) -> None:
        """Regression for ISSUE-127: an absent date must stay absent."""
        assert normalize_jalali_date("") is None


class TestJalaliToGregorian:
    def test_known_conversion(self) -> None:
        # 1405-06-23 == 2026-09-14 — the last trading day recorded in the audit.
        assert jalali_to_gregorian("1405-06-23") == date(2026, 9, 14)

    def test_accepts_slash_format(self) -> None:
        assert jalali_to_gregorian("1405/06/12") == date(2026, 9, 3)

    @pytest.mark.parametrize("raw", [None, "", "1405-13-01", "garbage", "2026-09-14"])
    def test_invalid_returns_none(self, raw: object) -> None:
        assert jalali_to_gregorian(raw) is None


# ── OHLC rules ────────────────────────────────────────────────────────


class TestDailyBarIssues:
    def test_valid_bar_has_no_issues(self) -> None:
        assert daily_bar_issues(close=105.0, high=110.0, low=90.0, open=100.0) == ()
        assert is_valid_daily_bar(close=105.0, high=110.0, low=90.0, open=100.0)

    def test_missing_close(self) -> None:
        assert ISSUE_MISSING_CLOSE in daily_bar_issues(close=None, high=110.0, low=90.0)

    def test_high_below_low_is_flagged_and_range_checks_are_skipped(self) -> None:
        issues = daily_bar_issues(close=95.0, high=90.0, low=100.0)
        assert issues == (ISSUE_HIGH_BELOW_LOW,)

    def test_close_outside_range(self) -> None:
        assert ISSUE_CLOSE_OUTSIDE_RANGE in daily_bar_issues(close=120.0, high=110.0, low=90.0)
        assert ISSUE_CLOSE_OUTSIDE_RANGE in daily_bar_issues(close=80.0, high=110.0, low=90.0)

    def test_open_outside_range(self) -> None:
        assert ISSUE_OPEN_OUTSIDE_RANGE in daily_bar_issues(
            close=100.0, high=110.0, low=90.0, open=85.0
        )

    def test_zero_and_negative_prices_are_flagged_not_rewritten(self) -> None:
        zero = daily_bar_issues(close=0.0, high=0.0, low=0.0, open=0.0)
        assert zero.count(ISSUE_NON_POSITIVE + ":close") == 1
        assert len([i for i in zero if i.startswith(ISSUE_NON_POSITIVE)]) == 4
        assert not is_valid_daily_bar(close=0.0, high=0.0, low=0.0, open=0.0)
        assert ISSUE_NON_POSITIVE + ":low" in daily_bar_issues(close=100.0, high=110.0, low=-1.0)

    def test_nan_and_infinity_are_flagged(self) -> None:
        issues = daily_bar_issues(close=float("nan"), high=float("inf"), low=90.0)
        assert any(i.startswith("non_finite:close") for i in issues)
        assert any(i.startswith("non_finite:high") for i in issues)

    def test_missing_high_low_does_not_invent_a_range(self) -> None:
        # Tables allow NULL OHLC columns; a bar with only a close is not "outside a range".
        assert daily_bar_issues(close=105.0) == ()

    def test_boundary_prices_are_valid(self) -> None:
        assert is_valid_daily_bar(close=90.0, high=110.0, low=90.0, open=110.0)


class TestFixtureClassification:
    def test_every_bar_classified_as_documented(self) -> None:
        payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        expected = payload["_expected"]

        counts = {
            "valid": 0,
            "high_below_low": 0,
            "close_outside_range": 0,
            "open_outside_range": 0,
            "non_positive": 0,
            "unparsable_date": 0,
        }
        valid_dates: list[str] = []
        for bar in payload["bars"]:
            trading_date = normalize_jalali_date(bar["date"])
            if trading_date is None:
                counts["unparsable_date"] += 1
                continue
            issues = daily_bar_issues(
                close=bar["close"], high=bar["high"], low=bar["low"], open=bar["open"]
            )
            if not issues:
                counts["valid"] += 1
                valid_dates.append(trading_date)
                continue
            for issue in issues:
                code = issue.split(":")[0]
                if code in counts:
                    counts[code] += 1
                    break

        assert counts == expected
        # Normalisation collapses the three valid separators/digit sets onto ISO Jalali.
        assert sorted(valid_dates) == ["1405-06-21", "1405-06-22", "1405-06-23"]


# ── Read-only diagnostics ─────────────────────────────────────────────


class TestHistoryQualityQueries:
    @pytest.mark.parametrize("table", OHLC_HISTORY_TABLES + NAV_HISTORY_TABLES)
    def test_all_queries_are_read_only_selects(self, table: str) -> None:
        queries = history_quality_queries(table)
        assert queries, "a table must expose at least one check"
        for name, sql in queries.items():
            normalized = " ".join(sql.upper().split())
            assert normalized.startswith(("SELECT", "WITH")), f"{name} is not a SELECT: {sql}"
            for forbidden in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "ALTER", "DROP", "CREATE"):
                assert forbidden not in normalized, f"{name} contains {forbidden}: {sql}"

    def test_ohlc_checks_cover_the_audited_defects(self) -> None:
        checks = history_quality_queries("brsapi_gold_coin_history")
        assert {
            "high_below_low",
            "close_outside_range",
            "open_outside_range",
            "non_positive_price",
            "null_close",
            "duplicate_symbol_date",
            "slash_separated_date",
        } <= set(checks)

    def test_nav_checks_cover_nav_specific_rules(self) -> None:
        checks = history_quality_queries("brsapi_nav_records")
        assert {
            "non_positive_nav_issue",
            "non_positive_nav_redemption",
            "missing_both_nav",
            "issue_redemption_mismatch",
            "duplicate_symbol_date",
        } <= set(checks)

    def test_date_diagnostics_normalize_slashes_and_persian_digits(self) -> None:
        # A raw `MAX(date)` would compare `1405/05/01` with `1405-06-23` and be wrong.
        span = history_quality_queries("brsapi_gold_coin_history")["trading_date_span"]
        assert "TRANSLATE" in span
        assert "REPLACE" in span

    def test_unknown_table_is_refused(self) -> None:
        with pytest.raises(ValueError):
            history_quality_queries("brsapi_symbol_snapshots")
        with pytest.raises(ValueError):
            history_quality_queries("brsapi_gold_coin_history; DROP TABLE funds")

    def test_history_tables_never_use_ingest_date_columns(self) -> None:
        """ISSUE-127 guard: no quality query may key on ingestion timestamps."""
        for table in OHLC_HISTORY_TABLES + NAV_HISTORY_TABLES:
            for name, sql in history_quality_queries(table).items():
                normalized = " ".join(sql.upper().split())
                assert "GREGORIAN_DATE" not in normalized, f"{table}.{name} uses gregorian_date"
                assert "SHAMSI_DATE" not in normalized, f"{table}.{name} uses shamsi_date"

"""Freshness must follow the market date of a history table, not its ingest date.

ISSUE-127: ``brsapi_gold_currency_pro_daily_history`` and
``brsapi_gold_coin_history`` carry ``gregorian_date``/``shamsi_date`` columns that
hold the *ingestion* day. Measuring freshness on them reported a 42-day-old
history as fresh (and made ``/gold/health`` green) right after a backfill.

These tests run offline with a fake session: no database, no BrsApi access.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jdatetime

from core.time import now_tehran
from src.gold_desk.freshness import (
    FRESHNESS_SOURCES,
    FreshnessSource,
    build_freshness_report,
)


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar(self) -> Any:
        return self._value


class _Nested:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _FakeSession:
    """Serves the answers a probe expects, in order, and records the SQL."""

    def __init__(self, answers: list[Any]) -> None:
        self._answers = list(answers)
        self.queries: list[str] = []

    async def execute(self, statement: Any) -> _FakeResult:
        self.queries.append(str(statement))
        return _FakeResult(self._answers.pop(0))

    def begin_nested(self) -> _Nested:
        return _Nested()


def _today_jalali() -> str:
    return jdatetime.date.fromgregorian(date=now_tehran().date()).strftime("%Y-%m-%d")


def _coin_source() -> FreshnessSource:
    return next(s for s in FRESHNESS_SOURCES if s.key == "brsapi_gold_coin_history")


class TestHistorySourceSemantics:
    def test_history_sources_are_jalali_and_use_the_trade_date_column(self) -> None:
        for key in ("brsapi_gold_coin_history", "brsapi_gold_currency_pro_daily_history"):
            src = next(s for s in FRESHNESS_SOURCES if s.key == key)
            assert src.column == "date"
            assert src.calendar == "jalali"

    def test_no_history_source_is_measured_on_an_ingest_column(self) -> None:
        """The regression guard: `gregorian_date` is the ingestion day (ISSUE-127)."""
        history_tables = {"brsapi_gold_coin_history", "brsapi_gold_currency_pro_daily_history", "brsapi_nav_records"}
        checked = 0
        for src in FRESHNESS_SOURCES:
            if src.table in history_tables:
                checked += 1
                assert src.column not in {"gregorian_date", "shamsi_date", "created_at", "fetched_at"}
        assert checked == len(history_tables), "every history table must be monitored"

    def test_nav_records_are_monitored(self) -> None:
        src = next(s for s in FRESHNESS_SOURCES if s.key == "brsapi_nav_records")
        assert src.table == "brsapi_nav_records"
        assert src.calendar == "jalali"

    def test_gold_fund_nav_note_states_what_is_actually_measured(self) -> None:
        """`gold_fund_nav` freshness is the job run, not the NAV as-of date."""
        src = next(s for s in FRESHNESS_SOURCES if s.key == "gold_fund_nav")
        assert src.column == "snapshot_at"
        assert "job" in src.label, "the label must say this is the job run, not the NAV date"
        assert src.note is not None
        assert "brsapi_nav_records" in src.note
        assert "snapshot" in src.note

    def test_note_reaches_the_report(self) -> None:
        src = FreshnessSource("t", "label", "some_table", "ts", 30, note="scope statement")
        session = _FakeSession([datetime.now(UTC) - timedelta(minutes=1), 2])

        report = build_report_sync(session, [src])

        assert report["sources"][0]["note"] == "scope statement"


class TestFreshnessProbe:
    def test_stale_history_is_stale_even_when_ingested_now(self) -> None:
        # 1405-06-23 == 2026-09-14: the last trading day recorded by the audit,
        # ingested weeks later by a backfill.
        session = _FakeSession(["1405-06-23", 44965])

        report = build_report_sync(session, [_coin_source()])

        item = report["sources"][0]
        assert item["last_at"] == "2026-09-14"
        assert item["status"] == "stale"
        assert item["calendar"] == "jalali"
        assert report["overall"] == "stale"
        assert item["age_minutes"] > 2880

    def test_fresh_trade_date_is_ok(self) -> None:
        session = _FakeSession([_today_jalali(), 10])

        report = build_report_sync(session, [_coin_source()])

        item = report["sources"][0]
        assert item["status"] == "ok"
        assert item["age_minutes"] is not None and item["age_minutes"] <= 2880

    def test_slash_separated_jalali_date_is_parsed(self) -> None:
        session = _FakeSession(["1405/06/23", 5])

        report = build_report_sync(session, [_coin_source()])

        assert report["sources"][0]["last_at"] == "2026-09-14"

    def test_probe_query_uses_date_not_ingest_columns(self) -> None:
        session = _FakeSession(["1405-06-23", 1])

        build_report_sync(session, [_coin_source()])

        probe_sql = " ".join(session.queries[0].upper().split())
        assert "FROM BRSAPI_GOLD_COIN_HISTORY" in probe_sql
        assert "GREGORIAN_DATE" not in probe_sql
        assert "MAX(REPLACE(TRANSLATE(DATE" in probe_sql

    def test_unparsable_trade_date_becomes_missing_not_fresh(self) -> None:
        session = _FakeSession(["not-a-date", 7])

        report = build_report_sync(session, [_coin_source()])

        item = report["sources"][0]
        assert item["status"] == "missing"
        assert item["last_at"] is None
        assert "unparsable" in (item["detail"] or "")
        assert report["overall"] == "missing"

    def test_empty_table_is_empty_not_ok(self) -> None:
        session = _FakeSession([None, 0])

        report = build_report_sync(session, [_coin_source()])

        assert report["sources"][0]["status"] == "empty"

    def test_database_error_is_missing(self) -> None:
        class _BrokenSession(_FakeSession):
            async def execute(self, statement: Any) -> _FakeResult:
                raise RuntimeError("column date does not exist")

        report = build_report_sync(_BrokenSession([]), [_coin_source()])

        assert report["sources"][0]["status"] == "missing"
        assert "date" in (report["sources"][0]["detail"] or "")

    def test_gregorian_sources_still_work(self) -> None:
        now = datetime.now(UTC) - timedelta(minutes=1)
        src = FreshnessSource("t", "label", "gold_snapshots", "snapshot_at", 30)
        session = _FakeSession([now, 3])

        report = build_report_sync(session, [src])

        assert report["sources"][0]["status"] == "ok"
        assert report["sources"][0]["calendar"] == "gregorian"


def build_report_sync(session: Any, sources: list[FreshnessSource]) -> dict:
    """Run the async report builder without an event-loop fixture."""
    import asyncio

    return asyncio.run(build_freshness_report(session, sources=sources))


def test_threshold_boundary() -> None:
    """``max_age_minutes`` is an inclusive upper bound on the age."""
    src = FreshnessSource("t", "label", "some_table", "ts", 1440)

    just_inside = _FakeSession([datetime.now(UTC) - timedelta(minutes=1439), 4])
    assert build_report_sync(just_inside, [src])["sources"][0]["status"] == "ok"

    just_outside = _FakeSession([datetime.now(UTC) - timedelta(minutes=1441), 4])
    assert build_report_sync(just_outside, [src])["sources"][0]["status"] == "stale"

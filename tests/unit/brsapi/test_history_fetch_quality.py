"""Offline tests for the gold/coin/FX history ingestion path.

``HistoryFetchService.sync_gold_currency_history`` is exercised with a fake async
session and a patched ``fetch_history``: no network, no BrsApi quota, no database.

Pinned behaviour:
  * the stored ``date`` is the provider's **market date**, normalised to Jalali
    ``YYYY-MM-DD`` — an absent/unparsable date is quarantined, never replaced by
    the ingestion day (ISSUE-127);
  * ``fetched_at`` (client receive time) is written and stays a separate concept
    from ``date`` and from the DB's ``created_at``;
  * bars that violate the OHLC rules are quarantined and counted, not silently
    dropped;
  * a failing INSERT is reported (``success=False`` + ``failed_count``) instead of
    disappearing inside ``contextlib.suppress(Exception)``.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import pytest

from brsapi.services.history_fetch_service import FetchReport, HistoryFetchService

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "brsapi" / "history_ohlc_mixed.json"
_FETCH_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def _bars() -> list[dict[str, Any]]:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return [
        {k: v for k, v in bar.items() if not k.startswith("_")}
        for bar in payload["bars"]
    ]


class _FakeSession:
    """Records executed statements; optionally fails one INSERT."""

    def __init__(self, fail_on_call: int | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.commits = 0
        self.fail_on_call = fail_on_call

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> None:
        self.calls.append((str(statement), params or {}))
        if self.fail_on_call is not None and len(self.calls) == self.fail_on_call:
            raise RuntimeError(
                "there is no unique or exclusion constraint matching the ON CONFLICT specification"
            )

    async def commit(self) -> None:
        self.commits += 1

    # The service wraps each INSERT in its own SAVEPOINT (audit DB-07); the fake
    # session treats that as a no-op context so the recorded calls are unchanged.
    def begin_nested(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    @property
    def inserts(self) -> list[dict[str, Any]]:
        return [params for _sql, params in self.calls if params]


def _run_crypto(
    monkeypatch: pytest.MonkeyPatch, session: _FakeSession, symbols: list[str]
) -> list[FetchReport]:
    """Same fake-session harness, but for the crypto history path."""

    async def fake_fetch(
        self: HistoryFetchService,
        symbol: str,
        date_start: str = "1390-01-01",
        date_end: str | None = None,
    ) -> list[dict[str, Any]]:
        return _bars()

    monkeypatch.setattr(HistoryFetchService, "fetch_history", fake_fetch)
    service = HistoryFetchService(session=session)
    return asyncio.run(service.sync_crypto_history(symbols=symbols))


def _run(monkeypatch: pytest.MonkeyPatch, session: _FakeSession, symbols: list[str]) -> list[FetchReport]:
    async def fake_fetch(
        self: HistoryFetchService,
        symbol: str,
        date_start: str = "1300-01-01",
        date_end: str | None = None,
    ) -> list[dict[str, Any]]:
        return _bars()

    monkeypatch.setattr(HistoryFetchService, "fetch_history", fake_fetch)
    service = HistoryFetchService(session=session)
    return asyncio.run(service.sync_gold_currency_history(symbols=symbols))


class TestHistoryIngestionQuality:
    def test_only_valid_bars_are_written_and_invalid_ones_are_counted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = _FakeSession()

        reports = _run(monkeypatch, session, ["IR_COIN_EMAMI"])

        assert len(reports) == 1
        report = reports[0]
        assert report.record_count == 3
        assert report.invalid_count == 6
        assert report.failed_count == 0
        assert report.success is True
        assert session.commits == 1
        assert len(session.inserts) == 3

    def test_market_date_is_stored_not_the_ingestion_date(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = _FakeSession()

        _run(monkeypatch, session, ["IR_COIN_EMAMI"])

        stored_dates = sorted(str(p["date"]) for p in session.inserts)
        assert stored_dates == ["1405-06-21", "1405-06-22", "1405-06-23"]
        # No row may carry an empty / invented date.
        assert all(p["date"] for p in session.inserts)

    def test_fetched_at_is_written_and_differs_in_kind_from_date(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = _FakeSession()

        _run(monkeypatch, session, ["IR_COIN_EMAMI"])

        stamps = {p["fetched_at"] for p in session.inserts}
        assert len(stamps) == 1, "one HTTP payload must share one receive timestamp"
        stamp = stamps.pop()
        assert _FETCH_STAMP.match(str(stamp)), f"unexpected fetched_at format: {stamp!r}"
        assert not re.match(r"^1[2-5]\d\d-", str(stamp)), "fetched_at must not look like a Jalali date"

        sql = session.calls[0][0]
        assert "fetched_at" in sql
        # The upsert must not overwrite the row's first-seen timestamp.
        assert "fetched_at = EXCLUDED.fetched_at" not in sql

    def test_prices_are_written_unmodified(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = _FakeSession()

        _run(monkeypatch, session, ["IR_COIN_EMAMI"])

        first = next(p for p in session.inserts if p["date"] == "1405-06-23")
        assert (first["o"], first["h"], first["low"], first["c"]) == (100.0, 110.0, 90.0, 105.0)

    def test_gold_symbols_route_to_coin_table_and_others_to_pro_table(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        coin_session = _FakeSession()
        _run(monkeypatch, coin_session, ["IR_COIN_EMAMI"])
        assert all("brsapi_gold_coin_history" in sql for sql, _ in coin_session.calls)

        pro_session = _FakeSession()
        _run(monkeypatch, pro_session, ["USD"])
        assert all("brsapi_gold_currency_pro_daily_history" in sql for sql, _ in pro_session.calls)

    def test_insert_failure_is_reported_not_hidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = _FakeSession(fail_on_call=1)

        reports = _run(monkeypatch, session, ["IR_COIN_EMAMI"])

        report = reports[0]
        assert report.success is False
        assert report.failed_count == 1
        assert report.error is not None and "RuntimeError" in report.error
        assert report.record_count == 2
        assert report.invalid_count == 6

    def test_crypto_history_uses_same_quality_and_error_rules(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = _FakeSession()

        reports = _run_crypto(monkeypatch, session, ["BTC_USDT"])

        report = reports[0]
        assert report.record_count == 3
        assert report.invalid_count == 6
        assert report.failed_count == 0
        assert report.success is True
        assert all("brsapi_crypto_daily_history" in sql for sql, _ in session.calls)
        stored = sorted(str(p["date"]) for p in session.inserts)
        assert stored == ["1405-06-21", "1405-06-22", "1405-06-23"]
        assert _FETCH_STAMP.match(str(session.inserts[0]["fetched_at"]))

    def test_crypto_insert_failure_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = _FakeSession(fail_on_call=1)

        report = _run_crypto(monkeypatch, session, ["BTC_USDT"])[0]

        assert report.success is False
        assert report.failed_count == 1
        assert report.record_count == 2
        assert report.error is not None and "RuntimeError" in report.error

    def test_no_bars_means_no_inserts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def empty_fetch(
            self: HistoryFetchService,
            symbol: str,
            date_start: str = "1300-01-01",
            date_end: str | None = None,
        ) -> list[dict[str, Any]]:
            return []

        monkeypatch.setattr(HistoryFetchService, "fetch_history", empty_fetch)
        session = _FakeSession()

        reports = asyncio.run(
            HistoryFetchService(session=session).sync_gold_currency_history(symbols=["USD"])
        )

        assert reports[0].record_count == 0
        assert reports[0].success is True
        assert session.calls == []

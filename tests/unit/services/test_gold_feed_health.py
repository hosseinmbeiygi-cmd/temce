"""Unit tests for gold feed health recording.

Providers are plain ``{name, fetch}`` mocks; no real network calls.
"""

from __future__ import annotations

import time

import pytest

from services.gold.feed_health import check_gold_feed_health
from services.gold.macro_indicators import GoldFeedUnavailableError

NOW = 1_700_000_000.0


class FakeSession:
    def __init__(self) -> None:
        self.rows: list = []
        self.commits = 0

    def add_all(self, rows) -> None:
        self.rows.extend(rows)

    async def commit(self) -> None:
        self.commits += 1


def _provider(name: str, result):
    def fetch():
        if isinstance(result, BaseException):
            raise result
        return result

    return {"name": name, "fetch": fetch}


def _quote(price: float, age_seconds: float = 10.0) -> dict:
    return {"price": price, "timestamp": NOW - age_seconds}


async def test_success_records_attempt_and_primary_status() -> None:
    session = FakeSession()
    providers = [_provider("brsapi", _quote(2_400.0))]

    result = await check_gold_feed_health(session, providers, now=NOW)

    assert result["ok"] is True
    assert result["provider"] == "brsapi"
    assert result["price"] == pytest.approx(2_400.0)
    assert result["primary"]["provider"] == "brsapi"
    assert result["primary"]["status"] == "ok"
    assert result["primary"]["ok"] is True
    assert len(session.rows) == 1
    assert session.commits == 1

    row = session.rows[0]
    assert row.check_id == result["check_id"]
    assert row.provider == "brsapi"
    assert row.status == "ok"
    assert row.ok is True
    assert row.price == pytest.approx(2_400.0)
    assert row.age_seconds == pytest.approx(10.0)
    assert row.latency_ms is not None
    assert row.latency_ms >= 0
    assert row.error is None


async def test_primary_error_marks_fallback_used() -> None:
    session = FakeSession()
    providers = [
        _provider("brsapi", RuntimeError("HTTP 500")),
        _provider("yahoo", _quote(2_401.0)),
    ]

    result = await check_gold_feed_health(session, providers, now=NOW)

    assert result["provider"] == "yahoo"
    assert result["fallback_used"] is True
    assert result["primary"]["status"] == "error"
    assert result["primary"]["ok"] is False
    assert [row.status for row in session.rows] == ["error", "ok"]
    assert session.rows[0].price is None
    assert session.rows[1].price == pytest.approx(2_401.0)


async def test_stale_quote_is_recorded_and_failover_happens() -> None:
    session = FakeSession()
    providers = [
        _provider("brsapi", _quote(2_400.0, age_seconds=300.0)),
        _provider("yahoo", _quote(2_402.0, age_seconds=5.0)),
    ]

    result = await check_gold_feed_health(session, providers, now=NOW)

    assert result["provider"] == "yahoo"
    assert session.rows[0].status == "stale"
    assert session.rows[0].age_seconds == pytest.approx(300.0)
    assert session.rows[1].status == "ok"


async def test_timeout_is_recorded_and_fallback_succeeds() -> None:
    session = FakeSession()

    def slow() -> dict:
        time.sleep(0.2)
        return _quote(2_400.0)

    providers = [{"name": "brsapi", "fetch": slow}, _provider("yahoo", _quote(2_401.0))]

    result = await check_gold_feed_health(session, providers, timeout_seconds=0.05, now=NOW)

    assert result["provider"] == "yahoo"
    assert session.rows[0].status == "timeout"
    assert session.rows[0].latency_ms is not None
    assert session.rows[0].latency_ms >= 50


async def test_all_fail_persists_attempts_then_raises() -> None:
    session = FakeSession()
    providers = [
        _provider("brsapi", RuntimeError("HTTP 500")),
        _provider("yahoo", _quote(2_400.0, age_seconds=500.0)),
    ]

    with pytest.raises(GoldFeedUnavailableError) as info:
        await check_gold_feed_health(session, providers, now=NOW)

    assert [row.status for row in session.rows] == ["error", "stale"]
    assert session.commits == 1
    assert info.value.attempts[0]["status"] == "error"
    assert getattr(info.value, "check_id", None) == session.rows[0].check_id


async def test_primary_not_attempted_is_reported_as_unknown() -> None:
    session = FakeSession()
    providers = [_provider("yahoo", _quote(2_401.0))]

    result = await check_gold_feed_health(session, providers, now=NOW)

    assert result["primary"]["provider"] == "brsapi"
    assert result["primary"]["status"] == "not_attempted"
    assert result["primary"]["ok"] is False

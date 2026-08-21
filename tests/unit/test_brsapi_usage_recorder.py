"""Unit tests for the BrsApi daily-usage report stack.

Covers:
  1. ``BrsApiUsageRecorder`` — in-memory accumulation, additive DB upsert
     flush (``ON CONFLICT (usage_date) DO UPDATE``), and resilience when the
     DB is unavailable (counters must NOT be lost).
  2. Governor wiring — a granted ``acquire()`` records usage and a
     ``report_302()`` records a block on the attached recorder.
  3. The admin endpoint ``GET /api/v1/brsapi/manage/usage`` — response
     contract for the admin usage widget (with a fake DB session so no real
     database is needed).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import AsyncClient

from brsapi.budget import BrsApiBudgetGovernor
from brsapi.usage_recorder import BrsApiUsageRecorder

# ── Fakes ────────────────────────────────────────────────────────────────


class _FakeSession:
    """Minimal AsyncSession stand-in: records executed statements and returns
    canned rows."""

    def __init__(self, rows: list[Any] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[Any] = []

    async def execute(self, stmt: Any):
        self.executed.append(stmt)
        return _FakeResult(self.rows)

    async def commit(self) -> None:
        pass


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeFactory:
    """``async with factory() as session`` stand-in."""

    def __init__(self, session: _FakeSession, fail: bool = False) -> None:
        self._session = session
        self._fail = fail

    async def __aenter__(self) -> _FakeSession:
        if self._fail:
            raise RuntimeError("db down")
        return self._session

    async def __aexit__(self, *args: Any) -> bool:
        return False


class _FakeLimiter:
    """Tiny RateLimiter stand-in with just the attributes the governor reads."""

    def __init__(self, daily: int = 1000) -> None:
        self._daily_limit = daily
        self._five_min_limit = 500
        self._fail_fast = True
        self._daily_count = 0
        self._daily_date = ""
        self._5min_window: list[float] = []

    async def acquire(self, category: str, tokens: int = 1, endpoint: str = "", fail_fast: bool | None = None) -> None:
        self._daily_count += tokens

    def status(self) -> dict[str, Any]:
        return {"global": {"daily_count": self._daily_count, "daily_remaining": self._daily_limit}}


# ── Recorder accumulation + flush ────────────────────────────────────────


async def test_record_used_accumulates_in_memory() -> None:
    rec = BrsApiUsageRecorder(session_factory=lambda: _FakeFactory(_FakeSession()))
    rec.record_used()
    rec.record_used(tokens=2)
    rec.record_block("https://cdn.example/Windows.iso")

    pending = rec.pending_days()
    assert len(pending) == 1
    day = next(iter(pending.values()))
    assert day["count"] == 3
    assert day["blocked"] == 1
    assert day["last_request_at"] is not None
    assert day["blocked_at"] is not None


async def test_flush_builds_additive_upsert_and_clears_memory() -> None:
    session = _FakeSession()
    rec = BrsApiUsageRecorder(session_factory=lambda: _FakeFactory(session))
    rec.record_used()
    rec.record_used(tokens=2)

    result = await rec.flush()

    assert result["flushed_days"] == 1
    assert result["error"] is None
    assert rec.pending_days() == {}, "counters must be cleared after a successful flush"

    # The executed statement must be an INSERT ... ON CONFLICT (usage_date)
    # DO UPDATE — the additive upsert that makes multi-worker counting safe.
    assert session.executed, "expected at least one statement"
    stmt = session.executed[0]
    from sqlalchemy.dialects import postgresql

    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "INSERT INTO brsapi_daily_usage" in sql
    assert "ON CONFLICT" in sql
    assert "request_count" in sql


async def test_flush_failure_keeps_counters_in_memory() -> None:
    rec = BrsApiUsageRecorder(session_factory=lambda: _FakeFactory(_FakeSession(), fail=True))
    rec.record_used()
    rec.record_used()

    result = await rec.flush()

    assert result["flushed_days"] == 0
    assert result["error"] is not None
    assert rec.pending_days(), "counters must survive a failed flush (retry next window)"


async def test_flush_with_nothing_pending_is_noop() -> None:
    rec = BrsApiUsageRecorder(session_factory=lambda: _FakeFactory(_FakeSession()))
    assert await rec.flush() == {"flushed_days": 0, "error": None}


# ── Governor wiring ──────────────────────────────────────────────────────


async def test_governor_acquire_records_usage() -> None:
    recorder = Mock(spec=BrsApiUsageRecorder)
    g = BrsApiBudgetGovernor(
        rate_limiter=_FakeLimiter(),
        persist=False,
        usage_recorder=recorder,
    )
    await g.acquire("tsetmc")
    recorder.record_used.assert_called_once_with(1)


async def test_governor_302_records_block() -> None:
    recorder = Mock(spec=BrsApiUsageRecorder)
    g = BrsApiBudgetGovernor(
        rate_limiter=_FakeLimiter(),
        persist=False,
        block_cooldown=60,
        usage_recorder=recorder,
    )
    await g.report_302("https://cdn.example/Windows.iso")
    recorder.record_block.assert_called_once_with("https://cdn.example/Windows.iso")


async def test_governor_without_recorder_still_works() -> None:
    g = BrsApiBudgetGovernor(rate_limiter=_FakeLimiter(), persist=False)
    await g.acquire("tsetmc")
    await g.report_302("loc")
    assert (await g.is_blocked()) is True


# ── Admin endpoint ──────────────────────────────────────────────────────


def _usage_row(**over: Any) -> SimpleNamespace:
    vals = {
        "usage_date": "2026-08-13",
        "request_count": 423,
        "daily_limit": 5000,
        "blocked_count": 0,
        "blocked_at": None,
        "last_request_at": None,
        "updated_at": None,
    }
    vals.update(over)
    return SimpleNamespace(**vals)


async def test_daily_usage_endpoint_contract(app, client: AsyncClient) -> None:
    from datetime import datetime

    from apps.api.dependencies import get_db_session

    session = _FakeSession([
        _usage_row(usage_date="2026-08-13", request_count=423, blocked_count=1,
                   blocked_at=datetime(2026, 8, 13, 9, 30, 0)),
        _usage_row(usage_date="2026-08-12", request_count=387, daily_limit=4000),
    ])

    async def _override_session():
        return session

    app.dependency_overrides[get_db_session] = _override_session

    fake_governor = Mock()
    fake_governor.stats = AsyncMock(return_value={"global": {"daily_count": 5}})

    import brsapi.budget as budget_mod
    original = budget_mod.get_budget_governor
    budget_mod.get_budget_governor = Mock(return_value=fake_governor)
    try:
        resp = await client.get("/api/v1/brsapi/manage/usage", params={"days": 30})
    finally:
        budget_mod.get_budget_governor = original
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    data = body["data"]
    assert data["query_days"] == 30
    assert len(data["days"]) == 2
    assert data["days"][0]["usage_date"] == "2026-08-13"
    assert data["days"][0]["request_count"] == 423
    assert data["days"][0]["blocked_count"] == 1
    assert data["days"][0]["daily_limit"] == 5000

    summary = data["summary"]
    assert summary["days_recorded"] == 2
    assert summary["total_requests"] == 423 + 387
    assert summary["blocked_days"] == 1
    assert summary["max_per_day"] == 423

    assert data["live"] == {"global": {"daily_count": 5}}


async def test_daily_usage_endpoint_handles_empty_table(app, client: AsyncClient) -> None:
    from apps.api.dependencies import get_db_session

    session = _FakeSession([])

    async def _override_session():
        return session

    app.dependency_overrides[get_db_session] = _override_session

    import brsapi.budget as budget_mod
    original = budget_mod.get_budget_governor
    budget_mod.get_budget_governor = Mock(return_value=Mock(stats=AsyncMock(return_value={})))
    try:
        resp = await client.get("/api/v1/brsapi/manage/usage")
    finally:
        budget_mod.get_budget_governor = original
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["days"] == []
    assert body["data"]["summary"] == {}


@pytest.mark.asyncio
async def test_flush_endpoint() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from apps.api.endpoints.brsapi import router as brsapi_router

    app = FastAPI()
    app.include_router(brsapi_router, prefix="/api/v1/brsapi")

    import brsapi.usage_recorder as ur_mod
    fake_rec = Mock(spec=BrsApiUsageRecorder)
    fake_rec.flush = AsyncMock(return_value={"flushed_days": 1, "error": None})
    ur_mod.get_usage_recorder = Mock(return_value=fake_rec)

    with TestClient(app) as tc:
        resp = tc.post("/api/v1/brsapi/manage/usage/flush")
    assert resp.status_code == 200
    assert resp.json()["data"]["flushed_days"] == 1

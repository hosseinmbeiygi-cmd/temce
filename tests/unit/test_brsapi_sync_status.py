"""Regression tests for the frontend sync-dashboard endpoints.

The frontend ``SyncStatus`` widget, ``/admin``, ``/sync`` and ``/sync-manager``
pages depend on:

- ``GET /api/v1/brsapi/sync-status``  → per-section freshness map
- ``GET /api/v1/brsapi/sync-history`` → recent sync-log entries

These endpoints previously did not exist (the frontend got 404), which made
the whole manual-sync UI in the admin and dashboard pages fail. These tests
lock in the response contract so a rename/removal cannot silently break the
UI again.

``test_sync_history_returns_list`` seeds a real ``brsapi_sync_log`` row
first — without that, the history assertions would pass vacuously against an
empty table (the endpoint only touches the per-item fields inside its row
loop, so a wrong attribute name would return 200 on zero rows).
"""

from __future__ import annotations

import os
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from brsapi.models.base import SyncLogModel
from core.time import utc_now_naive


def _db_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://market:market@localhost:5432/market_test",
    )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

# Keys the frontend renders (must match DEFAULT_SYNC_SETTINGS in sync-settings.ts)
EXPECTED_SYNC_KEYS = {
    "symbols",
    "commodities",
    "gold_coin",
    "currency",
    "crypto",
    "index",
    "ime_futures",
    "ime_options",
    "options",
    "codal",
}

ENTRY_FIELDS = {"last_fetched", "record_count", "age_minutes", "status", "max_age_minutes"}
VALID_STATUSES = {"ok", "stale", "outdated", "missing", "unknown", "error"}


@pytest.mark.asyncio
@pytest.mark.needs_db
async def test_sync_status_returns_all_sections(client: AsyncClient) -> None:
    """The sync-status map covers every section the frontend renders."""
    resp = await client.get("/api/v1/brsapi/sync-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    data = body["data"]
    assert isinstance(data, dict)
    # Exact match both ways: every frontend key must be present AND no extra
    # keys may leak (the frontend iterates this map and would render an
    # unknown section if an extra key slipped in).
    assert set(data.keys()) == EXPECTED_SYNC_KEYS

    for key in EXPECTED_SYNC_KEYS:
        entry = data[key]
        assert set(entry.keys()) >= ENTRY_FIELDS, f"{key} entry missing fields: {entry}"
        assert entry["status"] in VALID_STATUSES, f"{key} status invalid: {entry['status']}"
        assert isinstance(entry["record_count"], int) and entry["record_count"] >= 0
        assert entry["max_age_minutes"] > 0
        # ISO timestamp when present, otherwise null
        if entry["last_fetched"] is not None:
            assert "T" in entry["last_fetched"]


@pytest.mark.asyncio
@pytest.mark.needs_db
async def test_sync_history_returns_list(client: AsyncClient) -> None:
    """Sync history is a list of log entries with the fields the UI needs.

    Seeds a real ``brsapi_sync_log`` row (unique endpoint + recent
    ``completed_at``) so the per-item field assertions actually run instead
    of passing vacuously against an empty table, then cleans it up.
    """
    engine = create_async_engine(_db_url())
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    marker = f"__test_sync_history_{os.getpid()}_{utc_now_naive().microsecond}"

    async def _remove_marker_rows() -> None:
        async with Session() as session:
            await session.execute(delete(SyncLogModel).where(SyncLogModel.endpoint == marker))
            await session.commit()

    try:
        async with Session() as session:
            session.add(
                SyncLogModel(
                    endpoint=marker,
                    category="test",
                    status="success",
                    items_count=42,
                    duration_ms=123.0,
                    started_at=utc_now_naive() - timedelta(minutes=5),
                    completed_at=utc_now_naive() - timedelta(minutes=5),
                )
            )
            await session.commit()

        resp = await client.get(
            "/api/v1/brsapi/sync-history", params={"hours": 24, "limit": 50}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        assert len(body["data"]) >= 1, "expected at least the seeded sync-log row"

        seeded = [it for it in body["data"] if it.get("endpoint") == marker]
        assert seeded, "seeded sync-log row missing from history response"
        item = seeded[0]
        assert item["category"] == "test"
        assert item["status"] == "success"
        assert item["items_count"] == 42
        assert item["duration_ms"] == 123.0
        assert item["time"] is not None and "T" in item["time"]
        assert item["completed_at"] is not None and "T" in item["completed_at"]

        # All items expose the contract fields (defensive on non-seeded rows).
        for it in body["data"]:
            assert "time" in it
            assert "endpoint" in it
            assert "category" in it
            assert "status" in it
            assert "items_count" in it
            assert "duration_ms" in it
            assert "completed_at" in it
    finally:
        await _remove_marker_rows()
        await engine.dispose()

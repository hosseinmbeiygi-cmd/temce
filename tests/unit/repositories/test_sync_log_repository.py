"""Tests for brsapi.repositories.base.SyncLogRepository."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.base import SyncLogModel
from brsapi.repositories.base import SyncLogRepository


@pytest.fixture
def sync_log_repo(db_session: AsyncSession) -> SyncLogRepository:
    return SyncLogRepository(db_session)


@pytest.mark.asyncio
async def test_get_sync_stats_empty(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """Querying a non-existent endpoint should return an empty stats list."""
    stats = await sync_log_repo.get_sync_stats(endpoint="/NonExistent/Endpoint.php", window_days=7)
    assert stats == []


@pytest.mark.asyncio
async def test_get_sync_stats_calculation(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """Error rate, avg duration, and last success are calculated correctly."""
    now = datetime.now()
    endpoint = f"/Test/Endpoint-{uuid4()}.php"

    rows = [
        SyncLogModel(
            endpoint=endpoint,
            category="test",
            status="success",
            items_count=10,
            duration_ms=100.0,
            started_at=now - timedelta(hours=3),
            completed_at=now - timedelta(hours=3),
        ),
        SyncLogModel(
            endpoint=endpoint,
            category="test",
            status="success",
            items_count=20,
            duration_ms=200.0,
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=2),
        ),
        SyncLogModel(
            endpoint=endpoint,
            category="test",
            status="error",
            items_count=0,
            duration_ms=50.0,
            error_message="boom",
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(hours=1),
        ),
    ]
    session = sync_log_repo.session
    session.add_all(rows)
    await session.commit()

    stats = await sync_log_repo.get_sync_stats(endpoint=endpoint, window_days=7)
    assert len(stats) == 1

    stat = stats[0]
    assert stat["endpoint"] == endpoint
    assert stat["total_runs"] == 3
    assert stat["success_count"] == 2
    assert stat["error_count"] == 1
    assert round(float(stat["error_rate"]), 2) == 33.33
    assert round(float(stat["avg_duration_ms"]), 2) == 116.67
    assert stat["last_success_at"] is not None
    assert stat["last_run_at"] is not None


@pytest.mark.asyncio
async def test_get_sync_stats_time_window(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """Logs older than the window should be excluded."""
    now = datetime.now()
    endpoint = f"/Test/Old-{uuid4()}.php"

    session = sync_log_repo.session
    session.add_all([
        SyncLogModel(
            endpoint=endpoint,
            category="test",
            status="error",
            duration_ms=10.0,
            started_at=now - timedelta(days=10),
            completed_at=now - timedelta(days=10),
        ),
        SyncLogModel(
            endpoint=endpoint,
            category="test",
            status="success",
            duration_ms=20.0,
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(hours=1),
        ),
    ])
    await session.commit()

    stats = await sync_log_repo.get_sync_stats(endpoint=endpoint, window_days=7)
    assert len(stats) == 1
    stat = stats[0]
    assert stat["total_runs"] == 1
    assert stat["success_count"] == 1
    assert stat["error_count"] == 0
    assert stat["error_rate"] == 0.0
    assert stat["avg_duration_ms"] == 20.0


@pytest.mark.asyncio
async def test_get_sync_stats_per_endpoint(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """Stats are grouped per endpoint."""
    now = datetime.now()

    a_endpoint = f"A-{uuid4()}.php"
    b_endpoint = f"B-{uuid4()}.php"
    session = sync_log_repo.session
    session.add_all([
        SyncLogModel(
            endpoint=a_endpoint,
            category="test",
            status="success",
            duration_ms=10.0,
            started_at=now,
            completed_at=now,
        ),
        SyncLogModel(
            endpoint=b_endpoint,
            category="test",
            status="error",
            duration_ms=20.0,
            started_at=now,
            completed_at=now,
        ),
    ])
    await session.commit()

    a_stats = await sync_log_repo.get_sync_stats(endpoint=a_endpoint, window_days=7)
    b_stats = await sync_log_repo.get_sync_stats(endpoint=b_endpoint, window_days=7)
    assert len(a_stats) == 1
    assert len(b_stats) == 1
    assert a_stats[0]["total_runs"] == 1
    assert b_stats[0]["total_runs"] == 1
    assert a_stats[0]["error_rate"] == 0.0
    assert b_stats[0]["error_rate"] == 100.0


@pytest.mark.asyncio
async def test_get_sync_stats_filter_by_endpoint(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """Filtering by endpoint returns only that endpoint's stats."""
    now = datetime.now()
    session = sync_log_repo.session
    a_endpoint = f"A-{uuid4()}.php"
    b_endpoint = f"B-{uuid4()}.php"
    session.add_all([
        SyncLogModel(endpoint=a_endpoint, category="test", status="success", duration_ms=10.0, started_at=now, completed_at=now),
        SyncLogModel(endpoint=b_endpoint, category="test", status="error", duration_ms=20.0, started_at=now, completed_at=now),
    ])
    await session.commit()

    stats = await sync_log_repo.get_sync_stats(endpoint=a_endpoint, window_days=7)
    assert len(stats) == 1
    assert stats[0]["endpoint"] == a_endpoint

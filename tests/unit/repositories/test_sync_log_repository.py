"""Tests for brsapi.repositories.base.SyncLogRepository.

Revision: auto-generated for DATA-396 needs_sync test coverage.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.base import SyncLogModel
from brsapi.repositories.base import SyncLogRepository
from core.time import utc_now_naive


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
    now = utc_now_naive()
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
    now = utc_now_naive()
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
    now = utc_now_naive()

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
    now = utc_now_naive()
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


@pytest.mark.asyncio
async def test_needs_sync_no_previous_sync(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """When no previous sync exists, needs_sync should return True."""
    endpoint = "/Test/Endpoint.php"
    result = await sync_log_repo.needs_sync(endpoint)
    assert result is True


@pytest.mark.asyncio
async def test_needs_sync_no_completed_at(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """When last sync has no completed_at, needs_sync should return True."""
    endpoint = "/Test/Endpoint.php"
    row = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=utc_now_naive(),
        # completed_at is None!
    )
    sync_log_repo.session.add(row)
    await sync_log_repo.session.commit()

    result = await sync_log_repo.needs_sync(endpoint)
    assert result is True


@pytest.mark.asyncio
async def test_needs_sync_within_interval(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """When last sync is within the interval, needs_sync should return False."""
    now = utc_now_naive()
    endpoint = "/Test/Endpoint.php"
    row = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=now - timedelta(seconds=10),
        completed_at=now - timedelta(seconds=10),
    )
    sync_log_repo.session.add(row)
    await sync_log_repo.session.commit()

    # Interval is 60 seconds (default), last sync was 10 seconds ago
    # 10 seconds < 60 seconds, so needs_sync should return False (don't need sync)
    result = await sync_log_repo.needs_sync(endpoint, interval_seconds=60)
    assert result is False  # 10s elapsed < 60s interval, skip sync


@pytest.mark.asyncio
async def test_needs_sync_custom_interval(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """When custom interval is used, needs_sync respects it."""
    now = utc_now_naive()
    endpoint = "/Test/Endpoint.php"
    row = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=now - timedelta(seconds=30),
        completed_at=now - timedelta(seconds=30),
    )
    sync_log_repo.session.add(row)
    await sync_log_repo.session.commit()

    # Custom interval is 50 seconds, last sync was 30 seconds ago
    # 30 seconds < 50 seconds, so needs_sync should return False
    result = await sync_log_repo.needs_sync(endpoint, interval_seconds=50)
    assert result is False  # 30s elapsed < 50s interval, skip sync


@pytest.mark.asyncio
async def test_needs_sync_expired_interval(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """When interval has expired, needs_sync should return True."""
    now = utc_now_naive()
    endpoint = "/Test/Endpoint.php"
    row = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=now - timedelta(seconds=70),
        completed_at=now - timedelta(seconds=70),
    )
    sync_log_repo.session.add(row)
    await sync_log_repo.session.commit()

    # Interval is 60 seconds, last sync was 70 seconds ago
    # 70 seconds > 60 seconds, so needs_sync should return True
    result = await sync_log_repo.needs_sync(endpoint, interval_seconds=60)
    assert result is True  # 70s elapsed >= 60s interval, needs sync

@pytest.mark.asyncio
async def test_needs_sync_exact_interval_boundary(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """When elapsed time equals interval, needs_sync should return True (boundary case)."""

    from brsapi.models.base import SyncLogModel

    now = utc_now_naive()
    endpoint = "/Test/Endpoint.php"
    row = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=now - timedelta(seconds=60),
        completed_at=now - timedelta(seconds=60),
    )
    sync_log_repo.session.add(row)
    await sync_log_repo.session.commit()

    # Elapsed = 60s, interval = 60s → 60 >= 60 → True (needs sync)
    result = await sync_log_repo.needs_sync(endpoint, interval_seconds=60)
    assert result is True  # boundary: elapsed == interval


@pytest.mark.asyncio
async def test_needs_sync_zero_interval(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """When interval is 0, needs_sync should always return True (immediate sync)."""

    from brsapi.models.base import SyncLogModel

    now = utc_now_naive()
    endpoint = "/Test/Endpoint.php"
    row = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=now - timedelta(seconds=10),
        completed_at=now - timedelta(seconds=10),
    )
    sync_log_repo.session.add(row)
    await sync_log_repo.session.commit()

    # Interval = 0s → elapsed (10s) >= 0 → True (always needs sync)
    result = await sync_log_repo.needs_sync(endpoint, interval_seconds=0)
    assert result is True  # zero interval always triggers sync


@pytest.mark.asyncio
async def test_needs_sync_large_interval(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """When interval is very large (1 day), needs_sync should return False (recent sync)."""

    from brsapi.models.base import SyncLogModel

    now = utc_now_naive()
    endpoint = "/Test/Endpoint.php"
    row = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=now - timedelta(seconds=30),
        completed_at=now - timedelta(seconds=30),
    )
    sync_log_repo.session.add(row)
    await sync_log_repo.session.commit()

    # Interval = 86400s (1 day), elapsed = 30s → 30 < 86400 → False (skip sync)
    result = await sync_log_repo.needs_sync(endpoint, interval_seconds=86400)
    assert result is False  # 30s elapsed < 1 day interval, skip sync


@pytest.mark.asyncio
async def test_needs_sync_multiple_syncs_decreasing_interval(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """Test that needs_sync correctly handles multiple syncs with decreasing intervals."""

    from brsapi.models.base import SyncLogModel

    now = utc_now_naive()
    endpoint = "/Test/Endpoint.php"

    # First sync: 2 hours ago
    row1 = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=2),
    )
    sync_log_repo.session.add(row1)

    # Second sync: 1 hour ago (more recent)
    row2 = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=now - timedelta(hours=1),
        completed_at=now - timedelta(hours=1),
    )
    sync_log_repo.session.add(row2)
    await sync_log_repo.session.commit()

    # With interval=60s: last sync was 1 hour ago = 3600s > 60s → True (needs sync)
    result = await sync_log_repo.needs_sync(endpoint, interval_seconds=60)
    assert result is True  # 3600s elapsed >= 60s interval


@pytest.mark.asyncio
async def test_needs_sync_recent_multiple_syncs(db_session: AsyncSession, sync_log_repo: SyncLogRepository) -> None:
    """Test that needs_sync uses the MOST RECENT sync (not the first)."""

    from brsapi.models.base import SyncLogModel

    now = utc_now_naive()
    endpoint = "/Test/Endpoint.php"

    # First sync: 2 hours ago
    row1 = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=2),
    )
    sync_log_repo.session.add(row1)

    # Second sync: 10 seconds ago (more recent)
    row2 = SyncLogModel(
        endpoint=endpoint,
        category="test",
        status="success",
        items_count=10,
        duration_ms=100.0,
        started_at=now - timedelta(seconds=10),
        completed_at=now - timedelta(seconds=10),
    )
    sync_log_repo.session.add(row2)
    await sync_log_repo.session.commit()

    # With interval=60s: last sync was 10s ago = 10s < 60s → False (skip sync)
    # The method should use the most recent (row2), not the oldest (row1)
    result = await sync_log_repo.needs_sync(endpoint, interval_seconds=60)
    assert result is False  # 10s elapsed < 60s interval, skip sync (uses most recent)


@pytest.mark.asyncio
async def test_record_persists_outcome(
    db_session: AsyncSession, sync_log_repo: SyncLogRepository
) -> None:
    """The machine-readable outcome must survive the round-trip to the table."""
    entry = await sync_log_repo.record(
        endpoint="/Test/Outcome.php",
        category="test",
        status="error",
        error_message="BrsApi returned an HTML page instead of JSON",
        outcome="malformed",
    )
    await db_session.commit()

    stored = await db_session.get(SyncLogModel, entry.id)
    assert stored is not None
    assert stored.outcome == "malformed"


@pytest.mark.asyncio
async def test_record_defaults_outcome_to_unknown(
    db_session: AsyncSession, sync_log_repo: SyncLogRepository
) -> None:
    """Callers that do not classify a run must not claim a success outcome."""
    entry = await sync_log_repo.record(
        endpoint="/Test/Unclassified.php",
        category="test",
    )
    await db_session.commit()

    assert entry.outcome == "unknown"


@pytest.mark.asyncio
async def test_needs_sync_scopes_to_params(
    db_session: AsyncSession, sync_log_repo: SyncLogRepository
) -> None:
    """A recent sync of one param set must not suppress a different param set."""
    endpoint = f"/Test/ScopedParams-{uuid4()}.php"
    await sync_log_repo.record(
        endpoint=endpoint, category="test", params={"type": "1"}
    )
    await db_session.commit()

    assert (
        await sync_log_repo.needs_sync(
            endpoint, interval_seconds=60, params={"type": "1"}
        )
        is False
    )
    assert (
        await sync_log_repo.needs_sync(
            endpoint, interval_seconds=60, params={"type": "2"}
        )
        is True
    )


@pytest.mark.asyncio
async def test_needs_sync_redacts_credentials_before_matching(
    db_session: AsyncSession, sync_log_repo: SyncLogRepository
) -> None:
    """API keys must not break dedup: both sides are stored/looked up redacted."""
    endpoint = f"/Test/Redacted-{uuid4()}.php"
    await sync_log_repo.record(
        endpoint=endpoint, category="test", params={"key": "s3cret", "type": "1"}
    )
    await db_session.commit()

    assert (
        await sync_log_repo.needs_sync(
            endpoint, interval_seconds=60, params={"key": "other-key", "type": "1"}
        )
        is False
    )

"""Unit tests for the /data-admin aggregation endpoint.

Tests run entirely against mocked DB sessions and Redis; no live services.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.endpoints.data_admin import (
    PIPELINE_REGISTRY,
    _FRESHNESS_COLUMNS,
    _get_job_stats_24h,
    _get_last_job_runs,
    _get_recent_failures,
    _get_redis_queue_depths,
    _get_table_row_estimates,
    _staleness_label,
    _staleness_seconds,
    data_overview,
    data_sources,
    table_freshness,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _mock_session_scalar(value):
    result = MagicMock()
    result.scalar.return_value = value
    result.fetchone.return_value = (10, 7, 2, 1)
    result.fetchall.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _mock_session_rows(rows):
    result = MagicMock()
    result.fetchall.return_value = rows
    result.fetchone.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


# ── PIPELINE_REGISTRY ──────────────────────────────────────────────────────────


def test_pipeline_registry_is_non_empty():
    assert len(PIPELINE_REGISTRY) > 0


def test_pipeline_registry_has_required_fields():
    required = {"id", "name", "name_en", "source", "job_name", "schedule", "tables", "category", "status"}
    for src in PIPELINE_REGISTRY:
        missing = required - set(src.keys())
        assert not missing, f"Source {src.get('id')} missing: {missing}"


def test_pipeline_registry_ids_are_unique():
    ids = [s["id"] for s in PIPELINE_REGISTRY]
    assert len(ids) == len(set(ids)), "Duplicate pipeline IDs found"


def test_pipeline_registry_tables_are_lists():
    for src in PIPELINE_REGISTRY:
        assert isinstance(src["tables"], list), f"Source {src['id']} tables must be list"


# ── _staleness_seconds ─────────────────────────────────────────────────────────


def test_staleness_seconds_none_input():
    assert _staleness_seconds(None) is None


def test_staleness_seconds_valid_iso():
    past = datetime.now(UTC).isoformat()
    secs = _staleness_seconds(past)
    assert secs is not None
    assert secs >= 0


def test_staleness_seconds_invalid_iso():
    # malformed timestamp returns None
    result = _staleness_seconds("not-a-date")
    assert result is None


# ── _staleness_label ───────────────────────────────────────────────────────────


def test_staleness_label_none():
    assert _staleness_label(None) == "نامشخص"


def test_staleness_label_fresh():
    assert _staleness_label(60) == "تازه"


def test_staleness_label_minutes():
    label = _staleness_label(600)
    assert "دقیقه" in label


def test_staleness_label_hours():
    label = _staleness_label(7200)
    assert "ساعت" in label


def test_staleness_label_days():
    label = _staleness_label(172800)
    assert "روز" in label


# ── _get_redis_queue_depths ────────────────────────────────────────────────────


def test_get_redis_queue_depths_no_redis():
    """When Redis is unavailable, returns zeros without raising."""
    async def _run():
        with patch("apps.api.endpoints.data_admin.get_cache", side_effect=Exception("no redis")):
            # patching is inside data_admin; import the patched path
            pass
        return await _get_redis_queue_depths()

    # Patch core.cache.get_cache which is imported inside the function
    with patch("core.cache.get_cache", side_effect=Exception("no redis")):
        result = asyncio.run(_get_redis_queue_depths())
    assert result == {"queue": 0, "dead_letter": 0}


def test_get_redis_queue_depths_with_redis():
    client = AsyncMock()
    client.llen = AsyncMock(side_effect=[5, 2])
    cache = SimpleNamespace(client=client)

    with patch("core.cache.get_cache", return_value=cache):
        result = asyncio.run(_get_redis_queue_depths())

    assert result["queue"] == 5
    assert result["dead_letter"] == 2


# ── _get_job_stats_24h ─────────────────────────────────────────────────────────


def test_get_job_stats_24h_success():
    row = (20, 15, 3, 2)
    result_obj = MagicMock()
    result_obj.fetchone.return_value = row
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    stats = asyncio.run(_get_job_stats_24h(session))

    assert stats["total"] == 20
    assert stats["success"] == 15
    assert stats["failed"] == 3
    assert stats["running"] == 2


def test_get_job_stats_24h_db_failure():
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=Exception("DB down"))

    stats = asyncio.run(_get_job_stats_24h(session))

    assert stats == {"total": 0, "success": 0, "failed": 0, "running": 0}


# ── _get_recent_failures ────────────────────────────────────────────────────────


def test_get_recent_failures_empty():
    result_obj = MagicMock()
    result_obj.fetchall.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    failures = asyncio.run(_get_recent_failures(session, limit=5))
    assert failures == []


def test_get_recent_failures_with_data():
    dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    result_obj = MagicMock()
    result_obj.fetchall.return_value = [
        ("SyncQuotesJob", "Connection refused", dt, 5.5),
    ]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    failures = asyncio.run(_get_recent_failures(session, limit=5))
    assert len(failures) == 1
    assert failures[0]["job_type"] == "SyncQuotesJob"
    assert failures[0]["error"] == "Connection refused"
    assert failures[0]["duration_seconds"] == 5.5


def test_get_recent_failures_truncates_error():
    result_obj = MagicMock()
    long_error = "x" * 500
    result_obj.fetchall.return_value = [("Job", long_error, None, 0)]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    failures = asyncio.run(_get_recent_failures(session))
    assert len(failures[0]["error"]) <= 200


# ── _get_last_job_runs ─────────────────────────────────────────────────────────


def test_get_last_job_runs_empty():
    result_obj = MagicMock()
    result_obj.fetchall.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    runs = asyncio.run(_get_last_job_runs(session))
    assert runs == {}


def test_get_last_job_runs_with_data():
    dt = datetime(2026, 11, 1, tzinfo=UTC)
    result_obj = MagicMock()
    result_obj.fetchall.return_value = [
        ("SyncQuotesJob", "success", dt, 3.0, None),
        ("SyncCodalJob", "failed", dt, 10.0, "timeout"),
    ]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    runs = asyncio.run(_get_last_job_runs(session))
    assert "SyncQuotesJob" in runs
    assert runs["SyncQuotesJob"]["status"] == "success"
    assert "SyncCodalJob" in runs
    assert runs["SyncCodalJob"]["error"] == "timeout"


# ── _get_table_row_estimates ────────────────────────────────────────────────────


def test_get_table_row_estimates_success():
    result_obj = MagicMock()
    result_obj.fetchall.return_value = [("instruments", 50000), ("quotes", 1000000)]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    estimates = asyncio.run(_get_table_row_estimates(session))
    assert estimates["instruments"] == 50000
    assert estimates["quotes"] == 1000000


def test_get_table_row_estimates_db_failure():
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=Exception("DB error"))

    estimates = asyncio.run(_get_table_row_estimates(session))
    assert estimates == {}


# ── data_overview endpoint ─────────────────────────────────────────────────────


def test_data_overview_returns_success_structure():
    """data_overview should return a valid ApiResponse with expected keys."""
    # Minimal stubs — the real endpoint uses helpers that have their own tests
    session = AsyncMock()

    # job stats row
    stats_row = (10, 8, 1, 1)
    # row estimates
    estimates_rows = [("instruments", 1000), ("quotes", 500000)]
    # recent failures (empty)
    empty_rows: list = []

    mock_results = [
        # _get_job_stats_24h
        MagicMock(**{"fetchone.return_value": stats_row}),
        # _get_table_row_estimates
        MagicMock(**{"fetchall.return_value": estimates_rows}),
        # _get_recent_failures
        MagicMock(**{"fetchall.return_value": empty_rows}),
    ]
    call_count = 0

    async def mock_execute(query, params=None):
        nonlocal call_count
        result = mock_results[min(call_count, len(mock_results) - 1)]
        call_count += 1
        return result

    session.execute = mock_execute

    with (
        patch("core.cache.get_cache", side_effect=Exception("no redis")),
    ):
        resp = asyncio.run(data_overview(session=session))

    assert resp.success is True
    assert resp.data is not None
    assert "overall_status" in resp.data
    assert "jobs_24h" in resp.data
    assert "queue" in resp.data
    assert "storage" in resp.data
    assert "recent_failures" in resp.data
    assert "failure_rate_24h" in resp.data


def test_data_overview_overall_status_ok_when_no_failures():
    session = AsyncMock()
    no_failures_row = (10, 10, 0, 0)
    estimates_rows: list = []
    empty_rows: list = []

    results_iter = iter([
        MagicMock(**{"fetchone.return_value": no_failures_row}),
        MagicMock(**{"fetchall.return_value": estimates_rows}),
        MagicMock(**{"fetchall.return_value": empty_rows}),
    ])

    async def mock_execute(query, params=None):
        return next(results_iter, MagicMock(**{"fetchall.return_value": [], "fetchone.return_value": None}))

    session.execute = mock_execute

    client = AsyncMock()
    client.llen = AsyncMock(side_effect=[0, 0])
    cache = SimpleNamespace(client=client)

    with patch("core.cache.get_cache", return_value=cache):
        resp = asyncio.run(data_overview(session=session))

    assert resp.success is True
    assert resp.data["overall_status"] == "ok"


# ── data_sources endpoint ──────────────────────────────────────────────────────


def test_data_sources_returns_all_pipeline_sources():
    result_obj = MagicMock()
    result_obj.fetchall.return_value = []  # no last runs
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    resp = asyncio.run(data_sources(session=session))

    assert resp.success is True
    assert len(resp.data["sources"]) == len(PIPELINE_REGISTRY)
    assert "categories" in resp.data


def test_data_sources_enriches_with_last_run():
    dt = datetime(2026, 11, 1, tzinfo=UTC)
    result_obj = MagicMock()
    result_obj.fetchall.return_value = [
        ("SyncQuotesJob", "success", dt, 2.5, None),
    ]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    resp = asyncio.run(data_sources(session=session))

    assert resp.success is True
    quotes_src = next((s for s in resp.data["sources"] if s["job_name"] == "SyncQuotesJob"), None)
    assert quotes_src is not None
    assert quotes_src["last_run"] is not None
    assert quotes_src["pipeline_status"] == "ok"


def test_data_sources_marks_unknown_when_no_history():
    result_obj = MagicMock()
    result_obj.fetchall.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    resp = asyncio.run(data_sources(session=session))

    for src in resp.data["sources"]:
        if src["job_name"] != "BrsApi registry jobs":
            assert src["pipeline_status"] == "unknown"
            assert src["last_run"] is None


# ── table_freshness endpoint ───────────────────────────────────────────────────


def test_table_freshness_handles_missing_tables():
    """When a table is missing, it should return None gracefully."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=Exception("relation does not exist"))

    resp = asyncio.run(table_freshness(session=session))

    assert resp.success is True
    # All entries have latest_ts=None (errors were suppressed)
    for entry in resp.data["tables"]:
        assert entry["latest_ts"] is None


def test_table_freshness_returns_all_monitored_tables():
    result_obj = MagicMock()
    result_obj.scalar.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    resp = asyncio.run(table_freshness(session=session))

    assert resp.success is True
    assert len(resp.data["tables"]) == len(_FRESHNESS_COLUMNS)
    for entry in resp.data["tables"]:
        assert "table" in entry
        assert "staleness_label" in entry
        assert "freshness_column" in entry


def test_table_freshness_with_valid_timestamp():
    dt = datetime(2026, 11, 17, 10, 0, 0, tzinfo=UTC)
    result_obj = MagicMock()
    result_obj.scalar.return_value = dt
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    resp = asyncio.run(table_freshness(session=session))

    assert resp.success is True
    for entry in resp.data["tables"]:
        assert entry["latest_ts"] is not None
        assert entry["staleness_seconds"] is not None
        assert entry["staleness_seconds"] >= 0

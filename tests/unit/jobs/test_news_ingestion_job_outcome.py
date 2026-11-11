"""A dead news feed must not be reported as a successful zero-row run.

Audit SCH-05. ``NewsIngestionJob`` ignored ``fetch_error``/``errors`` and always
returned success, so a provider outage looked like a healthy "0 saved" cycle on
every dashboard that watches job outcomes.
"""

from __future__ import annotations

import pytest

from jobs.definitions import news_jobs
from jobs.job_context import JobContext


def _context() -> JobContext:
    return JobContext(job_id="job-1", job_name="NewsIngestionJob")


def _patch_ingest(monkeypatch: pytest.MonkeyPatch, stats: dict) -> None:
    class _FakeService:
        def __init__(self, session=None) -> None:
            self.session = session

        async def ingest(self, **_kwargs):
            return dict(stats)

    def _session_factory():
        async def _gen():
            yield object()

        return _gen()

    monkeypatch.setattr(news_jobs, "get_session", _session_factory)
    monkeypatch.setattr(news_jobs, "NewsIngestionService", _FakeService)


async def test_dead_feeds_fail_the_job(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_ingest(
        monkeypatch,
        {"saved": 0, "fetched": 0, "errors": 1, "fetch_error": "all feeds timed out"},
    )

    result = await news_jobs.NewsIngestionJob().execute(_context())

    assert result.success is False
    assert "fetch failed" in result.error


async def test_save_errors_without_progress_fail_the_job(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_ingest(monkeypatch, {"saved": 0, "fetched": 5, "errors": 5, "fetch_error": ""})

    result = await news_jobs.NewsIngestionJob().execute(_context())

    assert result.success is False


async def test_partial_fetch_still_counts_as_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    """One dead feed must not hide the rows the healthy feeds delivered."""
    _patch_ingest(
        monkeypatch,
        {"saved": 3, "fetched": 10, "errors": 1, "fetch_error": "one feed blocked"},
    )

    result = await news_jobs.NewsIngestionJob().execute(_context())

    assert result.success is True
    assert result.data["saved"] == 3
    assert result.data["fetch_error"] == "one feed blocked"


async def test_clean_run_reports_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_ingest(monkeypatch, {"saved": 7, "fetched": 9, "errors": 0, "fetch_error": ""})

    result = await news_jobs.NewsIngestionJob().execute(_context())

    assert result.success is True
    assert result.data["saved"] == 7

"""The two placeholder news entrypoints must not report success.

``orchestration.news_flow.NewsFlow`` and ``jobs.news_sync.NewsSyncJob`` do no
work, yet both returned ``{"status": "completed"}`` — any future wiring would
report a healthy ingestion that never happened. The scheduled, real path is
``jobs.definitions.news_jobs.NewsIngestionJob``.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_news_flow_placeholder_fails_closed() -> None:
    from orchestration.news_flow import NewsFlow

    result = await NewsFlow().run(context=None)

    assert result.success is False
    assert "not_implemented" in (result.error or "")


@pytest.mark.asyncio
async def test_news_sync_job_placeholder_fails_closed() -> None:
    from jobs.news_sync import NewsSyncJob

    result = await NewsSyncJob().execute(payload={})

    assert result.success is False
    assert "not_implemented" in (result.error or "")

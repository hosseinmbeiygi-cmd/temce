from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class NewsSyncJob:
    """Placeholder — NOT implemented.

    Superseded by ``jobs.definitions.news_jobs.NewsIngestionJob`` (the wired
    job). This stub used to answer ``{"status": "completed", "records": 0}``,
    which reads as a healthy sync that found nothing; it fails closed instead.
    """

    async def execute(self, payload: dict[str, Any]) -> Result[dict[str, Any]]:
        logger.error("NewsSyncJob.execute called but the sync job is not implemented")
        return Result.fail(
            "not_implemented: NewsSyncJob is a placeholder; use "
            "jobs.definitions.news_jobs.NewsIngestionJob"
        )

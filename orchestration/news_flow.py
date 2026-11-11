from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class NewsFlow:
    """Placeholder — NOT implemented.

    The real, scheduled ingestion path is
    ``jobs.definitions.news_jobs.NewsIngestionJob`` over
    ``services.news_ingestion.NewsIngestionService``. Answering
    ``{"status": "completed"}`` (as this stub used to) reported a finished flow
    for work that never ran, so it fails closed instead.
    """

    async def run(self, context: Any) -> Result[dict[str, Any]]:
        logger.error("NewsFlow.run called but the orchestration flow is not implemented")
        return Result.fail(
            "not_implemented: NewsFlow is a placeholder; scheduled news ingestion is "
            "jobs.definitions.news_jobs.NewsIngestionJob"
        )

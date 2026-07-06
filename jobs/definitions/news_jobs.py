from __future__ import annotations

from core.database import get_session
from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.news_ingestion import NewsIngestionService

logger = get_logger(__name__)


class NewsIngestionJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        sources = context.get_param("sources", None)
        limit = context.get_param("limit", 50)
        saved = 0
        fetched = 0
        session_obtained = False
        async for session in get_session():
            session_obtained = True
            service = NewsIngestionService(session=session)
            stats = await service.ingest(
                sources=sources,
                limit_per_source=limit,
                save=True,
                verbose=False,
            )
            saved = stats.get("saved", 0)
            fetched = stats.get("fetched", 0)
        # commit() fires AFTER the async for loop completes naturally
        if not session_obtained:
            return JobResult.failure("Could not obtain DB session", job_name=self.name)
        return JobResult.success_result(
            job_name=self.name,
            data={"saved": saved, "fetched": fetched},
        )


class NewsSentimentJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        return JobResult.success_result(job_name=self.name, data={"analyzed": 0})

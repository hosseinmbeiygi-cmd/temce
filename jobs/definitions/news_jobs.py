from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.news_service import NewsService

logger = get_logger(__name__)


class NewsIngestionJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        sources = context.get_param("sources", ["rss", "api"])
        limit = context.get_param("limit", 100)
        service = NewsService()
        count = 0
        for source in sources:
            result = await service.ingest_news(source=source, limit=limit)
            if result.success:
                count += result.data.get("count", 0)
        return JobResult.success_result(job_name=self.name, data={"ingested": count})


class NewsSentimentJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        news_ids = context.get_param("news_ids", [])
        service = NewsService()
        count = 0
        for news_id in news_ids:
            result = await service.analyze_sentiment(news_id)
            if result.success:
                count += 1
        return JobResult.success_result(job_name=self.name, data={"analyzed": count})

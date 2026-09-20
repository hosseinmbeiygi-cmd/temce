from __future__ import annotations

from core.database import get_session
from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.news_ingestion import NewsIngestionService
from services.news_sentiment_pipeline import NewsSentimentPipeline

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
    """امتیازدهی NLP سنتیمنت اخبار — عمومی + اختصاصی نماد (تب ۶)."""

    async def execute(self, context: JobContext) -> JobResult:
        batch_size = context.get_param("batch_size", 200)
        force = bool(context.get_param("force", False))
        session_obtained = False
        stats: dict[str, int] = {}
        async for session in get_session():
            session_obtained = True
            pipeline = NewsSentimentPipeline(session=session)
            stats = await pipeline.run(batch_size=batch_size, force=force)
        if not session_obtained:
            return JobResult.failure("Could not obtain DB session", job_name=self.name)
        return JobResult.success_result(job_name=self.name, data=stats)


class NewsSourceHealthJob(BaseJob):
    """هشدار منبع مرده — منابع RSS با last_fetched_at قدیمی‌تر از آستانه.

    Runs right after each ingestion in the scheduler; a Telegram alert
    fires (with cooldown) only when stale/never-fetched/unregistered
    sources exist. Disabled entirely when NEWS_SOURCE_STALE_MINUTES=0.
    """

    async def execute(self, context: JobContext) -> JobResult:
        from core.config import settings
        from services.news_source_health import NewsSourceHealthService

        if settings.news_source_stale_minutes <= 0:
            return JobResult.success_result(
                job_name=self.name, data={"status": "disabled"}
            )
        session_obtained = False
        alerted = False
        summary: dict = {}
        async for session in get_session():
            session_obtained = True
            service = NewsSourceHealthService(session)
            report = await service.notify_if_degraded()
            if report is not None:
                alerted = True
                summary = report.get("summary", {})
        if not session_obtained:
            return JobResult.failure("Could not obtain DB session", job_name=self.name)
        return JobResult.success_result(
            job_name=self.name,
            data={"alerted": alerted, **summary},
        )


class NewsReadPathHalterJob(BaseJob):
    """Auto-halt برای rollout کاناری مسیر خواندن اخبار.

    هر پنجره پاریتی را می‌سنجد؛ اگر نرخ تطابق legacy vs news_items زیر
    ``NEWS_READ_PARITY_FLOOR_PERCENT`` برود (با حداقل نمونه لازم)، حالت
    را به ``off`` برمی‌گرداند (Redis halt key که همه workerها می‌خوانند).
    با ``NEWS_READ_HALT_ENABLED=false`` غیرفعال می‌شود.
    """

    async def execute(self, context: JobContext) -> JobResult:
        from services.news_read_canary import evaluate_auto_halt

        result = await evaluate_auto_halt()
        return JobResult.success_result(job_name=self.name, data=result)

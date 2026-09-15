from __future__ import annotations

import contextlib

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.codal_service import CodalService

logger = get_logger(__name__)


class CodalIngestionJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        symbols = context.get_param("symbols", [])
        from_date = context.get_param("from_date", "")
        to_date = context.get_param("to_date", "")
        service = CodalService()
        count = 0
        for symbol in symbols:
            result = await service.ingest_codal(symbol, from_date=from_date, to_date=to_date)
            if result.success:
                count += 1
        return JobResult.success_result(job_name=self.name, data={"processed": count})


class CodalSyncJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        days_back = context.get_param("days_back", 7)
        service = CodalService()
        result = await service.sync_recent(days_back=days_back)
        if result.success:
            return JobResult.success_result(job_name=self.name, data=result.data)
        return JobResult.failure(result.error, job_name=self.name)


class CodalAttachmentDownloadJob(BaseJob):
    """Download Codal announcement attachments (PDF/Excel/HTML) for backfill."""

    async def execute(self, context: JobContext) -> JobResult:
        from sqlalchemy.ext.asyncio import AsyncSession

        from services.codal_attachment_service import CodalAttachmentDownloadService

        limit = context.get_param("limit", 1000)
        symbol = context.get_param("symbol", None)
        storage_type = context.get_param("storage_type", "local")
        concurrency = context.get_param("concurrency", 3)
        delay_seconds = context.get_param("delay_seconds", 1.0)

        session: AsyncSession | None = None
        owns_session = False
        try:
            # Jobs are expected to receive a session via context; fall back to creating one.
            session = context.get_param("session")
            if session is None:
                from core.database import async_session_factory

                session = async_session_factory()
                owns_session = True

            service = CodalAttachmentDownloadService(
                session,
                storage_type=storage_type,
                concurrency=concurrency,
                delay_seconds=delay_seconds,
            )
            summary = await service.download_all_pending(limit=limit, symbol=symbol)
            await service.close()

            return JobResult.success_result(
                job_name=self.name,
                data={
                    "total": summary.total,
                    "downloaded": summary.downloaded,
                    "skipped": summary.skipped,
                    "failed": summary.failed,
                    "errors": summary.errors[:50],
                },
            )
        except Exception as exc:
            logger.exception("CodalAttachmentDownloadJob failed")
            return JobResult.failure(str(exc), job_name=self.name)
        finally:
            if owns_session and session is not None:
                with contextlib.suppress(Exception):
                    await session.close()

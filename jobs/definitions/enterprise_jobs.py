"""🌙 Enterprise Overnight Jobs — موتور ساعات غیربازاری.

بخش ۱.۱ معماری Enterprise سهام:
  - ``IndicatorPrecomputeJob``: محاسبه اندیکاتورهای کل بازار و upsert به
    stock_indicators_snapshot (خواندن فرانت از DB زیر ۵۰ms).
  - ``MonthlySalesFillJob``: واکشی اکسل اطلاعیه‌های ماهانه کدال، پارس و
    fill جدول stock_monthly_sales_production با MoM/YoY.

هر دو job idempotent هستند و در صورت اجرای تکراری هزینه صفر دارند.
"""

from __future__ import annotations

from core.database import get_session
from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.indicator_precompute_service import IndicatorPrecomputeService
from services.monthly_sales_ingestion import MonthlySalesIngestionService

logger = get_logger(__name__)


class IndicatorPrecomputeJob(BaseJob):
    """Precompute اندیکاتورهای روزانه کل بازار (شبانه، batch-based)."""

    async def execute(self, context: JobContext) -> JobResult:
        batch_limit = int(context.get_param("batch_limit", 400))
        symbol = context.get_param("symbol", None)
        session_obtained = False
        stats: dict[str, int] = {}
        async for session in get_session():
            session_obtained = True
            service = IndicatorPrecomputeService(session)
            stats = await service.run(batch_limit=batch_limit, symbol=symbol)
        if not session_obtained:
            return JobResult.failure("Could not obtain DB session", job_name=self.name)
        logger.info("IndicatorPrecomputeJob done: %s", stats)
        return JobResult.success_result(job_name=self.name, data=stats)


class MonthlySalesFillJob(BaseJob):
    """Fill گزارش فروش ماهانه کدال از اکسل رسمی (شبانه)."""

    async def execute(self, context: JobContext) -> JobResult:
        limit = int(context.get_param("limit", 100))
        symbol = context.get_param("symbol", None)
        session_obtained = False
        summary_dict: dict[str, int] = {}
        async for session in get_session():
            session_obtained = True
            service = MonthlySalesIngestionService(session)
            try:
                summary = await service.run(limit=limit, symbol=symbol)
                summary_dict = {
                    "processed": summary.processed,
                    "parsed_rows": summary.parsed_rows,
                    "upserted": summary.upserted,
                    "all_time_highs": summary.all_time_highs,
                    "skipped": summary.skipped,
                    "errors": summary.errors,
                }
            finally:
                await service.close()
        if not session_obtained:
            return JobResult.failure("Could not obtain DB session", job_name=self.name)
        logger.info("MonthlySalesFillJob done: %s", summary_dict)
        return JobResult.success_result(job_name=self.name, data=summary_dict)


__all__ = ["IndicatorPrecomputeJob", "MonthlySalesFillJob"]

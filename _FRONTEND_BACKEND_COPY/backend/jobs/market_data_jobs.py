from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.quote_service import QuoteService

logger = get_logger(__name__)


class QuoteIngestionJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        symbols = context.get_param("symbols", [])
        source = context.get_param("source", "tsetmc")

        service = QuoteService()
        count = 0
        errors: list[str] = []

        for symbol in symbols:
            try:
                result = await service.ingest_realtime(symbol, source=source)

                if result.success:
                    count += 1
                else:
                    errors.append(f"{symbol}: {result.error}")

            except Exception as exc:  # noqa: BLE001
                logger.exception("Realtime quote ingestion failed for symbol=%s", symbol)
                errors.append(f"{symbol}: {exc}")

        return JobResult.success_result(
            job_name=self.name,
            data={
                "ingested": count,
                "symbols": len(symbols),
                "source": source,
                "errors": errors,
            },
        )


class HistoricalDataJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        symbols = context.get_param("symbols", [])
        start_date = context.get_param("start_date", "")
        end_date = context.get_param("end_date", "")

        service = QuoteService()
        count = 0
        errors: list[str] = []

        for symbol in symbols:
            try:
                result = await service.ingest_historical(
                    symbol,
                    start_date=start_date,
                    end_date=end_date,
                )

                if result.success:
                    count += 1
                else:
                    errors.append(f"{symbol}: {result.error}")

            except Exception as exc:  # noqa: BLE001
                logger.exception("Historical quote ingestion failed for symbol=%s", symbol)
                errors.append(f"{symbol}: {exc}")

        return JobResult.success_result(
            job_name=self.name,
            data={
                "processed": count,
                "symbols": len(symbols),
                "start_date": start_date,
                "end_date": end_date,
                "errors": errors,
            },
        )


class RealtimeQuoteJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        symbols = context.get_param("symbols", [])

        service = QuoteService()
        results = []
        errors: list[str] = []

        for symbol in symbols:
            try:
                result = await service.get_realtime(symbol)

                if result.success:
                    results.append(result.value)
                else:
                    errors.append(f"{symbol}: {result.error}")

            except Exception as exc:  # noqa: BLE001
                logger.exception("Realtime quote fetch failed for symbol=%s", symbol)
                errors.append(f"{symbol}: {exc}")

        return JobResult.success_result(
            job_name=self.name,
            data={
                "quotes": len(results),
                "symbols": len(symbols),
                "errors": errors,
            },
        )

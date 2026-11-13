"""
Feature Store nightly jobs
==========================

  * ``FeatureStoreBuildJob``      — rebuilds ``ml_engineered_features``
                                    (nightly, after the symbol-detail refresh)
  * ``ScreenerDailyScoresJob``    — writes the daily ``screener_daily_scores``
                                    snapshot with market/industry ranks

Both wrap the standalone scripts so the same logic runs under the job
dispatcher (queue mode → worker, or in-process dev mode).
"""

from __future__ import annotations

from datetime import date

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


class FeatureStoreBuildJob(BaseJob):
    """Nightly: compute engineered features for all active symbols."""

    async def execute(self, context: JobContext) -> JobResult:
        from core.database import get_session
        from scripts.build_feature_store import FeatureStoreBuilder

        days = int(context.get_param("days", 100))
        workers = int(context.get_param("workers", 4))
        symbols = context.get_param("symbols", None)

        try:
            # NOTE: do NOT return inside this `async for` loop — get_session()
            # commits only when the generator is resumed after the yield.
            result: JobResult | None = None
            async for _session in get_session():
                builder = FeatureStoreBuilder(symbols=symbols, days=days, workers=workers)
                stats = await builder.build_all()
                result = JobResult.success_result(
                    job_name=self._name,
                    data=stats,
                    message=f"Feature store: {stats['rows']} rows, {stats['fail']} failed",
                )
            if result is None:
                return JobResult.failure("Could not obtain DB session", job_name=self._name)
            return result
        except Exception as e:  # noqa: BLE001
            logger.exception("FeatureStoreBuildJob failed")
            return JobResult.failure(str(e), job_name=self._name)


class ScreenerDailyScoresJob(BaseJob):
    """Nightly: snapshot daily 110-column scores with ranks."""

    async def execute(self, context: JobContext) -> JobResult:
        from core.database import get_session
        from scripts.build_screener_scores import build_daily_scores

        date_str = context.get_param("date", None)
        trade_date = date.fromisoformat(date_str) if date_str else date.today()

        try:
            # NOTE: do NOT return inside this `async for` loop — get_session()
            # commits only when the generator is resumed after the yield.
            result: JobResult | None = None
            async for session in get_session():
                stats = await build_daily_scores(session, trade_date)
                result = JobResult.success_result(
                    job_name=self._name,
                    data=stats,
                    message=f"Screener daily scores: {stats['rows']} rows for {stats['trade_date']}",
                )
            if result is None:
                return JobResult.failure("Could not obtain DB session", job_name=self._name)
            return result
        except Exception as e:  # noqa: BLE001
            logger.exception("ScreenerDailyScoresJob failed")
            return JobResult.failure(str(e), job_name=self._name)

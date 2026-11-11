"""Gold options derivatives jobs (STEP 5-FIX-2).

* ``GoldOptionIvSnapshotJob`` — stores today's per-contract implied
  volatility in ``gold_option_iv_history`` (idempotent per
  ``(symbol, as_of, strike)``), the series behind ``iv_rank`` /
  ``iv_percentile`` on the options chain.
"""

from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.definitions.gold_macro_jobs import _with_session
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


class GoldOptionIvSnapshotJob(BaseJob):
    """Daily per-contract IV snapshot for the IME options chain."""

    async def execute(self, context: JobContext) -> JobResult:
        from services.gold.options_chain_service import snapshot_option_iv

        async def run(session) -> JobResult:
            counts = await snapshot_option_iv(session)
            logger.info("GoldOptionIvSnapshotJob: %s", counts)
            return JobResult.success_result(job_name=self._name, data=counts)

        return await _with_session(self._name, run)


__all__ = ["GoldOptionIvSnapshotJob"]

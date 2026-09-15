"""
BrsApi key-readiness probe job.

Runs every hour (registered in ``apps/scheduler/app.py``) and sends a
single live request to BrsApi to detect when the server-side usage counter
has reset (HTTP 200 instead of the 302 heavy-file redirect). On the
not-ready -> ready transition it notifies (Telegram if configured, else a
loud log line) so the operator knows to set ``BRSAPI_ENABLED=true`` and run
the backlog sync.

Budget: 1 request per run → 24/day worst case, negligible against the
4,000/day cap, and the probe never follows redirects or retries.

Concurrency: in queue mode (multi-replica) this job is executed by a worker
through ``JobDispatcher.dispatch``, whose distributed Redis lock ensures only
one replica runs it at a time — the state-file read-modify-write is not
atomic across processes, so the dispatcher lock is the guard against
duplicate notifications.
"""

from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


class BrsApiReadyCheckJob(BaseJob):
    """Hourly probe that watches for the BrsApi key becoming usable again."""

    def __init__(self, name: str = "BrsApiReadyCheckJob") -> None:
        super().__init__(name=name)

    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.readiness import check_and_notify

        try:
            summary = await check_and_notify()
            return JobResult.success_result(
                job_name=self._name,
                data=summary,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("BrsApi readiness probe failed")
            return JobResult.failure(str(exc), job_name=self._name)

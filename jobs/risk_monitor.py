from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


class RiskMonitorCheckJob(BaseJob):
    """Scheduled job that runs LiveRiskMonitorService.check_all() every 5 minutes during market hours."""

    def __init__(self) -> None:
        super().__init__(name="risk_monitor_check")

    async def execute(self, context: JobContext) -> JobResult:
        from services.live_risk_monitor import LiveRiskMonitorService

        try:
            monitor = LiveRiskMonitorService()
            results = await monitor.check_all()

            triggered = [r for r in results if r.triggered]
            logger.info(
                "Risk check complete: %d rules checked, %d triggered",
                len(results),
                len(triggered),
            )

            return JobResult.success_result(
                job_name=self.name,
                data={
                    "total_checks": len(results),
                    "triggered": len(triggered),
                    "details": [
                        {"rule": r.rule, "triggered": r.triggered, "details": r.details}
                        for r in results
                    ],
                },
            )
        except Exception as e:
            logger.error("Risk monitor check failed: %s", e)
            return JobResult.failure(str(e), job_name=self.name)

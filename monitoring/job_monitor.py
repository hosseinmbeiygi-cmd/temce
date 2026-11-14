from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# ponytail: in-process ring buffer, so history is lost on restart and not
# shared across workers. Move to a `job_runs` table when cross-restart
# failure-rate trends are needed.
MAX_RUNS = 1000


class JobMonitor:
    def __init__(self, maxlen: int = MAX_RUNS) -> None:
        self._runs: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._dead_queue_length: int = 0

    def record_run(self, job_name: str, status: str, duration_s: float, error: str | None = None) -> None:
        self._runs.append(
            {
                "job_name": job_name,
                "status": status,
                "duration_s": duration_s,
                "error": error,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    def failure_rate(self, job_name: str, window: int = 50) -> float:
        relevant = [r for r in self._runs if r["job_name"] == job_name][-window:]
        if not relevant:
            return 0.0
        failures = sum(1 for r in relevant if r["status"] == "failed")
        return failures / len(relevant)

    def avg_duration(self, job_name: str) -> float:
        relevant = [r for r in self._runs if r["job_name"] == job_name]
        if not relevant:
            return 0.0
        return sum(r["duration_s"] for r in relevant) / len(relevant)

    async def check_dead_queue(self) -> int:
        """Return the number of jobs in the job:dead dead-letter queue.

        Logs a WARNING when dead jobs are present so alerting picks it up.
        Returns 0 (fail-open) when Redis is unreachable so callers never crash.
        """
        from core.config import settings

        # Same key the queue consumer writes to (JOB_QUEUE_DEAD_LETTER).
        key = settings.job_queue_dead_letter
        try:
            from core.cache import get_cache

            client = get_cache().client
            if client is None:
                return 0
            length = int(await client.llen(key) or 0)
            self._dead_queue_length = length
            if length:
                logger.warning(
                    "%s dead-letter queue contains %d unprocessed job(s)",
                    key,
                    length,
                )
            return length
        except Exception:
            logger.exception("Failed to query %s dead-letter queue", key)
            return 0

    def report(self) -> dict[str, Any]:
        jobs = {r["job_name"] for r in self._runs}
        return {
            "jobs": {
                job: {
                    "total_runs": sum(1 for r in self._runs if r["job_name"] == job),
                    "failure_rate": self.failure_rate(job),
                    "avg_duration_s": self.avg_duration(job),
                }
                for job in jobs
            },
            "dead_queue_length": self._dead_queue_length,
        }

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class JobMonitor:
    def __init__(self) -> None:
        self._runs: list[dict[str, Any]] = []

    def record_run(self, job_name: str, status: str, duration_s: float, error: str | None = None) -> None:
        self._runs.append(
            {
                "job_name": job_name,
                "status": status,
                "duration_s": duration_s,
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
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

    def report(self) -> dict[str, Any]:
        jobs = {r["job_name"] for r in self._runs}
        return {
            job: {
                "total_runs": sum(1 for r in self._runs if r["job_name"] == job),
                "failure_rate": self.failure_rate(job),
                "avg_duration_s": self.avg_duration(job),
            }
            for job in jobs
        }

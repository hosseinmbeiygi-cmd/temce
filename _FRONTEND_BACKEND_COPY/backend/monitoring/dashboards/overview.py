from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from monitoring.health import health_checker
from monitoring.metrics.service import metrics_service

logger = get_logger(__name__)


class OverviewDashboard:
    def __init__(self) -> None:
        self._active_jobs: list[dict[str, Any]] = []

    def register_job(self, job_name: str, status: str, started_at: datetime | None = None) -> None:
        self._active_jobs.append(
            {
                "name": job_name,
                "status": status,
                "started_at": (started_at or datetime.now(UTC)).isoformat(),
            }
        )

    def deregister_job(self, job_name: str) -> None:
        self._active_jobs = [j for j in self._active_jobs if j["name"] != job_name]

    def get_market_summary(self) -> dict[str, Any]:
        dashboard_data = metrics_service.get_dashboard_data()
        api_requests = sum(v for k, v in dashboard_data["counters"].items() if k.startswith("api.requests."))
        api_errors = dashboard_data["counters"].get("api_errors", 0)
        api_server_errors = dashboard_data["counters"].get("api.server_errors", 0)
        job_failures = dashboard_data["counters"].get("jobs.failures", 0)
        provider_failures = sum(v for k, v in dashboard_data["counters"].items() if k.startswith("providers.failures."))
        error_rate = (api_errors / api_requests * 100) if api_requests > 0 else 0.0
        return {
            "total_api_requests": api_requests,
            "api_errors": api_errors,
            "api_server_errors": api_server_errors,
            "error_rate_percent": round(error_rate, 2),
            "job_failures": job_failures,
            "provider_failures": provider_failures,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def get_system_health(self) -> dict[str, Any]:
        health_status = health_checker.get_overall_status()
        components = health_checker._results
        return {
            "overall_status": health_status.value,
            "components": {name: status.value for name, status in components.items()},
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def get_active_jobs(self) -> dict[str, Any]:
        return {
            "jobs": list(self._active_jobs),
            "count": len(self._active_jobs),
            "timestamp": datetime.now(UTC).isoformat(),
        }


overview_dashboard = OverviewDashboard()

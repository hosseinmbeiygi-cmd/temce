from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from monitoring.metrics.collector import MetricsCollector, metrics_collector

logger = get_logger(__name__)


class MetricsService:
    def __init__(self, collector: MetricsCollector | None = None) -> None:
        self._collector = collector or metrics_collector

    def record_api_request(self, endpoint: str, method: str, status_code: int, duration_ms: float) -> None:
        tags = f"{method}:{endpoint}:{status_code}"
        self._collector.increment(f"api.requests.{tags}")
        self._collector.observe("api.request_duration_ms", duration_ms)
        if status_code >= 400:
            self._collector.increment("api.errors")
        if status_code >= 500:
            self._collector.increment("api.server_errors")

    def record_job_execution(self, job_name: str, status: str, duration_ms: float) -> None:
        self._collector.increment(f"jobs.executions.{job_name}.{status}")
        self._collector.observe(f"jobs.duration_ms.{job_name}", duration_ms)
        if status == "failed":
            self._collector.increment("jobs.failures")
        logger.info(
            "Job %s completed with status %s in %.2fms",
            job_name,
            status,
            duration_ms,
        )

    def record_provider_call(self, provider_name: str, success: bool, duration_ms: float) -> None:
        result = "success" if success else "failure"
        self._collector.increment(f"providers.calls.{provider_name}.{result}")
        self._collector.observe(f"providers.duration_ms.{provider_name}", duration_ms)
        if not success:
            self._collector.increment(f"providers.failures.{provider_name}")

    def record_data_freshness(self, entity_type: str, last_update: datetime) -> None:
        now = datetime.now(UTC)
        age_seconds = (now - last_update).total_seconds()
        self._collector.gauge(f"data.freshness_age_seconds.{entity_type}", age_seconds)

    def record_ml_prediction(self, model_id: str, latency_ms: float) -> None:
        self._collector.increment(f"ml.predictions.{model_id}")
        self._collector.observe(f"ml.prediction_latency_ms.{model_id}", latency_ms)

    def get_dashboard_data(self) -> dict[str, Any]:
        snapshot = self._collector.snapshot()
        return {
            "counters": snapshot["counters"],
            "gauges": snapshot["gauges"],
            "histograms": snapshot["histograms"],
            "timestamp": snapshot["timestamp"],
        }


metrics_service = MetricsService()

"""Phase 0 migration-health dashboard: BrsApi budget + dead-letter SLO.

Exposes the two migration SLOs defined in ADR-0001:
  - brsapi_blocked_total  (target: ~0/day; circuit-breaker trips counted)
  - job_dead_total       (target: < 10/day, else page)

 ponytail: ceiling = in-process MetricsCollector, no Prometheus text format
 here. Upgrade path: emit real Counter/Gauge via
 integrations.observability.prometheus_exporter when exporters gain labels.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from monitoring.metrics.collector import metrics_collector

logger = get_logger(__name__)

# SLO budget from ADR-0001 (Phase 0 baseline; tune per-domain in Phase 3)
JOB_DEAD_DAILY_BUDGET = 10
BRSAPI_BLOCK_DAILY_BUDGET = 3


class MigrationHealthDashboard:
    def record_brsapi_blocked(self, reason: str = "302") -> None:
        metrics_collector.increment(f"brsapi.blocked.{reason}")
        metrics_collector.increment("brsapi_blocked_total")
        logger.warning("BrsApi blocked (%s) — budget governor should trip", reason)

    def record_brsapi_circuit_open(self) -> None:
        metrics_collector.increment("brsapi.circuit_open_total")

    def record_brsapi_budget(self, used: int, daily_limit: int = 4000) -> None:
        metrics_collector.gauge("brsapi.budget_used_today", used)
        metrics_collector.gauge("brsapi.budget_remaining", daily_limit - used)

    def record_job_dead(self, job_name: str) -> None:
        metrics_collector.increment("job_dead_total")
        metrics_collector.increment(f"job.dead.{job_name}")
        logger.error("Job %s dead-lettered", job_name)

    def get_health(self) -> dict[str, Any]:
        counters = metrics_collector.snapshot()["counters"]
        dead = counters.get("job_dead_total", 0)
        blocked = counters.get("brsapi_blocked_total", 0)
        return {
            "brsapi_blocked_total": blocked,
            "brsapi_block_over_budget": blocked > BRSAPI_BLOCK_DAILY_BUDGET,
            "job_dead_total": dead,
            "job_dead_over_budget": dead > JOB_DEAD_DAILY_BUDGET,
            "brsapi_circuit_open_total": counters.get("brsapi.circuit_open_total", 0),
            "timestamp": datetime.now(UTC).isoformat(),
        }


migration_health_dashboard = MigrationHealthDashboard()

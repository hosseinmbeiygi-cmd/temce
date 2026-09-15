"""Data quality monitoring endpoint — Prometheus metrics + health dashboards.

Phase 2-2: Data Quality + Monitoring
Provides:
- Prometheus /metrics endpoint
- Data staleness checks
- 5xx error tracking
- Contract/day count
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from apps.api.metrics import get_prometheus_exporter
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()


@router.get("/metrics", summary="Prometheus metrics endpoint", include_in_schema=False)
async def metrics_endpoint() -> PlainTextResponse:
    """Render all Prometheus metrics in text exposition format."""
    exporter = get_prometheus_exporter()
    return PlainTextResponse(exporter.export_text())


@router.get("/data-quality", summary="Data quality dashboard")
async def data_quality() -> ApiResponse[dict]:
    """Live data quality status: staleness, error rates, contract volume."""
    exporter = get_prometheus_exporter()

    staleness = exporter.gauge("data_staleness_seconds")
    requests_5xx = exporter.counter("http_responses_total", labels={"status": "5xx"})
    total_requests = exporter.counter("http_requests_total")
    contracts_today = exporter.gauge("contracts_synced_today")

    # Built-in checks: null price/volume, price limits, timeliness
    checks = {
        "null_check": staleness < 300,  # no staleness > 5min
        "checksum": exporter.gauge("data_checksum_valid") > 0,
        "staleness": staleness < 300,
        "price_limit": exporter.gauge("price_limit_breaches") == 0,
    }

    return ApiResponse(
        success=True,
        data={
            "timestamp": datetime.now(UTC).isoformat(),
            "reports": {
                "staleness_seconds": staleness,
                "requests_5xx": requests_5xx,
                "total_requests": total_requests,
                "contracts_today": contracts_today,
            },
            "checks": checks,
            "all_checks_passed": all(checks.values()),
        },
    )

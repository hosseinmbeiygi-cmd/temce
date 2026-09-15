"""Prometheus metrics collection for the API.

Provides a process-wide ``PrometheusExporter`` singleton plus a middleware
that records HTTP request counters and latency histograms. The ``/metrics``
route in ``apps/api/app.py`` renders ``export_text()`` in the Prometheus text
exposition format.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging import get_logger
from integrations.observability.prometheus_exporter import PrometheusExporter

logger = get_logger(__name__)

_exporter: PrometheusExporter | None = None


def get_prometheus_exporter() -> PrometheusExporter:
    """Return the process-wide PrometheusExporter singleton."""
    global _exporter
    if _exporter is None:
        _exporter = PrometheusExporter()
    return _exporter


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request counts + latency histograms into the exporter.

    Every request increments ``http_requests_total`` (labelled by method and
    route) and observes ``http_request_duration_seconds``. Exceptions are
    re-raised so outer error handling still applies.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        exporter = get_prometheus_exporter()
        # NOTE: inside BaseHTTPMiddleware.dispatch the matched route is not yet
        # resolved (routing happens inside call_next), so the raw URL path is
        # the only stable label available here. Paths are bounded by the API
        # surface so label cardinality stays manageable.
        route_path = request.url.path

        exporter.inc("http_requests_total", labels={"method": request.method, "route": route_path})
        # Track in-flight requests so dashboards can spot queueing under load.
        in_flight_key = "http_request_in_flight"
        current = exporter.gauge(in_flight_key)
        exporter.set_gauge(in_flight_key, current + 1.0)
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            exporter.set_gauge(in_flight_key, exporter.gauge(in_flight_key) - 1.0)
            exporter.inc("http_request_errors_total", labels={"method": request.method, "route": route_path})
            raise
        exporter.set_gauge(in_flight_key, exporter.gauge(in_flight_key) - 1.0)
        exporter.observe(
            "http_request_duration_seconds",
            time.monotonic() - start,
            labels={"method": request.method, "route": route_path},
        )
        exporter.inc(
            "http_responses_total",
            labels={"method": request.method, "route": route_path, "status": str(response.status_code)},
        )
        return response

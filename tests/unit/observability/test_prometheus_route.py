"""``/metrics`` route and Prometheus-valid exposition tests."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from httpx import AsyncClient
from prometheus_client.parser import text_string_to_metric_families

from apps.api.metrics import MetricsMiddleware, get_prometheus_exporter
from integrations.observability.prometheus_exporter import PrometheusExporter


def _mini_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(MetricsMiddleware)

    @app.get("/api/v1/items/{item_id}")
    async def item(item_id: str) -> dict[str, str]:
        return {"id": item_id}

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        payload = get_prometheus_exporter().export_prometheus()
        return PlainTextResponse(
            f"{payload}\n" if payload else "",
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


def _families(text: str) -> dict[str, Any]:
    return {family.name: family for family in text_string_to_metric_families(text)}


class TestExposition:
    def test_output_is_parseable_prometheus_text(self) -> None:
        exporter = PrometheusExporter()
        exporter.inc("http_requests_total", {"method": "GET", "route": "/api/v1/x"})
        exporter.inc("http_requests_total", {"method": "POST", "route": "/api/v1/x"})
        exporter.set_gauge("http_request_in_flight", 3)
        exporter.observe("http_request_duration_seconds", 0.05, {"method": "GET", "route": "/api/v1/x"})

        text = exporter.export_prometheus()
        families = _families(text)

        # prometheus_client strips the _total suffix for counters.
        assert {"http_requests", "http_request_in_flight", "http_request_duration_seconds"} <= set(families)
        assert 'method="GET"' in text
        assert "method=GET" not in text

    def test_help_and_type_once_per_family(self) -> None:
        exporter = PrometheusExporter()
        for route in ("/a", "/b", "/c"):
            exporter.inc("http_requests_total", {"method": "GET", "route": route})

        text = exporter.export_prometheus()
        assert text.count("# HELP http_requests_total") == 1
        assert text.count("# TYPE http_requests_total") == 1
        assert text.count("http_requests_total{") == 3

    def test_label_values_are_escaped(self) -> None:
        exporter = PrometheusExporter()
        exporter.inc("custom_total", {"path": 'a"b\\c'})

        text = exporter.export_prometheus()
        assert 'path="a\\"b\\\\c"' in text
        families = _families(text)
        # prometheus_client strips the _total suffix for counter families.
        assert "custom" in families
        assert families["custom"].samples[0].name == "custom_total"

    def test_histogram_series_are_complete(self) -> None:
        exporter = PrometheusExporter()
        exporter.observe("latency_seconds", 0.05, {"route": "/a"})
        exporter.observe("latency_seconds", 0.2, {"route": "/a"})

        text = exporter.export_prometheus()
        assert 'latency_seconds_bucket{le="0.05",route="/a"} 1' in text
        assert 'latency_seconds_bucket{le="+Inf",route="/a"} 2' in text
        assert 'latency_seconds_count{route="/a"} 2' in text
        assert "latency_seconds_sum{" in text


class TestMetricsMiddleware:
    def test_labels_use_route_template_not_raw_path(self) -> None:
        exporter = get_prometheus_exporter()
        exporter.reset()
        client = TestClient(_mini_app(), raise_server_exceptions=False)

        client.get("/api/v1/items/1")
        client.get("/api/v1/items/2")

        text = exporter.export_prometheus()
        assert 'route="/api/v1/items/{item_id}"' in text
        assert 'route="/api/v1/items/1"' not in text
        assert 'http_requests_total{method="GET",route="/api/v1/items/{item_id}"} 2.0' in text

    def test_metrics_scrape_is_not_counted(self) -> None:
        exporter = get_prometheus_exporter()
        exporter.reset()
        client = TestClient(_mini_app(), raise_server_exceptions=False)

        assert client.get("/metrics").status_code == 200
        assert 'route="/metrics"' not in exporter.export_prometheus()

    def test_unmatched_paths_collapse_to_one_series(self) -> None:
        exporter = get_prometheus_exporter()
        exporter.reset()
        client = TestClient(_mini_app(), raise_server_exceptions=False)

        client.get("/nope/1")
        client.get("/nope/2")

        text = exporter.export_prometheus()
        assert 'route="<unmatched>"' in text
        assert 'route="/nope/1"' not in text


class TestAppRoute:
    async def test_app_exposes_valid_metrics_route(self, client: AsyncClient) -> None:
        exporter = get_prometheus_exporter()
        exporter.reset()
        exporter.inc("http_requests_total", {"method": "GET", "route": "/api/v1/signals"})

        response = await client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
        assert 'http_requests_total{method="GET",route="/api/v1/signals"} 1.0' in response.text
        assert 'route="/metrics"' not in response.text
        assert _families(response.text)

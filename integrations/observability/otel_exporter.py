from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class OTelExporter:
    def __init__(self, service_name: str = "iran-market-platform", endpoint: str | None = None):
        self._service_name = service_name
        self._endpoint = endpoint or settings.otlp_endpoint
        self._provider: TracerProvider | None = None
        self._tracer = trace.get_tracer(service_name)

    def setup(self) -> None:
        if not self._endpoint:
            logger.warning("OTLP endpoint not configured, skipping OTel setup")
            return
        resource = Resource.create({"service.name": self._service_name, "service.version": settings.api_version})
        self._provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=self._endpoint, insecure=True)
        self._provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(self._provider)
        logger.info("OpenTelemetry exporter configured for %s", self._endpoint)

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> trace.Span:
        span = self._tracer.start_span(name)
        if attributes:
            span.set_attributes(attributes)
        return span

    async def shutdown(self) -> None:
        if self._provider:
            self._provider.shutdown()

    @property
    def tracer(self) -> trace.Tracer:
        return self._tracer

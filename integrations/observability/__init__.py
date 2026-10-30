"""Observability adapters: structured logging, error reporting, Prometheus, OTel.

The OTel exporter (and its gRPC/protobuf baggage) is only needed when tracing is
actually configured.  Importing ``prometheus_exporter`` used to pull it in
through this package's eager imports, adding ~1s to every API boot.  Names are
resolved on first access instead (PEP 562).
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from integrations.observability.error_reporter import ErrorReporter
    from integrations.observability.otel_exporter import OTelExporter
    from integrations.observability.prometheus_exporter import PrometheusExporter
    from integrations.observability.structured_logger import StructuredLogger

__all__ = ["OTelExporter", "PrometheusExporter", "StructuredLogger", "ErrorReporter"]

_EXPORTS = {
    "OTelExporter": "integrations.observability.otel_exporter",
    "PrometheusExporter": "integrations.observability.prometheus_exporter",
    "StructuredLogger": "integrations.observability.structured_logger",
    "ErrorReporter": "integrations.observability.error_reporter",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

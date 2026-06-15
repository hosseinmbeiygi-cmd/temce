from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class AlertType(StrEnum):
    HEALTH = "health"
    METRIC = "metric"
    DRIFT = "drift"
    FRESHNESS = "freshness"
    JOB = "job"
    ERROR = "error"


class MetricGroup(StrEnum):
    SYSTEM = "system"
    BUSINESS = "business"
    PROVIDER = "provider"
    PIPELINE = "pipeline"
    ML = "ml"


SERVICE_NAMES = [
    "api",
    "admin",
    "worker",
    "scheduler",
    "market_data",
    "codal",
    "news",
    "macro",
    "funds",
    "ml_training",
    "ml_inference",
    "backtesting",
]

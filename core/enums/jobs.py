from __future__ import annotations

from enum import StrEnum


class JobType(StrEnum):
    DATA_INGESTION = "data_ingestion"
    MODEL_TRAINING = "model_training"
    MODEL_INFERENCE = "model_inference"
    BACKTEST = "backtest"
    REPORT_GENERATION = "report_generation"
    DATA_EXPORT = "data_export"
    DATA_CLEANUP = "data_cleanup"
    HEALTH_CHECK = "health_check"
    SYNC = "sync"
    MAINTENANCE = "maintenance"


class JobPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class JobTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"
    DEPENDENCY = "dependency"

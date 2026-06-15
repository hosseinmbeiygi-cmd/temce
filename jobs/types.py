from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JobPayload:
    job_name: str
    params: dict[str, Any] = field(default_factory=dict)
    scheduled_at: datetime | None = None
    correlation_id: str = ""


@dataclass
class JobResult:
    success: bool
    data: Any = None
    error: str | None = None
    duration_s: float = 0.0


@dataclass
class RetrySpec:
    max_attempts: int = 3
    base_delay_s: float = 5.0
    backoff_multiplier: float = 2.0


@dataclass
class ScheduleSpec:
    cron: str = ""
    interval_seconds: int = 0
    timezone: str = "Asia/Tehran"

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class JobContext:
    job_id: str
    job_name: str
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    user_id: str = ""
    retry_count: int = 0
    max_retries: int = 3

    def get_param(self, key: str, default: Any = None) -> Any:
        return self.params.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def record_start(self) -> None:
        self.started_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "params": self.params,
            "metadata": self.metadata,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

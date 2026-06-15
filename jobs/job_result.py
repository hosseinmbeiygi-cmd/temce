from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class JobResult:
    success: bool
    job_name: str = ""
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float = 0.0

    @classmethod
    def success_result(cls, job_name: str = "", data: dict[str, Any] | None = None, message: str = "") -> JobResult:
        now = datetime.now(UTC)
        return cls(
            success=True,
            job_name=job_name,
            message=message or "Completed",
            data=data or {},
            started_at=now,
            completed_at=now,
        )

    @classmethod
    def failure(cls, error: str, job_name: str = "") -> JobResult:
        now = datetime.now(UTC)
        return cls(success=False, job_name=job_name, message="Failed", error=error, started_at=now, completed_at=now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "job_name": self.job_name,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }

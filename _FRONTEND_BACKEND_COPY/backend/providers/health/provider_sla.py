from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ProviderSLA:
    def __init__(self, name: str, target_uptime: float = 99.5) -> None:
        self.name = name
        self.target_uptime = target_uptime
        self._start_time = datetime.now(UTC)
        self._downtime_seconds: float = 0.0
        self._last_down: datetime | None = None

    def record_downtime(self) -> None:
        if self._last_down is None:
            self._last_down = datetime.now(UTC)

    def record_uptime(self) -> None:
        if self._last_down is not None:
            self._downtime_seconds += (datetime.now(UTC) - self._last_down).total_seconds()
            self._last_down = None

    def current_uptime_pct(self) -> float:
        elapsed = (datetime.now(UTC) - self._start_time).total_seconds()
        if elapsed == 0:
            return 100.0
        uptime = elapsed - self._downtime_seconds
        return (uptime / elapsed) * 100.0

    def is_meeting_sla(self) -> bool:
        return self.current_uptime_pct() >= self.target_uptime

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_uptime": self.target_uptime,
            "current_uptime_pct": self.current_uptime_pct(),
            "meeting_sla": self.is_meeting_sla(),
            "downtime_seconds": self._downtime_seconds,
        }

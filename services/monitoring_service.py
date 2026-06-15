from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class MonitoringService:
    async def get_health(self) -> Result[dict[str, Any]]:
        return Result.ok({"status": "ok"})

    async def get_metrics(self) -> Result[dict[str, Any]]:
        return Result.ok({})

    async def get_alerts(self) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def get_dashboard(self) -> Result[dict[str, Any]]:
        return Result.ok({})

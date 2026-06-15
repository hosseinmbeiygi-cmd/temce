from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class FundSyncJob:
    async def execute(self, payload: dict[str, Any]) -> Result[dict[str, Any]]:
        logger.info("Fund sync job started")
        return Result.ok({"status": "completed", "records": 0})

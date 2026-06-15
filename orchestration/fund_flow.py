from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class FundFlow:
    async def run(self, context: Any) -> Result[dict[str, Any]]:
        logger.info("Fund flow started")
        return Result.ok({"status": "completed"})

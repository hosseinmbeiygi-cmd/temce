from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class FundFlow:
    """Placeholder - NOT implemented.

    The real fund ingestion path runs through the scheduled jobs/services. This
    stub used to answer ``{"status": "completed"}`` for work that never ran, so it
    fails closed instead.
    """

    async def run(self, context: Any) -> Result[dict[str, Any]]:
        logger.error("FundFlow.run called but the orchestration flow is not implemented")
        return Result.fail(
            "not_implemented: FundFlow is a placeholder; real fund ingestion runs via "
            "the scheduled jobs/services, not this orchestration stub"
        )

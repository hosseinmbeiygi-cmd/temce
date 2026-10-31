from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class CodalFlow:
    """Placeholder - NOT implemented.

    The real codal ingestion path runs through the scheduled jobs/services. This
    stub used to answer ``{"status": "completed"}`` for work that never ran, so it
    fails closed instead.
    """

    async def run(self, context: Any) -> Result[dict[str, Any]]:
        logger.error("CodalFlow.run called but the orchestration flow is not implemented")
        return Result.fail(
            "not_implemented: CodalFlow is a placeholder; real codal ingestion runs via "
            "the scheduled jobs/services, not this orchestration stub"
        )

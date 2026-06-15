from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ErrorPolicy:
    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries

    def should_retry(self, attempt: int, error: Exception) -> bool:
        if attempt >= self.max_retries:
            logger.warning("Max retries reached: %d", attempt)
            return False
        return True

    def handle_failure(self, job_name: str, error: Exception, attempt: int) -> str:
        logger.error("Job %s failed (attempt %d): %s", job_name, attempt, error)
        if attempt >= self.max_retries:
            return "dead_letter"
        return "retry"

    def handle_dead_letter(self, job_name: str, payload: dict[str, Any], error: Exception) -> None:
        logger.error("Job %s moved to dead letter queue: %s", job_name, error)

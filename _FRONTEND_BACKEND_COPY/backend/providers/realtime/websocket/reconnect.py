from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ReconnectPolicy:
    def __init__(
        self, max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 60.0, backoff: float = 2.0
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff = backoff

    async def execute(self, connect_fn: Callable[[], Any]) -> bool:
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await connect_fn()
                if result:
                    logger.info("Reconnected successfully after %d attempts", attempt)
                    return True
            except Exception as e:
                logger.warning("Reconnect attempt %d failed: %s", attempt, e)
            if attempt < self.max_retries:
                delay = min(self.base_delay * (self.backoff ** (attempt - 1)), self.max_delay)
                await asyncio.sleep(delay)
        logger.error("All %d reconnect attempts failed", self.max_retries)
        return False

from __future__ import annotations

import asyncio
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


class RSSClient(HttpClient):
    """HTTP client specialized for fetching RSS/Atom feeds."""

    def __init__(self, retry_attempts: int = 2, retry_delay: float = 1.0) -> None:
        super().__init__(timeout=15)
        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay

    async def fetch_feed(self, url: str) -> Result[str]:
        """Fetch an RSS/Atom feed from a URL with retry support.

        Returns Result.ok with the raw XML text, or Result.fail on error.
        """
        last_error: str = ""
        for attempt in range(self._retry_attempts + 1):
            if attempt > 0:
                logger.info("Retrying RSS fetch %s (attempt %d/%d)", url, attempt, self._retry_attempts)
                await asyncio.sleep(self._retry_delay * attempt)
            result = await self.get(url)
            if result.success:
                if result.value is None:
                    return Result.fail("Empty response from RSS feed")
                if hasattr(result.value, "text"):
                    return Result.ok(result.value.text)
                return Result.ok(str(result.value))
            last_error = result.error or "Unknown error"
            logger.warning("RSS fetch failed for %s: %s", url, last_error)
        return Result.fail(f"Failed to fetch RSS feed after {self._retry_attempts + 1} attempts: {last_error}")

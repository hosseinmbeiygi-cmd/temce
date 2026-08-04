from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class RetentionManager:
    """
    Deletes storage objects older than a per-pattern retention period.

    Works with any storage exposing ``iter_files`` + ``stat`` (returns a
    Result containing ``{"modified": mtime, "size": bytes}``) + ``delete``.
    """

    def __init__(self, storage: Any):
        self._storage = storage
        self._rules: dict[str, int] = {}

    def add_rule(self, pattern: str, retention_days: int) -> None:
        self._rules[pattern] = retention_days
        logger.info("Retention rule added: %s -> %d days", pattern, retention_days)

    def remove_rule(self, pattern: str) -> None:
        self._rules.pop(pattern, None)

    async def apply_rules(self) -> dict[str, int]:
        results: dict[str, int] = {}
        for pattern, days in self._rules.items():
            deleted = await self._apply_pattern(pattern, days)
            results[pattern] = deleted
        return results

    async def _apply_pattern(self, pattern: str, retention_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        cutoff_ts = cutoff.timestamp()
        deleted = 0
        async for filepath in self._storage.iter_files(pattern=pattern):
            try:
                stat = await self._storage.stat(filepath)
                if not stat.success:
                    logger.debug("Cannot stat %s: %s", filepath, stat.error)
                    continue
                modified = (stat.value or {}).get("modified")
                if modified is None:
                    logger.debug("No mtime for %s — skipping", filepath)
                    continue
                if modified < cutoff_ts:
                    result = await self._storage.delete(filepath)
                    if result.success:
                        deleted += 1
            except Exception as e:
                logger.warning("Failed to process file %s during retention: %s", filepath, e)
                continue
        logger.info("Retention: deleted %d files matching %s", deleted, pattern)
        return deleted

    async def apply_for_pattern(self, pattern: str) -> int:
        days = self._rules.get(pattern)
        if days is None:
            return 0
        return await self._apply_pattern(pattern, days)

    def get_rules(self) -> dict[str, int]:
        return dict(self._rules)

    def clear_rules(self) -> None:
        self._rules.clear()

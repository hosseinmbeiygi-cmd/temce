from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ReplayEngine:
    def __init__(self, lake: Any, parser_registry: Any, storage: Any) -> None:
        self._lake = lake
        self._parsers = parser_registry
        self._storage = storage

    async def replay_source(
        self,
        source: str,
        date_prefix: str | None = None,
        chunk_size: int = 1000,
    ) -> dict[str, Any]:
        objects = await self._lake.list_raw(source, date_prefix=date_prefix)
        total = len(objects)
        success = 0
        failed = 0

        for i in range(0, total, chunk_size):
            chunk = objects[i : i + chunk_size]
            for obj_key in chunk:
                try:
                    raw = await self._lake.get_raw(obj_key)
                    if raw is None:
                        failed += 1
                        continue

                    parser = self._parsers.find_by_source(source)
                    if parser is None:
                        logger.warning("No parser found for source: %s", source)
                        failed += 1
                        continue

                    events = await parser.parse(raw)
                    for event in events:
                        event.raw_object_key = obj_key
                        event.parsed_at = datetime.now(UTC).isoformat()
                    success += 1
                except Exception:
                    logger.exception("Replay failed for object: %s", obj_key)
                    failed += 1

        return {
            "source": source,
            "total_objects": total,
            "replayed": success,
            "failed": failed,
        }

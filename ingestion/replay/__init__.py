from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ReplayEngine:
    def __init__(
        self,
        lake: Any,
        parser_registry: Any,
        storage: Any,
        identity_resolver: Any | None = None,
    ) -> None:
        self._lake = lake
        self._parsers = parser_registry
        self._storage = storage
        self._identity = identity_resolver

    async def replay_source(
        self,
        source: str,
        date_prefix: str | None = None,
        chunk_size: int = 1000,
    ) -> dict[str, Any]:
        objects = await self._lake.list_raw(source, date_prefix=date_prefix)
        total = len(objects)
        objects_ok = 0
        objects_failed = 0
        events_written = 0

        for i in range(0, total, chunk_size):
            chunk = objects[i : i + chunk_size]
            for obj_key in chunk:
                try:
                    raw = await self._lake.get_raw(obj_key)
                    if raw is None:
                        objects_failed += 1
                        continue

                    parser = self._parsers.find_by_source(source)
                    if parser is None:
                        logger.warning("No parser found for source: %s", source)
                        objects_failed += 1
                        continue

                    events = await parser.parse(raw)
                    now = datetime.now(UTC).isoformat()
                    for event in events:
                        event.raw_object_key = obj_key
                        event.parsed_at = now
                        written = await self._write_event(event)
                        events_written += written

                    objects_ok += 1
                except Exception:
                    logger.exception("Replay failed for object: %s", obj_key)
                    objects_failed += 1

        return {
            "source": source,
            "total_objects": total,
            "objects_replayed": objects_ok,
            "objects_failed": objects_failed,
            "events_written": events_written,
        }

    async def _write_event(self, event: Any) -> int:
        """Resolve identity and persist one parsed event. Returns 1 on success, 0 otherwise."""
        if self._storage is None:
            return 0

        ins_id: str | None = None
        if self._identity is not None:
            ins_id = await self._identity.resolve(
                source=event.source,
                external_id=event.data.get("instrument_id", ""),
                symbol=event.data.get("symbol"),
            )
            if not ins_id:
                logger.warning(
                    "Unresolved instrument for replay source=%s external_id=%r symbol=%r — skipping",
                    event.source,
                    event.data.get("instrument_id", ""),
                    event.data.get("symbol"),
                )
                return 0
        else:
            ins_id = event.data.get("instrument_id", "")
            if not ins_id:
                return 0

        try:
            event_type = event.event_type
            if event_type == "trade_tick":
                await self._storage.write_trade_tick(ins_id, event.data)
            elif event_type == "market_snapshot":
                await self._storage.write_market_snapshot(ins_id, event.data)
            elif event_type == "orderbook_level":
                await self._storage.write_orderbook_level(ins_id, event.data)
            elif event_type == "daily_ohlcv":
                await self._storage.write_daily_ohlcv(ins_id, event.data)
            else:
                logger.debug("Unknown event_type=%s — skipping write", event_type)
                return 0
        except Exception:
            logger.exception("Failed to write replay event type=%s ins_id=%s", event.event_type, ins_id)
            return 0

        return 1

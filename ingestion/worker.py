from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

from .config import IngestionConfig
from .http_client import HttpClient
from .lake import RawDataLake
from .parser import ParserRegistry
from .parser.errors import ParseError
from .sources.derivatives import TsetmcFutureSource, TsetmcOptionSource
from .sources.library_sources import FinpyTseSource, TehranStocksSource, TsetmcLibSource, TseUtilsSource
from .sources.tsetmc import TsetmcOrderBookSource, TsetmcTradeSource
from .storage.dedup import DeduplicationEngine

logger = get_logger(__name__)


class IngestionWorker:
    def __init__(
        self,
        config: IngestionConfig,
        http: HttpClient,
        lake: RawDataLake,
        parsers: ParserRegistry,
        dedup: DeduplicationEngine | None = None,
        identity_resolver: Any | None = None,
        storage: Any | None = None,
        instrument_source: Any | None = None,
    ) -> None:
        self._config = config
        self._http = http
        self._lake = lake
        self._parsers = parsers
        self._dedup = dedup
        self._identity = identity_resolver
        self._storage = storage
        self._instrument_source = instrument_source
        self._sources: dict[str, Any] = {}
        self._instrument_ids: list[str] = []
        self._instrument_refresh_interval = 3600
        self._last_instrument_refresh = 0.0

    def register_source(self, source: Any) -> None:
        self._sources[source.name] = source

    async def ingest_all(self) -> dict[str, int]:
        results: dict[str, int] = {}
        await self._refresh_instruments()

        for name, source in self._sources.items():
            try:
                if isinstance(source, (TsetmcTradeSource, TsetmcOrderBookSource,
                                       TsetmcOptionSource, TsetmcFutureSource)):
                    total = 0
                    for ins_id in self._instrument_ids:
                        ctx = {"instrument_id": ins_id}
                        count = await self._ingest_source(source, ctx)
                        total += count
                    results[name] = total
                elif isinstance(source, (FinpyTseSource,)):
                    # finpy-tse: fetch market watch on each tick
                    ctx_mw = {"data_type": "market_watch"}
                    count_mw = await self._ingest_source(source, ctx_mw)
                    results[name] = count_mw
                elif isinstance(source, (TsetmcLibSource,)):
                    # tsetmc lib: fetch a sample instrument if we have any
                    count = 0
                    if self._instrument_ids and len(self._instrument_ids) > 0:
                        symbol = str(self._instrument_ids[0])
                        count = await self._ingest_source(source, {"symbol": symbol, "data_type": "all"})
                    results[name] = count
                elif isinstance(source, (TehranStocksSource,)):
                    # tehran-stocks: fetch all stocks list
                    count = await self._ingest_source(source, {"data_type": "all_stocks"})
                    results[name] = count
                elif isinstance(source, (TseUtilsSource,)):
                    # tse-utils: fetch market overview
                    count = await self._ingest_source(source, {"data_type": "market_overview"})
                    results[name] = count
                else:
                    count = await self._ingest_source(source)
                    results[name] = count
            except Exception:
                logger.exception("Ingestion failed for source: %s", name)
                results[name] = -1
        return results

    async def _refresh_instruments(self) -> None:
        now = asyncio.get_event_loop().time()
        if self._instrument_source and (now - self._last_instrument_refresh > self._instrument_refresh_interval):
            try:
                self._instrument_ids = await self._instrument_source.get_instrument_ids()
                self._last_instrument_refresh = now
                logger.info("Loaded %d instruments", len(self._instrument_ids))
            except Exception:
                logger.exception("Failed to refresh instruments")

    async def _ingest_source(self, source: Any, context: dict[str, Any] | None = None) -> int:
        """Fetch, parse and persist one source.

        Returns the number of events that were **successfully written** to
        storage (not the number parsed). A payload is marked as seen in the
        dedup window only after every event in it has been written, so a
        partial write failure is retried instead of being silently dropped.
        """
        fetch_result = await source.fetch(context)
        if not fetch_result.payloads:
            return 0
        written = 0

        for payload in fetch_result.payloads:
            if self._dedup is not None:
                try:
                    if await self._dedup.is_duplicate(payload.source, payload.raw_data):
                        logger.debug("Skipping duplicate payload for source=%s", payload.source)
                        continue
                except Exception:
                    # A broken dedup backend must not stop ingestion.
                    logger.warning("Dedup check failed for source=%s", payload.source, exc_info=True)

            object_key = await self._lake.store_raw(
                source=payload.source,
                endpoint=payload.endpoint,
                data=payload.raw_data,
                content_type=payload.content_type,
                fetch_time=payload.fetch_time,
                metadata=payload.metadata,
            )

            parser = self._parsers.find(
                payload.source,
                payload.endpoint,
                payload.content_type,
            )
            if parser is None:
                logger.warning("No parser for source=%s endpoint=%s", payload.source, payload.endpoint)
                continue

            try:
                events = await parser.parse(payload.raw_data)
            except ParseError as exc:
                # A payload we could not read is a failed ingest, not an empty
                # one: the raw copy stays in the lake for replay, and
                # ``ingest_all`` records the source as failed (-1) instead of
                # reporting zero written events as if the source were healthy.
                logger.error(
                    "Parse failed for source=%s endpoint=%s reason=%s. Raw payload kept at %s",
                    payload.source,
                    payload.endpoint,
                    exc.reason,
                    object_key,
                )
                raise
            except Exception:
                logger.exception(
                    "Parse failed for source=%s endpoint=%s. Raw payload kept at %s",
                    payload.source,
                    payload.endpoint,
                    object_key,
                )
                continue

            payload_written_all = True
            for event in events:
                event.raw_object_key = object_key
                event.parsed_at = datetime.now(UTC).isoformat()

                if self._identity and self._storage:
                    ins_id = await self._identity.resolve(
                        source=event.source,
                        external_id=event.data.get("instrument_id", ""),
                        symbol=event.data.get("symbol"),
                    )
                    if not ins_id:
                        # The storage tables require a resolved instrument_id;
                        # writing None would fail on every retry forever.
                        logger.warning(
                            "Unresolved instrument for source=%s external_id=%r symbol=%r — skipping event",
                            event.source,
                            event.data.get("instrument_id", ""),
                            event.data.get("symbol"),
                        )
                        continue
                    event.data["instrument_id"] = ins_id

                if self._identity and self._storage:
                    try:
                        await self._write_event(event, ins_id)
                    except Exception:
                        logger.exception("Failed to write event for %s", ins_id)
                        # Do not mark the payload as seen: the next tick retries it.
                        payload_written_all = False
                        continue
                    written += 1

            # Only after the whole payload was written successfully.
            if self._dedup is not None and payload_written_all:
                try:
                    await self._dedup.mark_seen(payload.source, payload.raw_data)
                except Exception:
                    logger.warning("Failed to mark payload seen for source=%s", payload.source, exc_info=True)

        return written

    async def _write_event(self, event: Any, instrument_id: str) -> None:
        """Persist one parsed event; exceptions propagate to the caller."""
        if self._storage is None:
            return
        event_type = event.event_type
        if event_type == "trade_tick":
            await self._storage.write_trade_tick(instrument_id, event.data)
        elif event_type == "market_snapshot":
            await self._storage.write_market_snapshot(instrument_id, event.data)
        elif event_type == "orderbook_level":
            await self._storage.write_orderbook_level(instrument_id, event.data)
        elif event_type == "daily_ohlcv":
            await self._storage.write_daily_ohlcv(instrument_id, event.data)

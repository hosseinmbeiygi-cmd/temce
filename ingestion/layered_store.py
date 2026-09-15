"""Layered persistence for scanner output — Hot (Redis) then Warm (TimescaleDB).

Design:

* **Hot** — the latest quote per symbol plus a scan index in Redis, written
  first so realtime readers (``api`` scope) see fresh data even if the warm
  write is slow or down.
* **Warm** — the durable ``brsapi_symbol_snapshots`` hypertable, written
  through the existing :class:`brsapi.repositories.BulkUpsertRepository`
  (``(symbol, fetched_at)`` upsert) rather than a new table.

A warm-layer failure never discards the hot-layer write; the report carries
both outcomes so the caller can alert.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from core.logging import get_logger

from .cache import MarketDataCache

logger = get_logger(__name__)

# 30s cadence -> 3x TTL so a single missed scan does not blank the reader.
HOT_TTL_SECONDS = 90
HOT_NAMESPACE = "ingestion:hot"

# Fields the hot layer needs; ``raw_json`` and the deeper orderbook levels are
# warm-layer concerns and would bloat Redis.
_HOT_FIELDS: tuple[str, ...] = (
    "symbol",
    "ins_id",
    "name",
    "sector",
    "price_last",
    "price_close",
    "price_yesterday",
    "price_last_change_pct",
    "trade_volume",
    "trade_value",
    "trade_count",
    "base_volume",
    "market_value",
    "time",
)


@dataclass
class PersistReport:
    """Outcome of one layered write."""

    hot_written: int = 0
    warm_written: int = 0
    hot_error: str | None = None
    warm_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.hot_error is None and self.warm_error is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "hot_written": self.hot_written,
            "warm_written": self.warm_written,
            "hot_error": self.hot_error,
            "warm_error": self.warm_error,
            "ok": self.ok,
        }


class WarmSink(Protocol):
    """Durable sink for parsed AllSymbols rows."""

    async def write_batch(self, records: Sequence[Mapping[str, Any]]) -> int:
        """Persist rows and return the number written."""


class HotLayer:
    """Latest-per-symbol quote cache in Redis (in-process fallback)."""

    def __init__(
        self,
        redis_client: Any | None = None,
        *,
        cache: MarketDataCache | None = None,
        ttl_seconds: int = HOT_TTL_SECONDS,
    ) -> None:
        self._cache = cache or MarketDataCache(redis_client, namespace=HOT_NAMESPACE)
        self._ttl = ttl_seconds

    async def write_batch(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        fetched_at: datetime,
    ) -> int:
        written = 0
        symbols: list[str] = []
        for record in records:
            symbol = str(record.get("symbol") or "").strip()
            if not symbol:
                continue
            payload = {name: record.get(name) for name in _HOT_FIELDS}
            payload["fetched_at"] = fetched_at.isoformat()
            await self._cache.set_json(f"quote:{symbol}", payload, self._ttl)
            symbols.append(symbol)
            written += 1

        if symbols:
            await self._cache.set_json(
                "scan:latest",
                {
                    "fetched_at": fetched_at.isoformat(),
                    "count": written,
                    "symbols": symbols,
                },
                self._ttl,
            )
        return written

    async def get_quote(self, symbol: str) -> Any | None:
        """Read a single hot quote (used by api-side readers and tests)."""
        return await self._cache.get_json(f"quote:{symbol}")

    async def latest_scan(self) -> Any | None:
        return await self._cache.get_json("scan:latest")


class SymbolSnapshotWarmSink:
    """Warm sink writing to ``brsapi_symbol_snapshots`` via bulk upsert."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    async def write_batch(self, records: Sequence[Mapping[str, Any]]) -> int:
        if not records:
            return 0

        from brsapi.models.tsetmc import SymbolSnapshotModel
        from brsapi.repositories.base import BulkUpsertRepository

        rows = [dict(record) for record in records]
        async with self._session_factory() as session:
            repo = BulkUpsertRepository(session, SymbolSnapshotModel)
            written = await repo.bulk_insert(
                rows,
                on_conflict_update=True,
                conflict_target=["symbol", "fetched_at"],
            )
            await session.commit()
        return written


class LayeredStoragePipeline:
    """Write each scan to the hot layer, then to the warm sink."""

    def __init__(
        self,
        *,
        hot: HotLayer,
        warm: WarmSink | None = None,
    ) -> None:
        self._hot = hot
        self._warm = warm

    @property
    def hot(self) -> HotLayer:
        return self._hot

    async def persist(self, scan: Any) -> PersistReport:
        """Persist a :class:`~ingestion.symbol_scanner.ScanResult`."""
        report = PersistReport()
        records: Sequence[Mapping[str, Any]] = scan.records
        fetched_at = scan.fetched_at

        try:
            report.hot_written = await self._hot.write_batch(records, fetched_at=fetched_at)
        except Exception as exc:  # noqa: BLE001 - report, never raise
            report.hot_error = str(exc)
            logger.exception("Hot layer write failed")

        if self._warm is not None and records:
            try:
                report.warm_written = await self._warm.write_batch(records)
            except Exception as exc:  # noqa: BLE001 - hot data is already safe
                report.warm_error = str(exc)
                logger.exception("Warm layer write failed")

        return report


def build_pipeline(
    *,
    redis_client: Any | None = None,
    warm_sink: WarmSink | None = None,
) -> LayeredStoragePipeline:
    """Convenience factory used by the scanner service."""
    return LayeredStoragePipeline(hot=HotLayer(redis_client), warm=warm_sink)


async def persist_scan(
    pipeline: LayeredStoragePipeline,
    scan: Any,
    *,
    on_report: Callable[[PersistReport], Awaitable[None]] | None = None,
) -> PersistReport:
    """Persist a scan and optionally hand the report to a callback."""
    report = await pipeline.persist(scan)
    if on_report is not None:
        await on_report(report)
    return report

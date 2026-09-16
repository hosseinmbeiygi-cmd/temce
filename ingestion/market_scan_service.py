"""Wire the AllSymbols scanner to the layered store.

This is the ingestion-scope entrypoint: it owns lifecycle (Redis, HTTP client,
scanner loop) and exposes a ``status()`` snapshot for health endpoints.

The warm sink is injected (an ``async_sessionmaker`` factory) so this service
never imports a database module at import time and degrades to hot-only when
no durable sink is configured.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any

from core.logging import get_logger

from .brs_api_client import BrsApiIngestionClient
from .config import IngestionConfig
from .layered_store import (
    HotLayer,
    LayeredStoragePipeline,
    PersistReport,
    SymbolSnapshotWarmSink,
    WarmSink,
)
from .quotas import DEFAULT_QUOTA_PROFILE, QuotaProfile
from .symbol_scanner import AllSymbolsScanner, ScanCadence, ScanResult

logger = get_logger(__name__)


class MarketScanService:
    """Owns the scanner lifecycle and the layered write path."""

    def __init__(
        self,
        *,
        config: IngestionConfig | None = None,
        client: BrsApiIngestionClient | None = None,
        profile: QuotaProfile = DEFAULT_QUOTA_PROFILE,
        cadence: ScanCadence | None = None,
        redis_client: Any | None = None,
        session_factory: Callable[[], Any] | None = None,
        warm_sink: WarmSink | None = None,
        auto_connect_redis: bool = True,
    ) -> None:
        self._config = config or IngestionConfig()
        self._profile = profile
        self._cadence = cadence
        self._redis = redis_client
        self._redis_owned = False
        self._auto_connect_redis = auto_connect_redis
        self._client = client
        self._client_owned = client is None
        self._warm_sink = warm_sink or (
            SymbolSnapshotWarmSink(session_factory) if session_factory is not None else None
        )
        self._pipeline: LayeredStoragePipeline | None = None
        self._scanner: AllSymbolsScanner | None = None
        self._run_task: asyncio.Task[Any] | None = None
        self._last_report: PersistReport | None = None

    @property
    def scanner(self) -> AllSymbolsScanner | None:
        return self._scanner

    @property
    def pipeline(self) -> LayeredStoragePipeline | None:
        return self._pipeline

    async def _ensure_redis(self) -> Any | None:
        if self._redis is not None or not self._auto_connect_redis:
            return self._redis
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._config.redis_url,
                decode_responses=False,
            )
            self._redis_owned = True
        except Exception as exc:  # noqa: BLE001 - Redis is optional (fallback)
            logger.warning("Redis unavailable, hot layer uses in-process fallback: %s", exc)
            self._redis = None
        return self._redis

    async def start(self) -> None:
        await self._ensure_redis()
        if self._client is None:
            self._client = BrsApiIngestionClient(profile=self._profile)
        if self._client_owned:
            await self._client.start()
        self._pipeline = LayeredStoragePipeline(
            hot=HotLayer(self._redis),
            warm=self._warm_sink,
        )
        self._scanner = AllSymbolsScanner(
            self._client,
            cadence=self._cadence or ScanCadence(),
            session=self._scanner_session(),
            on_scan=self._handle_scan,
        )
        logger.info(
            "MarketScanService started (warm=%s)",
            self._warm_sink is not None,
        )

    def _scanner_session(self) -> Any:
        from .symbol_scanner import MarketSession

        return MarketSession.from_config(self._config)

    async def _handle_scan(self, scan: ScanResult) -> None:
        assert self._pipeline is not None
        self._last_report = await self._pipeline.persist(scan)
        if not self._last_report.ok:
            logger.warning("Persist report: %s", self._last_report.as_dict())

    async def scan_once(self) -> PersistReport | None:
        """Run exactly one scan + persist cycle."""
        if self._scanner is None:
            await self.start()
        assert self._scanner is not None
        result = await self._scanner.scan_once()
        if not result.success or result.value is None:
            return None
        await self._handle_scan(result.value)
        return self._last_report

    async def run(self) -> None:
        """Run the scanner loop in the background."""
        if self._scanner is None:
            await self.start()
        assert self._scanner is not None
        self._run_task = asyncio.create_task(self._scanner.run())

    async def stop(self) -> None:
        if self._scanner is not None:
            self._scanner.stop()
        if self._run_task is not None:
            self._run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._run_task
            self._run_task = None
        if self._client is not None and self._client_owned:
            await self._client.stop()
        if self._redis is not None and self._redis_owned:
            with contextlib.suppress(Exception):
                await self._redis.aclose()
            self._redis = None
        logger.info("MarketScanService stopped")

    async def status(self) -> dict[str, Any]:
        scanner = self._scanner
        payload: dict[str, Any] = {
            "running": self._run_task is not None and not self._run_task.done(),
            "warm_enabled": self._warm_sink is not None,
            "redis_enabled": self._redis is not None,
            "scans": scanner.scan_count if scanner else 0,
            "failures": scanner.failure_count if scanner else 0,
            "last_scan": scanner.last_result.as_dict() if scanner and scanner.last_result else None,
            "last_persist": self._last_report.as_dict() if self._last_report else None,
        }
        if self._client is not None:
            try:
                payload["health"] = await self._client.health()
            except Exception as exc:  # noqa: BLE001 - status must never raise
                payload["health"] = {"error": str(exc)}
        return payload


async def run_service(
    *,
    redis_client: Any | None = None,
    session_factory: Callable[[], Any] | None = None,
) -> None:
    """Blocking helper used by a process entrypoint."""
    service = MarketScanService(
        redis_client=redis_client,
        session_factory=session_factory,
    )
    await service.start()
    try:
        await service.run()
        while True:
            await asyncio.sleep(3600)
    finally:
        await service.stop()

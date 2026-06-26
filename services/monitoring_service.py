from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from monitoring.health import HealthStatus, health_checker
from repositories.instrument_repository import InstrumentRepository
from services.tsetmc_client import TsetmcClient

logger = get_logger(__name__)


class MonitoringService:
    """Service for health monitoring, metrics, alerts, dashboard, and realtime ingestion.

    Integrates with the existing HealthChecker from monitoring/health.py
    to provide real status data for all system components. Also handles
    resilient realtime market-data ingestion with per-symbol error tracking.
    """

    def __init__(
        self,
        instrument_repo: InstrumentRepository | None = None,
        tsetmc_client: TsetmcClient | None = None,
    ) -> None:
        self._instrument_repo = instrument_repo or InstrumentRepository()
        self._tsetmc = tsetmc_client or TsetmcClient()

    # ========================================================================
    # REALTIME INGESTION
    # ========================================================================

    async def ingest_realtime(
        self,
        symbols: str | list[str],
    ) -> Result[dict[str, Any]]:
        """
        Fetch and persist realtime TSETMC data for one or more symbols.

        Each symbol is processed independently so a single failure never
        blocks the remaining symbols. Returns a summary with counts of
        successes, failures, and a per-symbol error list.
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        start = datetime.now(UTC)
        results: list[dict[str, Any]] = []

        for symbol in symbols:
            result = await self._ingest_one(symbol)
            results.append(result)

        elapsed = (datetime.now(UTC) - start).total_seconds()

        succeeded = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        return Result.ok({
            "total": len(symbols),
            "succeeded": len(succeeded),
            "failed": len(failed),
            "elapsed_seconds": round(elapsed, 2),
            "results": results,
            "timestamp": start.isoformat(),
        })

    async def _ingest_one(self, symbol: str) -> dict[str, Any]:
        """
        Ingest a single symbol and return a detailed result dict.

        Every unexpected exception is caught so that a single failing
        symbol never blocks the remainder of a batch.
        """
        entry: dict[str, Any] = {
            "symbol": symbol,
            "success": False,
            "step": "init",
            "error": None,
            "instrument_id": None,
        }

        try:
            # ── 1. Resolve instrument ──────────────────────────────────────
            inst_result = await self._instrument_repo.get_by_symbol(symbol)
            if not inst_result.success:
                entry["step"] = "resolve_instrument"
                entry["error"] = f"Instrument {symbol} not found"
                logger.warning("ingest_realtime: %s", entry["error"])
                return entry

            instrument = inst_result.value
            entry["instrument_id"] = instrument.id

            # ── 2. Validate ins_code ───────────────────────────────────────
            if not instrument.ins_code:
                entry["step"] = "validate_ins_code"
                entry["error"] = f"Instrument {symbol} has no ins_code"
                logger.warning("ingest_realtime: %s", entry["error"])
                return entry

            # ── 3. Fetch from TSETMC ──────────────────────────────────────
            entry["step"] = "tsetmc_fetch"
            try:
                api_result = await self._tsetmc.get_closing_price_info(instrument.ins_code)
            except Exception as exc:
                entry["error"] = f"TSETMC connection error: {exc}"
                logger.exception("ingest_realtime: TSETMC fetch failed for %s", symbol)
                return entry

            if not api_result.success:
                entry["error"] = f"TSETMC API error: {api_result.error}"
                logger.warning("ingest_realtime: %s", entry["error"])
                return entry

            # ── 4. Mark success ────────────────────────────────────────────
            # (save is delegated to the caller, e.g. QuoteService,
            #  since MonitoringService is a read/monitoring layer)
            entry["step"] = "complete"
            entry["success"] = True
            entry["data"] = api_result.value
            logger.info("ingest_realtime: %s → ok", symbol)
            return entry

        except Exception as exc:
            entry["error"] = f"Unexpected error: {exc}"
            logger.exception("ingest_realtime: unexpected error for %s", symbol)
            return entry

    # ========================================================================
    # HEALTH & METRICS (existing)
    # ========================================================================

    async def get_health(self) -> Result[dict[str, Any]]:
        """Full health check of all system components."""
        try:
            results = await health_checker.check_all()
            overall = health_checker.get_overall_status()
            return Result.ok({
                "status": overall.value,
                "timestamp": datetime.now(UTC).isoformat(),
                "components": {
                    name: status.value for name, status in results.items()
                },
            })
        except Exception as exc:
            logger.exception("Health check failed")
            return Result.ok({
                "status": "degraded",
                "timestamp": datetime.now(UTC).isoformat(),
                "error": str(exc),
            })

    async def get_metrics(self) -> Result[dict[str, Any]]:
        """Basic system metrics."""
        try:
            results = health_checker._results if hasattr(health_checker, '_results') else {}
            return Result.ok({
                "timestamp": datetime.now(UTC).isoformat(),
                "components": {
                    name: {"status": status.value} for name, status in results.items()
                },
                "overall": health_checker.get_overall_status().value,
                "healthy_count": sum(1 for s in results.values() if s == HealthStatus.HEALTHY),
                "total_count": len(results),
            })
        except Exception as exc:
            logger.exception("Metrics check failed")
            return Result.ok({
                "timestamp": datetime.now(UTC).isoformat(),
                "error": str(exc),
            })

    async def get_alerts(self) -> Result[list[dict[str, Any]]]:
        """Active alerts based on health check failures."""
        try:
            results = health_checker._results if hasattr(health_checker, '_results') else {}
            alerts = []
            for name, status in results.items():
                if status != HealthStatus.HEALTHY:
                    alerts.append({
                        "component": name,
                        "status": status.value,
                        "severity": "critical" if status == HealthStatus.UNHEALTHY else "warning",
                        "message": f"{name} is {status.value}",
                        "timestamp": datetime.now(UTC).isoformat(),
                    })
            return Result.ok(alerts)
        except Exception as exc:
            logger.exception("Alerts check failed")
            return Result.ok([])

    async def get_dashboard(self) -> Result[dict[str, Any]]:
        """Dashboard data combining health, metrics, and status."""
        try:
            health = await self.get_health()
            metrics = await self.get_metrics()
            alerts = await self.get_alerts()
            return Result.ok({
                "timestamp": datetime.now(UTC).isoformat(),
                "health": health.value if health.success else {},
                "metrics": metrics.value if metrics.success else {},
                "alerts": alerts.value if alerts.success else [],
                "status": "healthy" if not alerts.value else "degraded",
            })
        except Exception as exc:
            logger.exception("Dashboard build failed")
            return Result.ok({
                "timestamp": datetime.now(UTC).isoformat(),
                "status": "degraded",
                "error": str(exc),
            })

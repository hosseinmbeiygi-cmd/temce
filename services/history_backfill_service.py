"""
History Backfill Service
========================

Automatically discovers symbols that lack historical data in the
BrsApi per-symbol tables and backfills them from the corresponding
endpoints.

Supported data types:
  - ``brsapi_historical_daily`` via ``/Tsetmc/History.php``
  - ``brsapi_candlesticks`` via ``/Tsetmc/Candlestick.php``
  - ``brsapi_shareholder_records`` via ``/Tsetmc/Shareholder.php``

Respects BrsApi rate limits per endpoint:
  - History endpoint: 24 req/min
  - Candlestick endpoint: 12 req/min
  - Shareholder endpoint: 12 req/min

Designed to run as a daily APScheduler job.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from brsapi.client import get_client
from brsapi.services.sync_service import BrsApiSyncService
from core.database import async_session_factory
from core.db_utils import safe_row_str
from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)

# Default settings tuned to stay safely below BrsApi rate limits.
# Rate limits are per endpoint, so each backfill phase uses its own
# concurrency and delay.
MIN_BARS_FOR_SKIP = 30  # Minimum number of records to consider a symbol covered


@dataclass
class BackfillPhaseConfig:
    """Configuration for a single backfill phase (one data type)."""

    data_type: str
    table_name: str
    count_column: str
    count_filter: str
    sync_method: Callable[..., Any]
    batch_size: int
    delay_seconds: float
    min_count: int


# Predefined phases.  Concurrency is chosen so that we stay well under the
# documented per-minute rate limits (batch_size * 6 batches/min < limit).
BACKFILL_PHASES: dict[str, BackfillPhaseConfig] = {
    "history": BackfillPhaseConfig(
        data_type="history",
        table_name="brsapi_historical_daily",
        count_column="*",
        count_filter="WHERE price_close > 0",
        sync_method=lambda svc, sess, sym: svc.sync_history_price(sess, sym),
        batch_size=4,
        delay_seconds=10.0,
        min_count=MIN_BARS_FOR_SKIP,
    ),
    "candlestick": BackfillPhaseConfig(
        data_type="candlestick",
        table_name="brsapi_candlesticks",
        count_column="*",
        count_filter="",
        sync_method=lambda svc, sess, sym: svc.sync_candlesticks(sess, sym),
        batch_size=2,
        delay_seconds=10.0,
        min_count=MIN_BARS_FOR_SKIP,
    ),
    "shareholder": BackfillPhaseConfig(
        data_type="shareholder",
        table_name="brsapi_shareholder_records",
        count_column="*",
        count_filter="",
        sync_method=lambda svc, sess, sym: svc.sync_shareholders(sess, sym),
        batch_size=2,
        delay_seconds=10.0,
        min_count=MIN_BARS_FOR_SKIP,
    ),
}


def _build_missing_symbols_query(phase: BackfillPhaseConfig) -> str:
    """Return the SQL query used to find symbols needing backfill for a phase."""
    filter_clause = phase.count_filter
    if filter_clause:
        filter_clause = f" {filter_clause}"
    return f"""
        SELECT i.symbol
        FROM instruments i
        LEFT JOIN (
            SELECT symbol, COUNT({phase.count_column}) AS row_count
            FROM {phase.table_name}{filter_clause}
            GROUP BY symbol
        ) t ON i.symbol = t.symbol
        WHERE i.symbol IS NOT NULL AND i.symbol != ''
          AND (i.status IS NULL OR i.status = 'active')
          AND (t.row_count IS NULL OR t.row_count < :min_count)
        ORDER BY t.row_count ASC NULLS FIRST, i.symbol ASC
    """


async def get_symbols_needing_backfill(
    session: Any,
    *,
    min_bars: int | None = None,
    phase: BackfillPhaseConfig | None = None,
    min_count: int | None = None,
) -> list[str]:
    """
    Query the database for symbols that need backfill for the given phase.

    ``min_bars`` is a deprecated alias for ``min_count`` and is kept for
    backward compatibility with callers that pass it as a keyword arg.

    Returns symbols from ``instruments`` that have fewer than ``min_count``
    rows in the target backfill table.
    """
    if phase is None:
        phase = BACKFILL_PHASES["history"]
    threshold = min_count if min_count is not None else min_bars if min_bars is not None else phase.min_count
    result = await session.execute(
        text(_build_missing_symbols_query(phase)),
        {"min_count": threshold},
    )
    return [safe_row_str(row, idx=0) for row in result.fetchall()]


async def get_backfill_stats(
    session: Any,
    phase: BackfillPhaseConfig,
) -> dict[str, Any]:
    """Get statistics about backfill coverage for a single phase."""
    filter_clause = phase.count_filter
    if filter_clause:
        filter_clause = f" {filter_clause}"

    result = await session.execute(
        text(f"""
            SELECT
                COUNT(DISTINCT i.symbol) AS total_instruments,
                COUNT(DISTINCT t.symbol) AS with_data,
                COUNT(DISTINCT i.symbol) - COUNT(DISTINCT t.symbol) AS missing,
                COALESCE(SUM(t.row_count), 0) AS total_rows,
                COALESCE(AVG(t.row_count), 0) AS avg_rows_per_symbol
            FROM instruments i
            LEFT JOIN (
                SELECT symbol, COUNT({phase.count_column}) AS row_count
                FROM {phase.table_name}{filter_clause}
                GROUP BY symbol
            ) t ON i.symbol = t.symbol
            WHERE i.symbol IS NOT NULL AND i.symbol != ''
              AND (i.status IS NULL OR i.status = 'active')
        """),
    )
    row = result.fetchone()
    if not row:
        return {}
    return {
        "total_instruments": row[0] or 0,
        "with_data": row[1] or 0,
        "missing": row[2] or 0,
        "total_rows": row[3] or 0,
        "avg_rows_per_symbol": round(float(row[4] or 0), 1),
    }


async def run_backfill_for_symbol(
    sync_service: BrsApiSyncService,
    session: Any,
    symbol: str,
    phase: BackfillPhaseConfig,
) -> dict[str, Any]:
    """
    Fetch backfill data for a single symbol and phase.

    Returns a dict with symbol, data_type, success, items_count, and error.
    """
    try:
        report = await phase.sync_method(sync_service, session, symbol)
        return {
            "symbol": symbol,
            "data_type": phase.data_type,
            "success": report.success,
            "items_count": report.items_count,
            "error": report.error,
        }
    except Exception as e:
        logger.warning("Backfill failed for %s/%s: %s", phase.data_type, symbol, e)
        return {
            "symbol": symbol,
            "data_type": phase.data_type,
            "success": False,
            "items_count": 0,
            "error": str(e),
        }


def _apply_phase_overrides(
    phase: BackfillPhaseConfig,
    overrides: dict[str, Any] | None,
) -> BackfillPhaseConfig:
    """Return a phase config with optional per-phase overrides applied."""
    if not overrides:
        return phase
    try:
        batch_size = int(overrides.get("batch_size", phase.batch_size))
        delay_seconds = float(overrides.get("delay_seconds", phase.delay_seconds))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid phase override for {phase.data_type}: {exc}") from exc
    return BackfillPhaseConfig(
        data_type=phase.data_type,
        table_name=phase.table_name,
        count_column=phase.count_column,
        count_filter=phase.count_filter,
        sync_method=phase.sync_method,
        batch_size=batch_size,
        delay_seconds=delay_seconds,
        min_count=phase.min_count,
    )


async def execute_backfill_phase(
    session: Any,
    sync_service: BrsApiSyncService,
    phase: BackfillPhaseConfig,
    max_symbols: int = 0,
) -> dict[str, Any]:
    """
    Backfill a single data type for all symbols that need it.

    Args:
        session: Async SQLAlchemy session.
        sync_service: BrsApi sync service instance.
        phase: Configuration for the backfill phase.
        max_symbols: Max symbols to process (0 = unlimited).

    Returns:
        Dict with summary for this phase.
    """
    started_at = datetime.now(UTC)

    stats_before = await get_backfill_stats(session, phase)
    logger.info(
        "Backfill phase %s start: %d symbols with data out of %d instruments",
        phase.data_type,
        stats_before.get("with_data", 0),
        stats_before.get("total_instruments", 0),
    )

    symbols = await get_symbols_needing_backfill(session, phase)
    if not symbols:
        logger.info("Backfill phase %s: no symbols need backfill", phase.data_type)
        return {
            "status": "skipped",
            "phase": phase.data_type,
            "message": "All symbols already have sufficient data",
            "stats_before": stats_before,
        }

    if max_symbols > 0:
        symbols = symbols[:max_symbols]

    logger.info(
        "Backfill phase %s: found %d symbols needing backfill",
        phase.data_type,
        len(symbols),
    )

    all_results: list[dict[str, Any]] = []
    total_batches = math.ceil(len(symbols) / phase.batch_size)

    for batch_idx in range(total_batches):
        start_idx = batch_idx * phase.batch_size
        end_idx = min(start_idx + phase.batch_size, len(symbols))
        batch = symbols[start_idx:end_idx]

        logger.info(
            "Phase %s batch %d/%d: processing %d symbols (%d-%d of %d)",
            phase.data_type,
            batch_idx + 1,
            total_batches,
            len(batch),
            start_idx + 1,
            end_idx,
            len(symbols),
        )

        tasks = [
            run_backfill_for_symbol(sync_service, session, sym, phase)
            for sym in batch
        ]
        batch_results = await asyncio.gather(*tasks)
        all_results.extend(batch_results)

        succeeded = sum(1 for r in batch_results if r["success"])
        items = sum(r["items_count"] for r in batch_results)
        logger.info(
            "Phase %s batch %d: %d succeeded, %d items, %d failed",
            phase.data_type,
            batch_idx + 1,
            succeeded,
            items,
            len(batch_results) - succeeded,
        )

        if batch_idx < total_batches - 1:
            await asyncio.sleep(phase.delay_seconds)

    elapsed = (datetime.now(UTC) - started_at).total_seconds()
    total_succeeded = sum(1 for r in all_results if r["success"])
    total_failed = sum(1 for r in all_results if not r["success"])
    total_items = sum(r["items_count"] for r in all_results)

    logger.info(
        "Backfill phase %s complete: %d/%d symbols, %d items in %.1fs",
        phase.data_type,
        total_succeeded,
        len(symbols),
        total_items,
        elapsed,
    )

    stats_after = await get_backfill_stats(session, phase)

    return {
        "status": "completed",
        "phase": phase.data_type,
        "total_symbols_processed": len(symbols),
        "succeeded": total_succeeded,
        "failed": total_failed,
        "total_items_fetched": total_items,
        "duration_seconds": round(elapsed, 1),
        "stats_before": stats_before,
        "stats_after": stats_after,
        "errors": [r["error"] for r in all_results if not r["success"] and r.get("error")],
    }


async def execute_backfill(
    max_symbols: int | dict[str, int] = 0,
    data_types: list[str] | None = None,
    phase_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Main backfill execution.

    Runs through each requested data type sequentially, fetching missing
    data for all active symbols.  Concurrency is controlled per phase to
    stay within BrsApi rate limits.

    Args:
        max_symbols: Max symbols to process per phase. If an int, applied
            to all phases. If a dict, maps phase data_type to its max.
        data_types: List of data types to backfill. Defaults to all.
        phase_overrides: Optional per-phase overrides for ``batch_size``
            and ``delay_seconds``.

    Returns:
        Dict with summary for each phase.
    """
    if async_session_factory is None:
        return {"error": "Database not initialized"}

    if data_types is None:
        data_types = list(BACKFILL_PHASES.keys())

    # Validate requested data types
    unknown = [dt for dt in data_types if dt not in BACKFILL_PHASES]
    if unknown:
        return {"error": f"Unknown data types: {unknown}"}

    phase_overrides = phase_overrides or {}
    started_at = datetime.now(UTC)
    phase_results: list[dict[str, Any]] = []
    total_items = 0

    async with async_session_factory() as session:
        client = await get_client()
        sync_service = BrsApiSyncService(client=client)

        try:
            for data_type in data_types:
                phase = _apply_phase_overrides(
                    BACKFILL_PHASES[data_type],
                    phase_overrides.get(data_type),
                )
                phase_max_symbols = (
                    max_symbols.get(data_type, 0)
                    if isinstance(max_symbols, dict)
                    else max_symbols
                )
                result = await execute_backfill_phase(
                    session,
                    sync_service,
                    phase,
                    max_symbols=phase_max_symbols,
                )
                phase_results.append(result)
                total_items += result.get("total_items_fetched", 0)

                # Commit after each phase so partial progress is preserved.
                await session.commit()
        finally:
            await client.stop()

    elapsed = (datetime.now(UTC) - started_at).total_seconds()

    return {
        "status": "completed",
        "phases": phase_results,
        "total_items_fetched": total_items,
        "duration_seconds": round(elapsed, 1),
    }


# ── APScheduler Job ──────────────────────────────────────────────────────────


class BackfillHistoricalDataJob(BaseJob):
    """
    Scheduled job that auto-backfills per-symbol historical data for
    daily prices, candlesticks, and shareholder records.

    Registered as a daily job in the APScheduler.

    Supported JobContext params:
        data_types (list[str]): Phases to run, e.g. ["history", "candlestick"].
        max_symbols (int | dict[str, int]): Max symbols per phase. An int
            applies to all phases; a dict maps phase name to its limit.
        batch_sizes (dict[str, int]): Per-phase batch_size overrides.
        delay_seconds (dict[str, float]): Per-phase delay_seconds overrides.
    """

    async def execute(self, context: JobContext) -> JobResult:
        logger.info("BackfillHistoricalDataJob started")

        try:
            # Allow overriding data types and per-phase limits via job context.
            data_types = context.get_param("data_types", list(BACKFILL_PHASES.keys()))
            max_symbols = context.get_param("max_symbols", 0)
            batch_sizes = context.get_param("batch_sizes", {})
            delay_seconds = context.get_param("delay_seconds", {})

            if not isinstance(data_types, list):
                raise ValueError(f"data_types must be a list, got {type(data_types).__name__}")
            if isinstance(max_symbols, dict) and not all(isinstance(v, int) for v in max_symbols.values()):
                raise ValueError("max_symbols dict values must be integers")
            if not isinstance(batch_sizes, dict):
                raise ValueError(f"batch_sizes must be a dict, got {type(batch_sizes).__name__}")
            if not isinstance(delay_seconds, dict):
                raise ValueError(f"delay_seconds must be a dict, got {type(delay_seconds).__name__}")

            # Build per-phase overrides for batch_size and delay_seconds.
            phase_overrides: dict[str, dict[str, Any]] = {}
            for data_type in data_types:
                overrides: dict[str, Any] = {}
                if data_type in batch_sizes:
                    overrides["batch_size"] = batch_sizes[data_type]
                if data_type in delay_seconds:
                    overrides["delay_seconds"] = delay_seconds[data_type]
                if overrides:
                    phase_overrides[data_type] = overrides

            logger.debug(
                "BackfillHistoricalDataJob config: data_types=%s max_symbols=%s phase_overrides=%s",
                data_types,
                max_symbols,
                phase_overrides,
            )

            result = await execute_backfill(
                data_types=data_types,
                max_symbols=max_symbols,
                phase_overrides=phase_overrides,
            )

            if "error" in result:
                return JobResult.failure(result["error"], job_name=self.name)

            phase_summaries = []
            for phase in result.get("phases", []):
                if phase.get("status") == "skipped":
                    phase_summaries.append(
                        f"{phase['phase']}: skipped ({phase.get('message', '')})"
                    )
                else:
                    phase_summaries.append(
                        f"{phase['phase']}: {phase['succeeded']}/{phase['total_symbols_processed']} symbols, "
                        f"{phase['total_items_fetched']} items"
                    )

            summary = " | ".join(phase_summaries)

            return JobResult.success_result(
                job_name=self.name,
                data=result,
                message=summary,
            )

        except Exception as e:
            logger.exception("BackfillHistoricalDataJob failed")
            return JobResult.failure(str(e), job_name=self.name)

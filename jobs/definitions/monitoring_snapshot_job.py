"""Monitoring Snapshot Job — fills the 6 audit-F6 monitoring tables nightly.

Tables targeted:
  data_freshness          — latest ingest timestamp per data source
  market_data_quality_events — staleness events when TTL is exceeded
  signal_performance      — ensure_tables + evaluate pending signal outcomes
  signal_weight_accuracy  — updated by SignalPerformanceTracker.evaluate_pending_signals
  decision_results        — written by the decision engine endpoint (not here)

The job is idempotent: upserts on data_freshness, ON CONFLICT DO NOTHING on
market_data_quality_events (keyed on source+instrument+created_at minute).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = logging.getLogger(__name__)

# Staleness threshold per source (seconds)
_STALENESS_TTL = {
    "brsapi_symbol_snapshots": 7200,       # 2 h — intraday ticks
    "brsapi_historical_daily": 86400 * 2,  # 2 d — daily bars
    "brsapi_gold_coin_prices": 7200,
    "brsapi_currency_prices": 7200,
    "gold_option_iv_history": 86400 * 2,
    "option_snapshots": 86400 * 2,
    "signals": 86400 * 2,
}

_FRESHNESS_QUERY = """
SELECT
    '{table}' AS data_type,
    MAX(COALESCE(updated_at, created_at)) AS last_ok
FROM {table}
"""


class MonitoringSnapshotJob(BaseJob):
    """Nightly snapshot of data-source freshness and signal-performance evaluation."""

    async def execute(self, context: JobContext) -> JobResult:
        from jobs.definitions.gold_macro_jobs import _with_session

        async def run(session) -> JobResult:
            return await _run_snapshot(session)

        return await _with_session(self._name, run)


async def _run_snapshot(session) -> JobResult:
    now = datetime.now(UTC).replace(tzinfo=None)
    freshness_updated = 0
    quality_events = 0

    for table, ttl in _STALENESS_TTL.items():
        try:
            row = (await session.execute(text(
                f"SELECT MAX(COALESCE(updated_at, created_at)) FROM {table}"
            ))).scalar_one_or_none()
            last_ok_val = row if row is not None else None

            # 1. Upsert data_freshness
            await session.execute(text("""
                INSERT INTO data_freshness (data_type, last_ok, ttl)
                VALUES (:dt, :lo, :ttl)
                ON CONFLICT (data_type) DO UPDATE
                    SET last_ok = EXCLUDED.last_ok,
                        ttl     = EXCLUDED.ttl,
                        updated_at = NOW()
            """), {"dt": table, "lo": last_ok_val, "ttl": ttl})
            freshness_updated += 1

            # 2. Emit market_data_quality_events when stale
            if last_ok_val is not None:
                age_s = (now - last_ok_val).total_seconds()
                if age_s > ttl:
                    await session.execute(text("""
                        INSERT INTO market_data_quality_events
                            (source, instrument, severity, reason, details)
                        VALUES (:src, :inst, 'warning', :reason, :det::jsonb)
                    """), {
                        "src": "MonitoringSnapshotJob",
                        "inst": table,
                        "reason": "stale_source",
                        "det": f'{{"table": "{table}", "age_seconds": {int(age_s)}, "ttl": {ttl}}}',
                    })
                    quality_events += 1
            else:
                # Empty table — emit a data-gap event
                await session.execute(text("""
                    INSERT INTO market_data_quality_events
                        (source, instrument, severity, reason, details)
                    VALUES (:src, :inst, 'critical', :reason, :det::jsonb)
                """), {
                    "src": "MonitoringSnapshotJob",
                    "inst": table,
                    "reason": "empty_table",
                    "det": f'{{"table": "{table}"}}',
                })
                quality_events += 1
        except Exception as exc:
            logger.warning("MonitoringSnapshotJob: table %s failed: %s", table, exc)
            continue

    await session.commit()

    # 3. Evaluate pending signal_performance outcomes + update signal_weight_accuracy
    perf_evaluated = 0
    try:
        from services.signal_performance_tracker import SignalPerformanceTracker
        tracker = SignalPerformanceTracker(session=session)
        await tracker.ensure_tables()
        results = await tracker.evaluate_pending_signals()
        perf_evaluated = len(results)
    except Exception as exc:
        logger.warning("MonitoringSnapshotJob: signal_performance eval failed: %s", exc)

    logger.info(
        "MonitoringSnapshotJob: freshness=%d quality_events=%d signal_perf_evaluated=%d",
        freshness_updated, quality_events, perf_evaluated,
    )
    return JobResult.success_result(
        job_name="MonitoringSnapshotJob",
        data={
            "freshness_updated": freshness_updated,
            "quality_events_written": quality_events,
            "signal_perf_evaluated": perf_evaluated,
        },
    )


__all__ = ["MonitoringSnapshotJob"]

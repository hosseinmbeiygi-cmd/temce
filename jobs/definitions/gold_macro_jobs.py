"""Gold macro / sentiment ingestion jobs.

Three scheduled jobs feed the gold macro tables:

* ``GoldMacroSyncJob`` — FRED 10Y TIPS real yield (DFII10) + broad dollar
  index (DTWEXBGS).  Skipped when ``FRED_API_KEY`` is not configured, so a
  deployment without a key never fails the scheduler.
* ``GoldCftcCotSyncJob`` — CFTC Commitment of Traders gold futures positions.
* ``GoldEconomicCalendarSyncJob`` — CPI / NFP / FOMC calendar (seeded).

Every sync is idempotent (upsert by observation date), so re-running a job
after a restart never duplicates rows.  The providers are built through
module-level factories so tests can inject recorded fixtures instead of
touching the network.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)

FRED_API_KEY_ENV = "FRED_API_KEY"
DEFAULT_BACKFILL_YEARS = 2


# ── Provider factories (monkeypatch points for tests) ──────────────────────


def _fred_key_configured() -> bool:
    """True when FRED is configured via env *or* the repository ``.env``."""
    if os.environ.get(FRED_API_KEY_ENV):
        return True
    try:
        from core.config import get_settings

        return bool(get_settings().fred_api_key)
    except Exception:  # pragma: no cover - config failure means "not configured"
        return False


def _build_fred_provider() -> Any:
    from providers.macro_sources.fred import FREDClient

    return FREDClient()


def _build_cftc_provider() -> Any:
    from providers.macro_sources.cftc import CFTCClient

    return CFTCClient()


def _build_calendar_provider() -> Any:
    from providers.macro_sources.economic_calendar import SeededEconomicCalendarProvider

    return SeededEconomicCalendarProvider()


def _build_tokenized_gold_provider(session: Any) -> Any:
    from providers.macro_sources.tokenized_gold import BrsApiTokenizedGoldProvider

    return BrsApiTokenizedGoldProvider(session)


def _build_gold_spot_provider(session: Any) -> Any:
    from providers.macro_sources.tokenized_gold import StoredGoldSpotProvider

    return StoredGoldSpotProvider(session)


# ── Helpers ───────────────────────────────────────────────────────────────


def _result_to_job_result(result: Any, job_name: str) -> JobResult:
    """Translate a ``SyncResult`` into a ``JobResult`` (data kept on failure)."""
    data = {
        "job_type": result.job_type,
        "upserted": result.upserted,
        "skipped": result.skipped,
        "errors": result.errors[:20],
        "duration_ms": round(result.duration_ms, 1),
    }
    if result.ok:
        return JobResult.success_result(job_name=job_name, data=data)
    return JobResult(
        success=False,
        job_name=job_name,
        message="Failed",
        error="; ".join(result.errors[:3]) or "sync failed",
        data=data,
    )


async def _with_session(job_name: str, run) -> JobResult:
    """Run ``run(session)`` inside a DB session, following the job conventions."""
    from core.database import get_session

    session_obtained = False
    try:
        async for session in get_session():
            session_obtained = True
            result = await run(session)

        if not session_obtained:
            return JobResult.failure("Could not obtain DB session", job_name=job_name)
        return result
    except Exception as exc:  # noqa: BLE001 - a job must never crash the scheduler
        logger.exception("%s failed", job_name)
        return JobResult.failure(str(exc), job_name=job_name)


# ── Jobs ──────────────────────────────────────────────────────────────────


class GoldMacroSyncJob(BaseJob):
    """Sync FRED macro indicators (10Y TIPS real yield + broad dollar index).

    The regular run fetches the latest observation.  Pass
    ``{"backfill": true, "years": 2}`` (or an explicit
    ``observation_start``) to run the one-shot history backfill instead; the
    window defaults to two years and the upsert is idempotent.
    """

    async def execute(self, context: JobContext) -> JobResult:
        if not _fred_key_configured():
            logger.info(
                "GoldMacroSyncJob skipped: %s is not configured", FRED_API_KEY_ENV
            )
            return JobResult.success_result(
                job_name=self._name,
                message="skipped",
                data={"skipped": True, "reason": f"{FRED_API_KEY_ENV} is not configured"},
            )

        backfill = bool(context.get_param("backfill", False))
        if not backfill:
            backfill = (
                context.get_param("observation_start") is not None
                or context.get_param("years") is not None
            )

        observation_start = context.get_param("observation_start")
        observation_end = context.get_param("observation_end")
        if backfill and observation_start is None:
            years = int(context.get_param("years", DEFAULT_BACKFILL_YEARS))
            observation_start = (
                datetime.now(UTC).date() - timedelta(days=365 * years)
            ).isoformat()

        from services.gold.macro_sync import MacroSyncService

        async def run(session) -> JobResult:
            service = MacroSyncService(
                session, fred_provider=_build_fred_provider()
            )
            if backfill:
                result = await service.backfill_fred_indicators(
                    observation_start=observation_start,
                    observation_end=observation_end,
                )
            else:
                result = await service.sync_fred_indicators()
            logger.info("GoldMacroSyncJob: %s", result)
            return _result_to_job_result(result, self._name)

        return await _with_session(self._name, run)


class GoldCftcCotSyncJob(BaseJob):
    """Sync CFTC Commitment of Traders gold futures positions."""

    async def execute(self, context: JobContext) -> JobResult:
        from services.gold.macro_sync import MacroSyncService

        async def run(session) -> JobResult:
            service = MacroSyncService(
                session, cftc_provider=_build_cftc_provider()
            )
            result = await service.sync_cftc_cot_gold()
            logger.info("GoldCftcCotSyncJob: %s", result)
            return _result_to_job_result(result, self._name)

        return await _with_session(self._name, run)


class GoldEconomicCalendarSyncJob(BaseJob):
    """Sync the CPI / NFP / FOMC economic calendar."""

    async def execute(self, context: JobContext) -> JobResult:
        from services.gold.macro_sync import MacroSyncService

        async def run(session) -> JobResult:
            service = MacroSyncService(
                session, calendar_provider=_build_calendar_provider()
            )
            result = await service.sync_economic_calendar()
            logger.info("GoldEconomicCalendarSyncJob: %s", result)
            return _result_to_job_result(result, self._name)

        return await _with_session(self._name, run)


class GoldTokenizedGoldSyncJob(BaseJob):
    """Sync tokenized-gold (PAXG / XAUT) premium against spot.

    Reads the BrsApi crypto feed that is already synced into the database plus
    the stored gold spot, so it needs no extra market-data subscription.
    """

    async def execute(self, context: JobContext) -> JobResult:
        from services.gold.macro_sync import MacroSyncService

        async def run(session) -> JobResult:
            service = MacroSyncService(
                session,
                tokenized_gold_provider=_build_tokenized_gold_provider(session),
                gold_spot_provider=_build_gold_spot_provider(session),
            )
            result = await service.sync_tokenized_gold_premium()
            logger.info("GoldTokenizedGoldSyncJob: %s", result)
            return _result_to_job_result(result, self._name)

        return await _with_session(self._name, run)


__all__ = [
    "FRED_API_KEY_ENV",
    "GoldCftcCotSyncJob",
    "GoldEconomicCalendarSyncJob",
    "GoldMacroSyncJob",
    "GoldTokenizedGoldSyncJob",
]

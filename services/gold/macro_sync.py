"""Gold macro / sentiment sync jobs.

Sync jobs are:

* idempotent — upsert by (indicator, as_of) for FRED series and by
  ``report_date`` for CFTC COT, so re-running a job never duplicates rows,
* retried — each source call retries on transient failure with backoff,
* network-free in tests — every source provider is injectable, so tests use
  recorded fixtures / mock providers.

Per-row provenance and ``fetched_at`` are stored on every inserted row.
"""

from __future__ import annotations

import asyncio
import inspect
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from models.gold_macro import (
    GoldCotPositionModel,
    GoldEconomicCalendarEventModel,
    GoldIranManualEventModel,
    GoldMacroIndicatorModel,
)
from providers.macro_sources.cftc import CFTC_GOLD_CONTRACT_MARKET_CODE, CFTCClient
from providers.macro_sources.economic_calendar import (
    EconomicCalendarProvider,
    SeededEconomicCalendarProvider,
)
from providers.macro_sources.fred import (
    FRED_DXY_BROAD_SERIES,
    FRED_TIPS_10Y_SERIES,
    FREDClient,
)
from providers.macro_sources.tokenized_gold import (
    PREMIUM_INDICATOR_SUFFIX,
    BrsApiTokenizedGoldProvider,
    GoldSpotPriceProvider,
    StoredGoldSpotProvider,
    TokenizedGoldProvider,
    compute_tokenized_gold_premium,
)
from services.gold.macro_indicators import percentile

logger = get_logger(__name__)

# ── High-volatility calendar categories ────────────────────────────────
HIGH_VOLATILITY_CATEGORIES = ("CPI", "NFP", "FOMC")
DEFAULT_STALENESS_SECONDS = 7 * 24 * 60 * 60  # 7 days


@dataclass
class SyncResult:
    """Outcome of a single sync job."""

    job_type: str
    ok: bool = False
    upserted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


# ── Helpers ────────────────────────────────────────────────────────────


def _iso_from_raw(value: Any) -> str | None:
    """Normalise a provider observation date to an ISO date string."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value[:10]
    return None


def _as_of_datetime(as_of: str) -> datetime:
    """Turn an ISO date into the aware UTC midnight stored in ``as_of``.

    The column is ``timestamptz``: binding the raw string would compare
    ``timestamptz = varchar`` and raise on PostgreSQL, so both the stored
    value and the existence check use this same aware datetime.
    """
    parsed = date.fromisoformat(as_of[:10])
    return datetime.combine(parsed, time.min, tzinfo=UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def _run_with_retry(fn, attempts: int = 3, base_delay: float = 0.5, **kwargs):
    """Run ``fn(**kwargs)`` with exponential backoff retries.

    Retries every exception: a provider may raise ``MacroSourceError`` for
    known transport failures, or an unwrapped ``httpx``/parse error. The job
    must never crash the scheduler, so the last error is re-raised and the
    caller records it.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            if inspect.iscoroutinefunction(fn):
                return await fn(**kwargs)
            return fn(**kwargs)
        except Exception as exc:  # noqa: BLE001 - every provider failure is retryable
            last_exc = exc
            logger.warning(
                "macro sync attempt %d/%d failed: %s", attempt, attempts, exc
            )
            if attempt < attempts:
                await asyncio.sleep(base_delay * attempt)
    raise last_exc or RuntimeError("sync job failed with no recorded error")


def summarize_indicator_values(
    values: Iterable[float | None],
    percentiles: tuple[float, ...] = (10.0, 20.0, 50.0, 80.0, 90.0),
) -> dict[str, Any]:
    """Count/min/max plus percentiles for a stored indicator series.

    Used by the backfill CLI to prove the fetched window is large and its
    thresholds are stable (``count``, ``min``, ``max``, ``p20``, ``p80``...).
    """
    cleaned: list[float] = []
    for raw in values:
        if raw is None:
            continue
        try:
            number = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            cleaned.append(number)

    summary: dict[str, Any] = {
        "count": len(cleaned),
        "min": min(cleaned) if cleaned else None,
        "max": max(cleaned) if cleaned else None,
    }
    for pct in percentiles:
        key = f"p{int(pct) if float(pct).is_integer() else pct}"
        summary[key] = percentile(cleaned, pct) if cleaned else None
    return summary


# ── Sync service ───────────────────────────────────────────────────────


class MacroSyncService:
    """Drive the gold macro / sentiment ingestion jobs."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        fred_provider: FREDClient | None = None,
        cftc_provider: CFTCClient | None = None,
        calendar_provider: EconomicCalendarProvider | None = None,
        tokenized_gold_provider: TokenizedGoldProvider | None = None,
        gold_spot_provider: GoldSpotPriceProvider | None = None,
        clock: Any = None,
        retry_attempts: int = 3,
        retry_base_delay: float = 0.5,
    ) -> None:
        self.session = session
        self.fred_provider = fred_provider or FREDClient()
        self.cftc_provider = cftc_provider or CFTCClient()
        self.calendar_provider = calendar_provider or SeededEconomicCalendarProvider()
        self.tokenized_gold_provider = (
            tokenized_gold_provider or BrsApiTokenizedGoldProvider(session)
        )
        self.gold_spot_provider = gold_spot_provider or StoredGoldSpotProvider(session)
        self.clock = clock or _utc_now
        self.retry_attempts = retry_attempts
        self.retry_base_delay = retry_base_delay

    async def _safe_rollback(self) -> None:
        """Roll back a failed batch so the session is usable again.

        A failed statement aborts the whole PostgreSQL transaction, so every
        later statement in the batch would fail too. The batch is discarded
        and the next scheduled run redoes it (all upserts are idempotent).
        """
        try:
            await self.session.rollback()
        except Exception:  # noqa: BLE001 - nothing left to salvage
            logger.warning("macro sync rollback failed", exc_info=True)

    # ── FRED: 10Y TIPS real yield + broad dollar index ───────────────

    async def sync_fred_indicators(
        self,
        indicators: tuple[str, ...] = (FRED_TIPS_10Y_SERIES, FRED_DXY_BROAD_SERIES),
    ) -> SyncResult:
        """Idempotent upsert of FRED macro observations (provenance + fetched_at)."""
        started = _utc_now()
        result = SyncResult(job_type="fred_macro_indicators")
        try:
            observations = await _run_with_retry(
                self.fred_provider.fetch,
                attempts=self.retry_attempts,
                base_delay=self.retry_base_delay,
            )
        except Exception as exc:  # noqa: BLE001 - never crash the scheduler
            result.errors.append(str(exc))
            result.duration_ms = (_utc_now() - started).total_seconds() * 1000
            return result

        filtered = [
            obs
            for obs in observations
            if obs.get("series_id") in indicators
        ]
        for obs in filtered:
            try:
                if await self._upsert_macro_indicator(obs):
                    result.upserted += 1
                else:
                    result.skipped += 1
            except Exception as exc:  # noqa: BLE001 - one bad row shouldn't kill the job
                result.errors.append(f"{obs.get('series_id')}: {exc}")
                await self._safe_rollback()
                result.upserted = 0
                result.skipped = 0

        await self.session.commit()
        result.ok = not result.errors or result.upserted > 0
        result.duration_ms = (_utc_now() - started).total_seconds() * 1000
        return result

    async def backfill_fred_indicators(
        self,
        *,
        observation_start: str | date,
        observation_end: str | date | None = None,
        indicators: tuple[str, ...] = (FRED_TIPS_10Y_SERIES, FRED_DXY_BROAD_SERIES),
    ) -> SyncResult:
        """One-shot historical backfill of FRED macro observations.

        Fetches every observation from ``observation_start`` (the caller uses
        today − 2 years) and upserts by ``(indicator, as_of)``.  Re-running the
        same window is a no-op: existing rows are counted as ``skipped``.
        """
        started = _utc_now()
        result = SyncResult(job_type="fred_macro_backfill")
        start = (
            observation_start.isoformat()
            if isinstance(observation_start, date)
            else str(observation_start)
        )
        end = (
            observation_end.isoformat()
            if isinstance(observation_end, date)
            else (str(observation_end) if observation_end is not None else None)
        )
        result.details = {
            "observation_start": start,
            "observation_end": end,
            "indicators": list(indicators),
        }

        for series_id in indicators:
            try:
                observations = await _run_with_retry(
                    self.fred_provider.fetch_range,
                    attempts=self.retry_attempts,
                    base_delay=self.retry_base_delay,
                    series_id=series_id,
                    observation_start=start,
                    observation_end=end,
                )
            except Exception as exc:  # noqa: BLE001 - never crash the scheduler
                result.errors.append(f"{series_id}: {exc}")
                continue

            series_upserted = 0
            series_skipped = 0
            for obs in observations:
                try:
                    if await self._upsert_macro_indicator(obs):
                        series_upserted += 1
                    else:
                        series_skipped += 1
                except Exception as exc:  # noqa: BLE001 - one bad row shouldn't kill the job
                    result.errors.append(f"{series_id}: {exc}")
                    await self._safe_rollback()
                    # The rollback discarded this series' uncommitted inserts.
                    series_upserted = 0
                    series_skipped = 0
                    break

            result.upserted += series_upserted
            result.skipped += series_skipped
            result.details[f"{series_id}_rows"] = len(observations)
            # Commit per series so a later series failure cannot discard an
            # already-completed backfill.
            await self.session.commit()

        result.ok = not result.errors or result.upserted > 0
        result.duration_ms = (_utc_now() - started).total_seconds() * 1000
        return result

    async def _upsert_macro_indicator(self, obs: dict[str, Any]) -> bool:
        """Store one observation. Returns True when a row was added, False when skipped."""
        series_id = obs.get("series_id")
        as_of = _iso_from_raw(obs.get("observation_date"))
        if not series_id or not as_of:
            return False
        return await self._store_macro_indicator(
            indicator=f"FRED_{series_id}",
            value=obs.get("value"),
            previous_value=obs.get("previous_value"),
            change_pct=obs.get("change"),
            as_of=as_of,
            source="FRED",
            unit="percent" if series_id == FRED_TIPS_10Y_SERIES else "index",
            frequency="daily",
            provenance=str(obs.get("provenance") or series_id),
        )

    async def _store_macro_indicator(
        self,
        *,
        indicator: str,
        value: float | None,
        as_of: str,
        source: str,
        unit: str,
        frequency: str,
        previous_value: float | None = None,
        change_pct: float | None = None,
        provenance: str | None = None,
    ) -> bool:
        """Idempotent upsert of one macro-indicator observation.

        ``as_of`` is an ISO date string in both the stored value and the
        existence check, so a re-run can never duplicate a row.
        """
        if not indicator or not as_of:
            return False

        existing = await self._get_macro_indicator(indicator, as_of)
        if existing is not None:
            return False  # idempotent: already stored

        row = GoldMacroIndicatorModel(
            indicator=indicator,
            country="global",
            value=value,
            previous_value=previous_value,
            change_pct=change_pct,
            as_of=_as_of_datetime(as_of) if isinstance(as_of, str) else as_of,
            fetched_at=self.clock(),
            source=source,
            provenance=provenance or indicator,
            unit=unit,
            frequency=frequency,
        )
        self.session.add(row)
        return True

    async def _get_macro_indicator(
        self, indicator: str, as_of: str
    ) -> GoldMacroIndicatorModel | None:
        statement = select(GoldMacroIndicatorModel).where(
            GoldMacroIndicatorModel.indicator == indicator,
            GoldMacroIndicatorModel.as_of == _as_of_datetime(as_of),
        )
        result = await self.session.execute(statement)
        return result.scalars().first()

    # ── CFTC COT gold ────────────────────────────────────────────────

    async def sync_cftc_cot_gold(self) -> SyncResult:
        """Idempotent upsert of CFTC COT gold futures positions."""
        started = _utc_now()
        result = SyncResult(job_type="cftc_cot_gold")
        try:
            observations = await _run_with_retry(
                self.cftc_provider.fetch,
                attempts=self.retry_attempts,
                base_delay=self.retry_base_delay,
            )
        except Exception as exc:  # noqa: BLE001 - never crash the scheduler
            result.errors.append(str(exc))
            result.duration_ms = (_utc_now() - started).total_seconds() * 1000
            return result

        # Percentile needs history: compute ranking over stored rows incl. the
        # current batch. Load existing rows sorted newest-first.
        existing_rows = await self._load_existing_cot_rows()
        existing_dates = {
            parsed
            for parsed in (_date_from_raw(row.report_date) for row in existing_rows)
            if parsed is not None
        }

        # Order ascending by date so percentile ranking is stable.
        batch = sorted(
            [obs for obs in observations if obs.get("report_date")],
            key=lambda o: str(o.get("report_date")),
        )

        # Normalise every report_date to an ISO string so stored rows (date)
        # and provider rows (str) sort together.
        all_rows: list[dict[str, Any]] = [
            {
                "report_date": str(row.report_date),
                "managed_money_net": row.managed_money_net,
            }
            for row in existing_rows
        ]
        for obs in batch:
            all_rows.append(
                {
                    "report_date": str(obs.get("report_date")),
                    "managed_money_net": obs.get("managed_money_net"),
                }
            )
        all_rows.sort(key=lambda r: r["report_date"])

        nets = [r["managed_money_net"] for r in all_rows if r["managed_money_net"] is not None]
        sorted_nets = sorted(nets)

        for obs in batch:
            report_date = _date_from_raw(obs.get("report_date"))
            if report_date is None:
                continue
            if report_date in existing_dates:
                result.skipped += 1
                continue
            net = obs.get("managed_money_net")
            percentile = self._percentile(net, sorted_nets)
            row = GoldCotPositionModel(
                report_date=report_date,
                cftc_contract_market_code=CFTC_GOLD_CONTRACT_MARKET_CODE,
                market_name=obs.get("market_name"),
                managed_money_long=obs.get("managed_money_long"),
                managed_money_short=obs.get("managed_money_short"),
                managed_money_net=net,
                managed_money_net_change=obs.get("managed_money_net_change"),
                commercial_long=obs.get("commercial_long"),
                commercial_short=obs.get("commercial_short"),
                commercial_net=obs.get("commercial_net"),
                open_interest=obs.get("open_interest"),
                managed_money_net_percentile=percentile,
                fetched_at=self.clock(),
                source="CFTC",
                provenance=str(obs.get("provenance") or "CFTC COT disaggregated"),
            )
            self.session.add(row)
            result.upserted += 1

        await self.session.commit()
        result.ok = not result.errors or result.upserted > 0
        result.duration_ms = (_utc_now() - started).total_seconds() * 1000
        return result

    async def _load_existing_cot_rows(self) -> list[GoldCotPositionModel]:
        statement = (
            select(GoldCotPositionModel)
            .where(GoldCotPositionModel.cftc_contract_market_code == CFTC_GOLD_CONTRACT_MARKET_CODE)
            .order_by(GoldCotPositionModel.report_date.desc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    def _percentile(value: int | None, sorted_nets: list[int | None]) -> float | None:
        if value is None or not sorted_nets:
            return None
        count = sum(1 for n in sorted_nets if n is not None and n <= value)
        total = sum(1 for n in sorted_nets if n is not None)
        if total == 0:
            return None
        return round(count / total * 100.0, 2)

    # ── Economic calendar (seeded / manual) ──────────────────────────

    async def sync_economic_calendar(self) -> SyncResult:
        """Idempotent upsert of scheduled economic calendar events."""
        started = _utc_now()
        result = SyncResult(job_type="economic_calendar")
        try:
            events = self.calendar_provider.fetch()
        except Exception as exc:  # noqa: BLE001 - calendar is best-effort
            result.errors.append(str(exc))
            result.duration_ms = (_utc_now() - started).total_seconds() * 1000
            return result

        for ev in events:
            event_id = ev.get("event_id")
            if not event_id:
                continue
            existing = await self._get_calendar_event(event_id)
            if existing is not None:
                new_date = _date_from_raw(ev.get("event_date"))
                if new_date is not None and existing.event_date != new_date:
                    # A reschedule is *new information*: the stored date changes
                    # now and ``fetched_at`` records when the new date became
                    # known.  The point-in-time feature block refuses rows whose
                    # content changed after the feature's timestamp, so the new
                    # date is never back-dated into an earlier feature value.
                    existing.event_date = new_date
                    existing.fetched_at = self.clock()
                    result.upserted += 1
                else:
                    result.skipped += 1
                continue
            row = GoldEconomicCalendarEventModel(
                event_id=event_id,
                event_date=_date_from_raw(ev.get("event_date")),
                event_time=ev.get("event_time"),
                title=ev.get("title"),
                country=ev.get("country"),
                category=ev.get("category"),
                importance=ev.get("importance"),
                is_high_volatility=bool(
                    ev.get("is_high_volatility")
                    or str(ev.get("category", "")).upper() in HIGH_VOLATILITY_CATEGORIES
                ),
                source=ev.get("source"),
                fetched_at=self.clock(),
            )
            self.session.add(row)
            result.upserted += 1

        await self.session.commit()
        result.ok = not result.errors or result.upserted > 0
        result.duration_ms = (_utc_now() - started).total_seconds() * 1000
        return result

    async def _get_calendar_event(self, event_id: str) -> GoldEconomicCalendarEventModel | None:
        statement = select(GoldEconomicCalendarEventModel).where(
            GoldEconomicCalendarEventModel.event_id == event_id
        )
        result = await self.session.execute(statement)
        return result.scalars().first()

    # ── Manual Iran events (insert-only, never overwritten) ──────────

    async def insert_iran_manual_event(
        self,
        *,
        event_id: str,
        event_date: date,
        event_time: str | None = None,
        title: str | None = None,
        category: str | None = None,
        importance: int | None = None,
        note: str | None = None,
        is_high_volatility: bool = False,
    ) -> GoldIranManualEventModel:
        """Insert (idempotent by event_id) an Iran-specific manual calendar event."""
        from services.gold.economic_calendar import add_iran_manual_event

        return await add_iran_manual_event(
            self.session,
            event_id=event_id,
            event_date=event_date,
            event_time=event_time,
            title=title,
            category=category,
            importance=importance,
            note=note,
            is_high_volatility=is_high_volatility,
        )

    # ── Tokenized gold (PAXG / XAUT) premium vs spot ─────────────────

    async def sync_tokenized_gold_premium(self) -> SyncResult:
        """Idempotent upsert of tokenized-gold premium against spot.

        The token quote comes from the BrsApi crypto feed (already synced into
        ``brsapi_crypto_prices``) and the spot from the stored gold snapshots,
        so this sync needs no extra market-data subscription.
        """
        started = _utc_now()
        result = SyncResult(job_type="tokenized_gold_premium")

        try:
            quotes = await self.tokenized_gold_provider.fetch()
        except Exception as exc:  # noqa: BLE001 - never crash the scheduler
            result.errors.append(str(exc))
            result.duration_ms = (_utc_now() - started).total_seconds() * 1000
            return result

        try:
            spot = await self.gold_spot_provider.fetch()
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"gold spot: {exc}")
            result.duration_ms = (_utc_now() - started).total_seconds() * 1000
            return result

        if not spot or spot <= 0:
            result.errors.append("gold spot price unavailable — premium not computed")
            result.duration_ms = (_utc_now() - started).total_seconds() * 1000
            return result

        today = self.clock().date().isoformat()
        for quote in quotes:
            ticker = quote.get("ticker")
            price = quote.get("price_usd")
            if not ticker or price is None:
                continue
            premium = compute_tokenized_gold_premium(float(price), spot)
            if premium is None:
                continue
            as_of = quote.get("as_of") or today
            symbol = quote.get("symbol") or ticker
            try:
                stored = await self._store_macro_indicator(
                    indicator=f"{ticker}{PREMIUM_INDICATOR_SUFFIX}",
                    value=premium,
                    as_of=as_of,
                    source="BrsApi",
                    unit="percent",
                    frequency="daily",
                    provenance=(
                        f"BrsApi crypto feed: {symbol} @ {price} USD vs "
                        f"stored spot {spot} USD"
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - one bad row must not kill the job
                result.errors.append(f"{ticker}: {exc}")
                await self._safe_rollback()
                result.upserted = 0
                result.skipped = 0
                continue
            if stored:
                result.upserted += 1
            else:
                result.skipped += 1

        await self.session.commit()
        result.ok = not result.errors or result.upserted > 0
        result.duration_ms = (_utc_now() - started).total_seconds() * 1000
        return result

    # ── Convenience: run all jobs ────────────────────────────────────

    async def sync_all(self) -> dict[str, SyncResult]:
        results: dict[str, SyncResult] = {}
        results["fred"] = await self.sync_fred_indicators()
        results["cftc"] = await self.sync_cftc_cot_gold()
        results["calendar"] = await self.sync_economic_calendar()
        return results


def _date_from_raw(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


__all__ = [
    "MacroSyncService",
    "SyncResult",
    "HIGH_VOLATILITY_CATEGORIES",
    "DEFAULT_STALENESS_SECONDS",
]

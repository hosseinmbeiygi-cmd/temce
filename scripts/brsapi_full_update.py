#!/usr/bin/env python3
"""
BrsApi Full Update Script — v2
================================

Comprehensive updater that:
1. Auto-creates missing database tables before syncing
2. Fetches ALL BrsApi endpoints respecting rate limits
3. **Daily limit: 10,000 requests** (hard stop, regardless of 500/5min limiter)
4. Per-request rate limit: 500 requests / 5 minutes
5. Retries HTTP 502 errors (configurable)
6. Collects ALL errors and reports them grouped by type
7. Skips already-synced data where possible

Usage:
    python scripts/brsapi_full_update.py [--api-key KEY] [--tables TABLE,...]

    --tables:   symbols,index,nav,options,ime,commodity,crypto,
                gold_currency,gold_currency_pro,history,codal,all
    --dry-run:  Show what would be done without executing
    --symbols N:Limit to first N symbols (for testing)
    --retries N: Max retries for 502 errors (default 3)
    --daily-limit N: Max requests per day (default 10000)
    --skip-502:  Skip per-symbol symbols on first 502 instead of retrying (saves daily quota)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import os
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import timedelta
from logging import INFO, FileHandler, Formatter, StreamHandler, getLogger
from typing import Any

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Project imports ──────────────────────────
import core.database as db_module
from brsapi.client import BrsApiClient, get_client
from brsapi.config import BrsApiEndpoints

# ── Model imports ─────────────────────────────
from brsapi.models import (
    CandlestickModel,
    CodalAnnouncementModel,
    CommodityPriceModel,
    CryptoPriceModel,
    GoldCoinPriceModel,
    GoldCurrencyProPriceModel,
    HistoricalDailyModel,
    HistoricalRealLegalModel,
    ImeCertificateModel,
    ImeFundModel,
    ImeFutureModel,
    ImeOptionModel,
    IndexValueModel,
    NavRecordModel,
    OptionSnapshotModel,
    ShareholderRecordModel,
    SymbolDetailModel,
    SymbolSnapshotModel,
)
from brsapi.models.base import BrsApiBase
from brsapi.parsers import (
    CodalParser,
    CommodityParser,
    CryptoParser,
    GoldCurrencyParser,
    ImeParser,
    TsetmcParser,
)
from brsapi.repositories import BulkUpsertRepository
from core.database import get_session

logger = getLogger("brsapi_full_update")

# ──────────────────────────────────────────────
#  Dual Rate Limiter: 500/5min + 10k/day
# ──────────────────────────────────────────────


class DailyRateLimiter:
    """Hard daily limit: max 10,000 requests per rolling 24h window."""

    def __init__(self, daily_max: int = 10000):
        self.daily_max = daily_max
        self._timestamps: deque[float] = deque()
        self._window = timedelta(hours=24)
        self._rejected = 0

    async def acquire(self) -> bool:
        """Return True if request allowed, False if daily limit exceeded."""
        now = time.monotonic()
        cutoff = now - self._window.total_seconds()

        # Prune old timestamps
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

        if len(self._timestamps) >= self.daily_max:
            self._rejected += 1
            wait_until = self._timestamps[0] + self._window.total_seconds()
            wait_seconds = wait_until - now
            if wait_seconds > 0:
                logger.critical(
                    "🚫 DAILY LIMIT REACHED (%d/%d). "
                    "Next request available in %.1f hours (%.1f minutes). "
                    "STOPPING.",
                    len(self._timestamps), self.daily_max,
                    wait_seconds / 3600, wait_seconds / 60,
                )
            return False

        self._timestamps.append(now)
        return True

    @property
    def used_today(self) -> int:
        return len(self._timestamps)

    @property
    def remaining_today(self) -> int:
        return max(0, self.daily_max - self.used_today)

    def summary(self) -> str:
        pct = (self.used_today / self.daily_max * 100) if self.daily_max > 0 else 0
        return f"{self.used_today}/{self.daily_max} ({pct:.1f}%) today, {self._rejected} rejected"


class WindowRateLimiter:
    """Sliding window limiter: max N requests per M seconds (e.g., 500/5min)."""

    def __init__(self, max_requests: int = 500, window_seconds: int = 300):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._total_allowed = 0
        self._total_limited = 0

    async def acquire(self) -> None:
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] > self.window_seconds:
            self._timestamps.popleft()

        if len(self._timestamps) >= self.max_requests:
            sleep_time = self.window_seconds - (now - self._timestamps[0]) + 0.1
            self._total_limited += 1
            logger.warning(
                "⏳ Window limit (%d/%d). Sleeping %.1fs ...",
                len(self._timestamps), self.max_requests, sleep_time,
            )
            await asyncio.sleep(sleep_time)
            return await self.acquire()

        self._timestamps.append(now)
        self._total_allowed += 1

    def summary(self) -> str:
        return f"{self._total_allowed} allowed, {self._total_limited} limited (window ratio: {self._total_limited/max(self._total_allowed,1):.2%})"


class DualRateLimiter:
    """Combines daily + window rate limiting."""

    def __init__(self, daily_max: int = 10000, window_max: int = 500, window_sec: int = 300):
        self.daily = DailyRateLimiter(daily_max=daily_max)
        self.window = WindowRateLimiter(max_requests=window_max, window_seconds=window_sec)

    async def acquire(self) -> bool:
        """Returns False if DAILY limit exceeded (hard stop)."""
        allowed = await self.daily.acquire()
        if not allowed:
            return False
        await self.window.acquire()
        return True

    def summary(self) -> str:
        return f"Daily: {self.daily.summary()} | Window: {self.window.summary()}"


# ──────────────────────────────────────────────
#  Error Collector
# ──────────────────────────────────────────────


@dataclass
class SyncError:
    endpoint: str
    symbol: str = ""
    error_type: str = "Unknown"
    message: str = ""
    timestamp: float = 0.0


class ErrorCollector:
    """Collects all errors for comprehensive final report."""

    def __init__(self):
        self._errors: list[SyncError] = []
        self._counter: Counter = Counter()

    def add(self, endpoint: str, message: str, symbol: str = "", error_type: str = "Unknown"):
        self._errors.append(SyncError(
            endpoint=endpoint, symbol=symbol,
            error_type=error_type, message=message,
            timestamp=time.monotonic(),
        ))
        self._counter[error_type] += 1

    @property
    def total(self) -> int:
        return len(self._errors)

    def report(self) -> str:
        if not self._errors:
            return "✨ No errors! All endpoints synced successfully."

        lines = ["\n" + "═" * 70, "❌ ERROR REPORT", "═" * 70]

        # Summary by type
        lines.append("\n📊 Errors by type:")
        for err_type, count in self._counter.most_common():
            pct = count / len(self._errors) * 100
            lines.append(f"  {err_type}: {count} ({pct:.1f}%)")

        # Top error endpoints
        endpoint_counter = Counter(e.endpoint for e in self._errors)
        lines.append("\n📊 Errors by endpoint:")
        for ep, count in endpoint_counter.most_common(15):
            lines.append(f"  {ep}: {count}")

        # Detailed error samples (limit to avoid flooding)
        lines.append("\n📋 Sample errors (up to 30):")
        for e in self._errors[:30]:
            sym_str = f"({e.symbol})" if e.symbol else ""
            lines.append(f"  [{e.error_type}] {e.endpoint}{sym_str}: {e.message[:120]}")

        if len(self._errors) > 30:
            lines.append(f"  ... and {len(self._errors) - 30} more errors")

        lines.append("═" * 70)
        return "\n".join(lines)


# ──────────────────────────────────────────────
#  DB Helpers
# ──────────────────────────────────────────────


_ALL_MODEL_CLASSES: set[type] = set()


def _collect_models():
    """Collect all model classes that might need tables created."""
    global _ALL_MODEL_CLASSES
    if not _ALL_MODEL_CLASSES:
        for name in dir():
            obj = globals()[name]
            if isinstance(obj, type) and hasattr(obj, '__tablename__') and hasattr(obj, '__table__'):
                _ALL_MODEL_CLASSES.add(obj)
    return _ALL_MODEL_CLASSES


async def ensure_tables_exist(session) -> None:
    """Create any missing database tables for BrsApi models."""
    _collect_models()
    existing = set()
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        existing = {row[0] for row in result}
    except Exception as e:
        logger.warning("Cannot check existing tables: %s — will attempt create_all anyway", e)

    missing = []
    for model in _ALL_MODEL_CLASSES:
        if hasattr(model, '__tablename__') and model.__tablename__ not in existing:
            missing.append(model)

    if missing:
        logger.info("Creating %d missing tables: %s", len(missing),
                     [m.__tablename__ for m in missing])
        # Get the live engine reference from the database module
        db_engine = db_module.engine
        if db_engine is None:
            # Engine not initialized yet — use session bind
            db_engine = session.get_bind()
        try:
            async with db_engine.begin() as conn:
                for model in missing:
                    await conn.run_sync(model.__table__.create)
            logger.info("✅ %d tables created successfully", len(missing))
        except Exception as e:
            logger.warning("Table creation via individual create failed: %s — trying metadata.create_all", e)
            try:
                async with db_engine.begin() as conn:
                    await conn.run_sync(BrsApiBase.metadata.create_all)
                logger.info("✅ All tables via metadata.create_all")
            except Exception as fallback_e:
                logger.error("❌ metadata.create_all fallback also failed: %s", fallback_e)
                for model in missing:
                    logger.debug("  Failed model: %s (%s)", model.__tablename__, model.__name__)
                raise RuntimeError(
                    f"Failed to create {len(missing)} database tables: "
                    f"individual create failed ({e}), "
                    f"metadata.create_all also failed ({fallback_e})"
                ) from fallback_e
    else:
        logger.info("All tables already exist — no creation needed")

    # Safety net: run metadata.create_all for any models that _collect_models missed
    # (e.g. GoldCurrencyProPriceModel if __table__ wasn't available at collection time)
    try:
        db_engine = db_module.engine or session.get_bind()
        async with db_engine.begin() as conn:
            await conn.run_sync(BrsApiBase.metadata.create_all)
    except Exception:
        pass  # Silent — already logged if needed above


async def get_all_symbols(session: Any, limit: int | None = None) -> list[str]:
    from sqlalchemy import select
    stmt = select(SymbolSnapshotModel.symbol).distinct()
    if limit:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return [row[0] for row in result if row[0]]


async def get_existing_history_dates(session: Any, symbol: str) -> set[str]:
    from sqlalchemy import select
    stmt = select(HistoricalDailyModel.date).where(HistoricalDailyModel.symbol == symbol)
    result = await session.execute(stmt)
    return {row[0] for row in result if row[0]}


async def get_existing_codal_codes(session: Any) -> set[str]:
    from sqlalchemy import select
    stmt = select(CodalAnnouncementModel.code)
    result = await session.execute(stmt)
    return {row[0] for row in result if row[0]}


# ──────────────────────────────────────────────
#  Update Runner
# ──────────────────────────────────────────────


@dataclass
class UpdateResult:
    endpoint: str
    success: bool
    items_count: int = 0
    duration_ms: float = 0.0
    error: str | None = None
    skipped: bool = False
    symbol: str = ""


class BrsApiFullUpdater:
    """
    Orchestrates a full update across all BrsApi endpoints,
    respecting dual rate limits (500/5min + 10k/day).
    """

    def __init__(
        self,
        client: BrsApiClient,
        rate_limiter: DualRateLimiter | None = None,
        dry_run: bool = False,
        max_502_retries: int = 3,
        skip_502: bool = False,
    ):
        self._client = client
        self._rate_limiter = rate_limiter or DualRateLimiter()
        self._dry_run = dry_run
        self._max_502_retries = max_502_retries
        self._skip_502 = skip_502
        self._results: list[UpdateResult] = []
        self._errors = ErrorCollector()
        self._start_time = time.monotonic()
        self._skipped_502_count = 0  # counter for skipped per-symbol 502s

    # ── Rate-limited fetch ─────────────────────

    async def _fetch(
        self,
        endpoint: Any,
        label: str,
        params: dict[str, str] | None = None,
        skip_502: bool = False,
    ) -> Any | None:
        """Fetch with dual rate limiting and 502 retry.

        Args:
            skip_502: If True and a 502 is received on the first attempt,
                      skip immediately (no retries). Used for per-symbol
                      endpoints where a 502 likely means "no data" and
                      retrying wastes the daily quota.
        """
        # Daily limit check
        allowed = await self._rate_limiter.acquire()
        if not allowed:
            self._errors.add(endpoint.path if hasattr(endpoint, 'path') else label,
                             "Daily limit exceeded. Stopping.")
            return None

        if self._dry_run:
            logger.info("[DRY-RUN] Would fetch %s %s", label, params or {})
            return None

        # Fetch with 502 retry (or skip on first 502 if skip_502=True)
        last_error = None
        for attempt in range(self._max_502_retries + 1):
            try:
                result = await self._client.fetch(endpoint, params=params)
            except Exception as exc:
                last_error = str(exc)
                self._errors.add(label, last_error, error_type="ClientError")
                return None

            if result.success:
                return result.value.data

            # Check for 502 specifically
            error_msg = result.error or ""
            if "502" in error_msg:
                # skip_502 mode: skip immediately on first 502, no retry
                if skip_502 and attempt == 0:
                    self._skipped_502_count += 1
                    logger.warning("⏭️ %s (502, attempt 1/%d) — skip_502 ON, skipping",
                                   label, self._max_502_retries)
                    last_error = error_msg
                    break

                if attempt < self._max_502_retries:
                    wait = 2 ** (attempt + 1)  # exponential backoff: 2, 4, 8s
                    logger.warning("⚠️ %s (502, attempt %d/%d) — retrying in %ds",
                                   label, attempt + 1, self._max_502_retries, wait)
                    await asyncio.sleep(wait)
                    last_error = error_msg
                    continue

            last_error = error_msg
            if attempt >= self._max_502_retries:
                break

        # All retries exhausted or skipped
        self._errors.add(label, last_error, error_type="FetchFailed")
        self._results.append(
            UpdateResult(endpoint=label, success=False, error=last_error, skipped=skip_502)
        )
        return None

    async def _store(
        self,
        session: Any,
        label: str,
        records: list[dict[str, Any]],
        model_class: type,
        truncate_first: bool = False,
    ) -> int:
        if self._dry_run:
            logger.info("[DRY-RUN] Would store %d records in %s", len(records), label)
            return len(records)
        if not records:
            return 0

        try:
            repo = BulkUpsertRepository(session, model_class)
            if truncate_first:
                try:
                    await repo.truncate()
                except Exception as e:
                    # Table might not exist yet — ensure it exists and retry
                    logger.warning("Truncate failed for %s: %s — ensuring table exists", model_class.__tablename__, e)
                    await ensure_tables_exist(session)
                    await repo.truncate()

            total = 0
            for i in range(0, len(records), 500):
                batch = records[i:i + 500]
                total += await repo.bulk_insert(batch)
            await session.flush()
            return total
        except Exception as e:
            self._errors.add(label, str(e), error_type="DBError")
            raise

    # ── Bulk endpoints ─────────────────────────

    async def _sync_bulk(
        self, session: Any, endpoint: Any, parser_fn: Any,
        model_class: type, label: str,
        params: dict[str, str] | None = None, truncate_first: bool = True,
    ) -> UpdateResult | None:
        start = time.monotonic()
        data = await self._fetch(endpoint, label, params=params)
        if data is None:
            return None

        try:
            records = parser_fn(data)
        except Exception as e:
            self._errors.add(label, f"ParseError: {e}", error_type="ParseError")
            return UpdateResult(
                endpoint=label, success=False, error=f"ParseError: {e}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        if isinstance(records, dict):
            records = [records] if records else []
        if not isinstance(records, list):
            records = list(records) if records else []

        try:
            total = await self._store(session, label, records, model_class,
                                       truncate_first=truncate_first)
        except Exception as e:
            return UpdateResult(
                endpoint=label, success=False, error=f"StoreError: {e}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        elapsed = (time.monotonic() - start) * 1000
        result = UpdateResult(endpoint=label, success=True, items_count=total, duration_ms=elapsed)
        self._results.append(result)
        logger.info("✅ %s → %d records in %.0fms", label, total, elapsed)
        return result

    # ── Per-symbol endpoints ───────────────────

    async def _sync_for_symbols(
        self, session: Any, symbols: list[str], endpoint: Any,
        parser_fn: Any, model_class: type, label: str,
        param_template: dict[str, str],
        limit_symbols: int | None = 50,
        skip_if_missing: bool = True,
    ) -> list[UpdateResult]:
        # Per-symbol endpoints respect skip_502: skip on first 502, no retries
        results: list[UpdateResult] = []
        symbols_to_process = symbols[:limit_symbols] if limit_symbols else symbols

        for idx, symbol in enumerate(symbols_to_process):
            # Check daily limit before each symbol
            if self._rate_limiter.daily.remaining_today <= 0:
                logger.critical("🚫 Daily limit reached! Stopping per-symbol sync.")
                break

            label_sym = f"{label}({symbol})"
            params = dict(param_template)
            if "l18" in params:
                params["l18"] = symbol

            start = time.monotonic()
            data = await self._fetch(endpoint, label_sym, params=params,
                                     skip_502=self._skip_502)
            if data is None:
                results.append(UpdateResult(
                    endpoint=label_sym, success=False, symbol=symbol,
                    error="Fetch failed",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
                continue

            try:
                records = parser_fn(data)
            except Exception as e:
                self._errors.add(label_sym, f"ParseError: {e}", symbol=symbol, error_type="ParseError")
                results.append(UpdateResult(
                    endpoint=label_sym, success=False, symbol=symbol,
                    error=f"ParseError: {e}",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
                continue

            if isinstance(records, dict):
                records = [records] if records else []
            if not isinstance(records, list):
                records = list(records) if records else []

            # Enrich with symbol
            for r in records:
                r["symbol"] = symbol

            try:
                total = await self._store(session, label_sym, records, model_class)
                elapsed = (time.monotonic() - start) * 1000
                result = UpdateResult(
                    endpoint=label_sym, success=True, symbol=symbol,
                    items_count=total, duration_ms=elapsed,
                )
                results.append(result)
                self._results.append(result)
                pct = (idx + 1) / len(symbols_to_process) * 100
                logger.info("[%d/%d (%.0f%%)] %s: %d records in %.0fms",
                            idx + 1, len(symbols_to_process), pct, label_sym, total, elapsed)
            except Exception as e:
                self._errors.add(label_sym, str(e), symbol=symbol, error_type="StoreError")
                results.append(UpdateResult(
                    endpoint=label_sym, success=False, symbol=symbol,
                    error=f"StoreError: {e}",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))

            await asyncio.sleep(0.2)

        return results

    # ── Main run ───────────────────────────────

    async def run(
        self, session: Any,
        tables: set[str] | None = None,
        max_symbols: int | None = None,
    ) -> list[UpdateResult]:
        if tables is None:
            tables = {"symbols", "index", "nav", "options", "ime",
                      "commodity", "crypto", "gold_currency",
                      "gold_currency_pro", "history", "codal"}

        self._start_time = time.monotonic()

        logger.info("=" * 60)
        logger.info("🚀 BrsApi Full Update v2")
        logger.info("   Tables: %s", tables)
        logger.info("   Dry-run: %s", self._dry_run)
        logger.info("   Window limit: 500 req / 5 min")
        logger.info("   Daily limit: %d req / day", self._rate_limiter.daily.daily_max)
        logger.info("   502 retries: %d", self._max_502_retries)
        logger.info("=" * 60)

        # ── Step 0: Ensure all tables exist ─────
        logger.info("📋 Ensuring database tables exist...")
        if not self._dry_run:
            await ensure_tables_exist(session)
            await session.flush()

        # ── Step 1: Bulk endpoints ─────────────

        if "symbols" in tables:
            await self._sync_bulk(session, BrsApiEndpoints.ALL_SYMBOLS,
                                  TsetmcParser.parse_all_symbols,
                                  SymbolSnapshotModel, "AllSymbols",
                                  truncate_first=False  # upsert, don't destroy existing data
                                  )

            if self._rate_limiter.daily.remaining_today <= 0:
                return self._finalize()

        if "index" in tables:
            await self._sync_bulk(session, BrsApiEndpoints.INDEX,
                                  TsetmcParser.parse_index,
                                  IndexValueModel, "Index(type=1)",
                                  params={"type": "1"})
            await self._sync_bulk(session, BrsApiEndpoints.INDEX,
                                  TsetmcParser.parse_index,
                                  IndexValueModel, "Index(type=2)",
                                  params={"type": "2"})

        if "options" in tables:
            await self._sync_bulk(session, BrsApiEndpoints.OPTION,
                                  TsetmcParser.parse_options,
                                  OptionSnapshotModel, "Options(TSETMC)")

        if "ime" in tables:
            await self._sync_bulk(session, BrsApiEndpoints.IME_FUTURES,
                                  ImeParser.parse_futures, ImeFutureModel, "IME_Futures")
            await self._sync_bulk(session, BrsApiEndpoints.IME_OPTION,
                                  ImeParser.parse_options, ImeOptionModel, "IME_Options")
            await self._sync_bulk(session, BrsApiEndpoints.IME_CERTIFICATE,
                                  ImeParser.parse_certificates, ImeCertificateModel, "IME_Certificates")
            await self._sync_bulk(session, BrsApiEndpoints.IME_FUND,
                                  ImeParser.parse_funds, ImeFundModel, "IME_Funds")

        if "commodity" in tables:
            await self._sync_bulk(session, BrsApiEndpoints.COMMODITY,
                                  CommodityParser.parse, CommodityPriceModel, "Commodities")

        if "crypto" in tables:
            await self._sync_bulk(session, BrsApiEndpoints.CRYPTOCURRENCY,
                                  CryptoParser.parse, CryptoPriceModel, "Cryptocurrencies")

        if "gold_currency" in tables:
            await self._sync_bulk(session, BrsApiEndpoints.GOLD_CURRENCY,
                                  GoldCurrencyParser.parse_gold, GoldCoinPriceModel,
                                  "Gold_Currency/gold", params=None)

        # ── Gold_Currency_Pro: use sync_service (with daily limit) ─
        if "gold_currency_pro" in tables:
            if self._dry_run:
                logger.info("[DRY-RUN] Would sync Gold_Currency_Pro: section=gold|currency|cryptocurrency, then 24h history + daily history per-symbol")
                svc = None
            else:
                # Ensure tables exist before sync_service truncates
                await ensure_tables_exist(session)
                # Create sync service once; reused for prices + history below
                from brsapi.services.sync_service import BrsApiSyncService
                svc = BrsApiSyncService(client=self._client)
                # Check daily limit first (sync_service doesn't use _fetch)
                allowed = await self._rate_limiter.acquire()
                if not allowed:
                    logger.critical("Daily limit reached before Gold_Currency_Pro sync")
                    svc = None
                else:
                    try:
                        pro_reports = await svc.sync_gold_currency_pro(session)
                        for r in pro_reports:
                            self._results.append(UpdateResult(
                                endpoint=r.endpoint, success=r.success,
                                items_count=r.items_count, error=r.error))
                            if not r.success:
                                self._errors.add(r.endpoint, r.error or "unknown", error_type="ProSyncError")
                            logger.info("   Gold_Currency_Pro/%s: %s (%d items)",
                                        r.endpoint, "OK" if r.success else "FAIL", r.items_count)
                        await session.flush()
                    except Exception as e:
                        self._errors.add("Gold_Currency_Pro", str(e), error_type="ProSyncError")
                        logger.exception("Gold_Currency_Pro sync failed: %s", e)
                        svc = None

            # ── Gold_Currency_Pro 24h history (per-symbol) ──
            if svc is not None and self._rate_limiter.daily.remaining_today > 10:
                try:
                    from sqlalchemy import distinct, select
                    stmt = select(distinct(GoldCurrencyProPriceModel.symbol)).limit(10)
                    result = await session.execute(stmt)
                    pro_symbols = [row[0] for row in result if row[0]]
                    if pro_symbols:
                        logger.info("Syncing 24h history for %d Pro symbols", len(pro_symbols))
                        for psym in pro_symbols:
                            if self._rate_limiter.daily.remaining_today <= 2:
                                break
                            allowed = await self._rate_limiter.acquire()
                            if not allowed:
                                break
                            try:
                                report_24h = await svc.sync_gold_currency_pro_history_24h(session, symbol=psym)
                                logger.info("   Pro history_24h/%s: %s (%d items)",
                                            psym, "OK" if report_24h.success else "FAIL", report_24h.items_count)
                            except Exception as exc:
                                self._errors.add(f"Pro_24h({psym})", str(exc), error_type="ProHistory24hError")
                                logger.warning("   Pro history_24h/%s failed: %s", psym, exc)
                            await asyncio.sleep(0.3)

                        # ── Gold_Currency_Pro daily history ──
                        logger.info("Syncing daily history for %d Pro symbols", len(pro_symbols))
                        for psym in pro_symbols:
                            if self._rate_limiter.daily.remaining_today <= 2:
                                break
                            allowed = await self._rate_limiter.acquire()
                            if not allowed:
                                break
                            try:
                                report_daily = await svc.sync_gold_currency_pro_daily_history(session, symbol=psym)
                                logger.info("   Pro daily_history/%s: %s (%d items)",
                                            psym, "OK" if report_daily.success else "FAIL", report_daily.items_count)
                            except Exception as exc:
                                self._errors.add(f"Pro_Daily({psym})", str(exc), error_type="ProDailyHistoryError")
                                logger.warning("   Pro daily_history/%s failed: %s", psym, exc)
                            await asyncio.sleep(0.3)
                    else:
                        logger.info("No Pro symbols available for history sync")
                except Exception as e:
                    self._errors.add("Gold_Currency_Pro_History", str(e), error_type="ProHistoryError")
                    logger.warning("Gold_Currency_Pro history sync failed: %s", e)

        # Commit bulk operations
        if not self._dry_run:
            try:
                await session.commit()
                logger.info("✅ Bulk operations committed")
            except Exception as e:
                await session.rollback()
                self._errors.add("commit", str(e), error_type="CommitError")
                logger.error("❌ Bulk commit failed: %s", e)

        # ── Step 2: Per-symbol endpoints ──────
        if self._rate_limiter.daily.remaining_today <= 0:
            return self._finalize()

        symbols = await get_all_symbols(session, limit=max_symbols)
        if not symbols:
            logger.warning("⚠️  No symbols found in DB. Skipping per-symbol endpoints.")
        else:
            logger.info("📋 Processing %d symbols for per-symbol endpoints (daily remaining: %d)",
                        len(symbols), self._rate_limiter.daily.remaining_today)

            if "nav" in tables:
                await self._sync_for_symbols(
                    session, symbols, BrsApiEndpoints.NAV,
                    TsetmcParser.parse_nav, NavRecordModel,
                    "NAV", {"l18": ""}, limit_symbols=min(200, self._rate_limiter.daily.remaining_today // 2))

            if "symbols" in tables:
                await self._sync_for_symbols(
                    session, symbols, BrsApiEndpoints.SYMBOL_DETAIL,
                    TsetmcParser.parse_symbol_detail, SymbolDetailModel,
                    "SymbolDetail", {"l18": ""}, limit_symbols=min(500, self._rate_limiter.daily.remaining_today // 3))

                await self._sync_for_symbols(
                    session, symbols, BrsApiEndpoints.SHAREHOLDER,
                    TsetmcParser.parse_shareholders, ShareholderRecordModel,
                    "Shareholder", {"l18": ""}, limit_symbols=min(200, self._rate_limiter.daily.remaining_today // 3))

            if "history" in tables:
                await self._sync_for_symbols(
                    session, symbols, BrsApiEndpoints.CANDLESTICK,
                    TsetmcParser.parse_candlesticks, CandlestickModel,
                    "Candlestick", {"l18": "", "type": "3"},
                    limit_symbols=min(100, self._rate_limiter.daily.remaining_today // 3))

                await self._sync_for_symbols(
                    session, symbols, BrsApiEndpoints.HISTORY_PRICE,
                    TsetmcParser.parse_history_price, HistoricalDailyModel,
                    "HistoryPrice", {"l18": "", "type": "0"},
                    limit_symbols=min(50, self._rate_limiter.daily.remaining_today // 3))

                await self._sync_for_symbols(
                    session, symbols, BrsApiEndpoints.HISTORY_REALLEGAL,
                    TsetmcParser.parse_history_real_legal, HistoricalRealLegalModel,
                    "HistoryRealLegal", {"l18": "", "type": "1"},
                    limit_symbols=min(50, self._rate_limiter.daily.remaining_today // 3))

        # ── Step 3: Codal ─────────────────────
        if "codal" in tables and self._rate_limiter.daily.remaining_today > 0:
            await self._sync_codal(session)

        # Final commit
        if not self._dry_run:
            try:
                await session.commit()
                logger.info("✅ All changes committed")
            except Exception as e:
                await session.rollback()
                self._errors.add("final_commit", str(e), error_type="CommitError")
                logger.error("❌ Final commit failed: %s", e)

        return self._finalize()

    def _finalize(self) -> list[UpdateResult]:
        """Print summary and return results."""
        elapsed = time.monotonic() - self._start_time
        success_count = sum(1 for r in self._results if r.success)
        total_items = sum(r.items_count for r in self._results)

        logger.info("")
        logger.info("=" * 70)
        logger.info("🏁 COMPLETE in %.1fs (%.1f minutes)", elapsed, elapsed / 60)
        logger.info("   %s", self._rate_limiter.summary())
        logger.info("   Results: ✅ %d success | ❌ %d failed | 📦 %d items | 📊 %d total ops",
                    success_count, len(self._results) - success_count,
                    total_items, len(self._results))
        if self._skip_502 and self._skipped_502_count > 0:
            logger.info("   ⏭️  Per-symbol 502s skipped: %d (saved ~%d retry requests)",
                        self._skipped_502_count,
                        self._skipped_502_count * self._max_502_retries)

        if self._errors.total > 0:
            logger.info("   ❌ Total errors: %d", self._errors.total)
            logger.info("   %s", self._errors.report())
        else:
            logger.info("   ✨ No errors!")

        logger.info("=" * 70)
        return self._results

    async def _sync_codal(self, session: Any) -> UpdateResult | None:
        start = time.monotonic()
        existing_codes = await get_existing_codal_codes(session)
        total_new = 0
        page = 1
        max_pages = 10

        while page <= max_pages:
            if self._rate_limiter.daily.remaining_today <= 0:
                break

            label = f"Codal(page={page})"
            data = await self._fetch(BrsApiEndpoints.CODAL_ANNOUNCEMENT, label,
                                      params={"page": str(page)})
            if data is None:
                break

            try:
                parsed = CodalParser.parse(data)
                announcements = parsed.get("announcements", [])
            except Exception as e:
                self._errors.add(label, f"ParseError: {e}", error_type="ParseError")
                break

            if not announcements:
                logger.info("📄 No more Codal at page %d", page)
                break

            new_records = [a for a in announcements if a.get("code", "") not in existing_codes]
            if new_records:
                stored = await self._store(session, label, new_records, CodalAnnouncementModel)
                total_new += stored
                for a in new_records:
                    if a.get("code"):
                        existing_codes.add(a["code"])
                logger.info("   → %d new (page %d)", stored, page)
            else:
                logger.info("   → No new on page %d", page)

            if parsed.get("count_page", 0) <= page:
                break
            page += 1
            await asyncio.sleep(0.5)

        elapsed = (time.monotonic() - start) * 1000
        result = UpdateResult(endpoint="Codal", success=True, items_count=total_new, duration_ms=elapsed)
        self._results.append(result)
        logger.info("✅ Codal → %d new in %.0fms", total_new, elapsed)
        return result


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────


async def main():
    parser = argparse.ArgumentParser(description="BrsApi Full Update v2 — 10k/day limit, error reporting, auto-create tables")
    parser.add_argument("--api-key", help="BrsApi API key (or BRSAPI_API_KEY env)")
    parser.add_argument("--tables", default="all",
                        help="Comma-separated: symbols,index,nav,options,ime,commodity,crypto,"
                             "gold_currency,gold_currency_pro,history,codal")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--symbols", type=int, default=None, help="Limit to N symbols")
    parser.add_argument("--retries", type=int, default=3, help="Max retries for 502 errors (default: 3)")
    parser.add_argument("--daily-limit", type=int, default=10000, help="Max requests per day (default: 10000)")
    parser.add_argument("--skip-502", action="store_true",
                        help="Skip per-symbol endpoints on first 502 (no retry, saves daily quota)")
    parser.add_argument("--log-file", type=str,
                        help="Path to log file (UTF-8). Bypasses Windows console encoding issues with emoji.")
    args = parser.parse_args()

    if args.api_key:
        os.environ["BRSAPI_API_KEY"] = args.api_key

    table_groups = {"symbols", "index", "nav", "options", "ime",
                    "commodity", "crypto", "gold_currency",
                    "gold_currency_pro", "history", "codal"}
    if args.tables != "all":
        table_groups = set(args.tables.split(","))

        # ── Fix Windows console encoding for emoji ──
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # Python 3.7+
        except Exception:
            with contextlib.suppress(Exception):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    # Setup root logger
    root = getLogger()
    root.setLevel(INFO)

    formatter = Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")

    # Console handler (encoding fixed above; emoji now works on Windows)
    console = StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Optional file handler (always UTF-8, no emoji issues)
    if args.log_file:
        try:
            log_dir = os.path.dirname(args.log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            file_handler = FileHandler(args.log_file, mode="w", encoding="utf-8")
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
            print(f"[INFO] Logging to file: {args.log_file}", flush=True)
        except Exception as e:
            print(f"[WARN] Cannot create log file {args.log_file}: {e}", flush=True)

    logger.info("🚀 Starting BrsApi Full Update v2")
    logger.info("   Daily limit: %d requests", args.daily_limit)
    logger.info("   Window limit: 500 req / 5 min")
    logger.info("   502 retries: %d", args.retries)
    logger.info("   Skip-502: %s", args.skip_502)

    client = await get_client()
    limiter = DualRateLimiter(daily_max=args.daily_limit, window_max=500, window_sec=300)
    updater = BrsApiFullUpdater(
        client=client,
        rate_limiter=limiter,
        dry_run=args.dry_run,
        max_502_retries=args.retries,
        skip_502=args.skip_502,
    )

    async for session in get_session():
        await updater.run(session, tables=table_groups, max_symbols=args.symbols)

    await client.stop()
    logger.info("👋 Done. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())

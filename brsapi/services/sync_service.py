"""
BrsApi Sync Service
===================

Orchestrates the full data-fetch pipeline:
1. Call the BrsApi endpoint (via ``BrsApiClient``)
2. Parse the response (via parser classes)
3. Store parsed records in the database (via repositories)
4. Log the sync operation (via ``SyncLogRepository``)
5. Optionally store raw payloads for audit

Supports dedup: skips re-fetching if a recent sync already exists.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from logging import getLogger
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.client import BrsApiClient, BrsApiResponse, get_client
from brsapi.config import BrsApiEndpoints, EndpointConfig
from brsapi.constants import BRSAPI_ETF_SYMBOLS
from brsapi.models import (
    CandlestickModel,
    CodalAnnouncementModel,
    CommodityPriceModel,
    CryptoPriceModel,
    CurrencyPriceModel,
    GoldCoinPriceModel,
    GoldCurrencyProDailyHistoryModel,
    GoldCurrencyProHistory24hModel,
    GoldCurrencyProPriceModel,
    HistoricalDailyModel,
    HistoricalRealLegalModel,
    ImeCertificateModel,
    ImeFundModel,
    ImeFutureModel,
    ImeOptionModel,
    ImePhysicalTradeModel,
    IndexValueModel,
    IntradayTradeModel,
    NavRecordModel,
    OptionSnapshotModel,
    ShareholderRecordModel,
    SymbolDetailModel,
    SymbolSnapshotModel,
)
from brsapi.parsers import (
    CodalParser,
    CommodityParser,
    CryptoParser,
    CurrencyParser,
    GoldCoinParser,
    GoldCurrencyParser,
    GoldCurrencyProParser,
    ImeParser,
    TsetmcParser,
)
from brsapi.repositories import (
    BulkUpsertRepository,
    RawPayloadRepository,
    SyncLogRepository,
)

logger = getLogger(__name__)


def _to_jalali_date(value: str | None) -> str | None:
    """Convert a Gregorian ``YYYY-MM-DD`` date to Jalali (Shamsi) format.

    BrsApi TSETMC endpoints (e.g. ``/Tsetmc/Transaction.php``) expect the
    ``date`` parameter in the Persian calendar (e.g. ``1404-02-22``), NOT the
    Gregorian one. This helper:

    - Returns already-Jalali dates untouched (year 1200–1500 is treated as Jalali).
    - Converts Gregorian dates via ``jdatetime``.
    - Returns the (stripped) input unchanged when the value is unparseable.

    Example:
        _to_jalali_date("2026-08-04")  → "1405-05-13"
        _to_jalali_date("1404-02-22")  → "1404-02-22"
    """
    if not value:
        return value
    v = value.strip()
    if not v:
        return v
    # Jalali (Shamsi) years are 1200–1500 (currently 1405); Gregorian here are 20xx.
    # Only treat full YYYY-MM-DD values as Jalali to avoid passing garbage through.
    if len(v) == 10 and v[:4].isdigit() and 1200 <= int(v[:4]) <= 1500:
        return v
    try:
        from datetime import datetime

        import jdatetime

        gdate = datetime.strptime(v, "%Y-%m-%d").date()
        return jdatetime.date.fromgregorian(date=gdate).strftime("%Y-%m-%d")
    except Exception:
        logger.warning("Could not convert date %r to Jalali; passing through", value)
        return value


def _dedupe_symbols(symbols: list[str]) -> list[str]:
    """Return a deduplicated list of non-empty, stripped symbols, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in symbols:
        symbol = raw.strip() if raw else ""
        if symbol and symbol not in seen:
            seen.add(symbol)
            result.append(symbol)
    return result


# ──────────────────────────────────────────────
#  Sync Report
# ──────────────────────────────────────────────


@dataclass
class SyncReport:
    """Outcome of a single sync operation."""
    endpoint: str
    success: bool
    items_count: int = 0
    duration_ms: float = 0.0
    error: str | None = None
    skipped: bool = False       # True when dedup prevented a fetch
    failed_symbols: list[str] = field(default_factory=list)  # Symbols that failed during batch sync


# ──────────────────────────────────────────────
#  Sync Service
# ──────────────────────────────────────────────


class BrsApiSyncService:
    """
    High-level sync orchestrator.

    Usage::

        service = BrsApiSyncService(client, session)
        report = await service.sync_all_symbols()
        report = await service.sync_index()
        report = await service.sync_commodities()

        # Or sync everything
        reports = await service.sync_all()
    """

    def __init__(
        self,
        client: BrsApiClient | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self._client = client
        self._session = session
        self._sync_log: SyncLogRepository | None = None
        self._raw_payload: RawPayloadRepository | None = None

    # ── Lazy deps ──────────────────────────────────

    async def _ensure_client(self) -> BrsApiClient:
        if self._client is None:
            self._client = await get_client()
        return self._client

    def _ensure_repos(self, session: AsyncSession) -> tuple[SyncLogRepository, RawPayloadRepository]:
        if self._sync_log is None or self._sync_log.session is not session:
            self._sync_log = SyncLogRepository(session)
        if self._raw_payload is None or self._raw_payload.session is not session:
            self._raw_payload = RawPayloadRepository(session)
        return self._sync_log, self._raw_payload

    # ── Generic sync ───────────────────────────────

    async def sync(
        self,
        endpoint: EndpointConfig,
        parser: Callable[[Any], Any],
        model_class: type,
        params: dict[str, str] | None = None,
        category_override: str | None = None,
        batch_size: int = 500,
        dedup_seconds: int = 0,          # 0 = always fetch
        truncate_first: bool = False,     # True for full-refresh endpoints
        session: AsyncSession | None = None,
    ) -> SyncReport:
        """
        Generic sync pipeline.

        1. Check dedup (skip if recently synced)
        2. Fetch from API
        3. Parse response
        4. Store in DB
        5. Log result
        """
        start = time.monotonic()
        client = await self._ensure_client()
        sess = session or self._session

        if sess is None:
            raise RuntimeError("BrsApiSyncService: no session available")

        sync_log, raw_payload = self._ensure_repos(sess)

        # 1. Dedup check
        if dedup_seconds > 0 and not params:
            needs = await sync_log.needs_sync(endpoint.path, dedup_seconds)
            if not needs:
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.debug("Skipped %s (recent sync exists)", endpoint.path)
                return SyncReport(
                    endpoint=endpoint.path,
                    success=True,
                    skipped=True,
                    duration_ms=elapsed_ms,
                )

        # 2. Fetch
        result = await client.fetch(endpoint, params=params, category_override=category_override)
        if not result.success:
            elapsed_ms = (time.monotonic() - start) * 1000
            await sync_log.record(
                endpoint=endpoint.path,
                category=category_override or endpoint.category.value,
                status="error",
                error_message=result.error,
                duration_ms=elapsed_ms,
                params=params,
            )
            await sess.commit()
            return SyncReport(
                endpoint=endpoint.path,
                success=False,
                error=result.error,
                duration_ms=elapsed_ms,
            )

        brs_resp: BrsApiResponse = result.value

        if brs_resp.is_empty:
            elapsed_ms = (time.monotonic() - start) * 1000
            await sync_log.record(
                endpoint=endpoint.path,
                category=category_override or endpoint.category.value,
                status="success",
                items_count=0,
                duration_ms=elapsed_ms,
                params=params,
            )
            return SyncReport(
                endpoint=endpoint.path,
                success=True,
                items_count=0,
                duration_ms=elapsed_ms,
            )

        # 3. Parse (support both sync and async parsers)
        try:
            parsed = parser(brs_resp.data)
            if asyncio.iscoroutine(parsed):
                parsed = await parsed
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.exception("Parse error for %s", endpoint.path)
            await sync_log.record(
                endpoint=endpoint.path,
                category=category_override or endpoint.category.value,
                status="error",
                error_message=f"ParseError: {exc}",
                duration_ms=elapsed_ms,
                params=params,
            )
            await sess.commit()
            return SyncReport(
                endpoint=endpoint.path,
                success=False,
                error=f"ParseError: {exc}",
                duration_ms=elapsed_ms,
            )

        # Normalise to list
        records: list[dict[str, Any]]
        if isinstance(parsed, dict):
            records = [parsed] if parsed else []
        elif isinstance(parsed, list):
            records = parsed
        else:
            records = []

        if not records:
            elapsed_ms = (time.monotonic() - start) * 1000
            await sync_log.record(
                endpoint=endpoint.path,
                category=category_override or endpoint.category.value,
                status="success",
                items_count=0,
                duration_ms=elapsed_ms,
                params=params,
            )
            return SyncReport(
                endpoint=endpoint.path,
                success=True,
                items_count=0,
                duration_ms=elapsed_ms,
            )

        # 4. Store
        repo = BulkUpsertRepository(sess, model_class)

        # Snapshots carry the (symbol, fetched_at) unique constraint — refresh
        # on conflict instead of silently appending a duplicate row.
        on_conflict_update = model_class is SymbolSnapshotModel
        conflict_target = ["symbol", "fetched_at"] if on_conflict_update else None

        try:
            if truncate_first:
                await repo.truncate()

            # Batch insert
            total = 0
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                inserted = await repo.bulk_insert(
                    batch,
                    on_conflict_update=on_conflict_update,
                    conflict_target=conflict_target,
                )
                total += inserted

            await sess.commit()

        except Exception as exc:
            await sess.rollback()
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.exception("DB insert error for %s", endpoint.path)
            await sync_log.record(
                endpoint=endpoint.path,
                category=category_override or endpoint.category.value,
                status="error",
                error_message=f"DBError: {exc}",
                items_count=len(records),
                duration_ms=elapsed_ms,
                params=params,
            )
            await sess.commit()
            return SyncReport(
                endpoint=endpoint.path,
                success=False,
                error=f"DBError: {exc}",
                duration_ms=elapsed_ms,
            )

        # 5. Raw payload (optional)
        if brs_resp.raw_bytes is not None:
            try:
                await raw_payload.store(
                    endpoint=endpoint.path,
                    payload=brs_resp.raw_bytes.decode("utf-8", errors="replace"),
                    status_code=brs_resp.status_code,
                    params=params,
                )
                await sess.flush()
            except Exception:
                logger.warning("Failed to store raw payload for %s", endpoint.path, exc_info=True)

        elapsed_ms = (time.monotonic() - start) * 1000
        await sync_log.record(
            endpoint=endpoint.path,
            category=category_override or endpoint.category.value,
            status="success",
            items_count=total,
            duration_ms=elapsed_ms,
            params=params,
        )
        await sess.commit()

        logger.info("Synced %s → %d records in %.0fms", endpoint.path, total, elapsed_ms)
        return SyncReport(
            endpoint=endpoint.path,
            success=True,
            items_count=total,
            duration_ms=elapsed_ms,
        )

    # ── Convenience sync methods ──────────────────

    async def sync_all_symbols(
        self, session: AsyncSession, symbol_type: str = "1"
    ) -> SyncReport:
        """Sync all TSETMC symbols (AllSymbols)."""
        return await self.sync(
            endpoint=BrsApiEndpoints.ALL_SYMBOLS,
            parser=TsetmcParser.parse_all_symbols,
            model_class=SymbolSnapshotModel,
            params={"type": symbol_type},
            dedup_seconds=30,
            truncate_first=False,  # upsert — don't destroy existing data
            session=session,
        )

    async def sync_index(
        self, session: AsyncSession, index_type: str = "1"
    ) -> SyncReport:
        """Sync market index values."""
        return await self.sync(
            endpoint=BrsApiEndpoints.INDEX,
            parser=TsetmcParser.parse_index,
            model_class=IndexValueModel,
            params={"type": index_type},
            dedup_seconds=30,
            session=session,
        )

    async def sync_commodities(self, session: AsyncSession) -> SyncReport:
        """Sync global commodity prices."""
        return await self.sync(
            endpoint=BrsApiEndpoints.COMMODITY,
            parser=CommodityParser.parse,
            model_class=CommodityPriceModel,
            params=None,
            dedup_seconds=30,
            session=session,
        )

    async def sync_crypto(self, session: AsyncSession) -> SyncReport:
        """Sync cryptocurrency prices."""
        return await self.sync(
            endpoint=BrsApiEndpoints.CRYPTOCURRENCY,
            parser=CryptoParser.parse,
            model_class=CryptoPriceModel,
            params=None,
            dedup_seconds=30,
            session=session,
        )

    # ── NAV ─────────────────────────────────────────
    async def sync_nav(
        self, session: AsyncSession, symbol: str
    ) -> SyncReport:
        """Sync NAV for a given ETF symbol."""
        ins_id = await self._lookup_ins_id(session, symbol)

        def _parse_with_ins_id(data: Any) -> list[dict[str, Any]]:
            rec = TsetmcParser.parse_nav(data)
            if rec:
                rec["symbol"] = symbol
                if ins_id:
                    rec["ins_id"] = ins_id
            return rec

        return await self.sync(
            endpoint=BrsApiEndpoints.NAV,
            parser=_parse_with_ins_id,
            model_class=NavRecordModel,
            params={"l18": symbol},
            session=session,
        )

    async def sync_nav_all(
        self,
        session: AsyncSession,
        symbols: list[str] | None = None,
        sleep_seconds: float = 11.0,
    ) -> SyncReport:
        """
        Sync NAV for a list of ETF/fund symbols sequentially.

        Args:
            session: Database session.
            symbols: List of symbols to sync. If None, queries the DB for
                symbols whose sector contains "صندوق" or "fund".
            sleep_seconds: Delay between requests to respect the NAV endpoint
                rate limit (1 req / 10s → default 11s).
        """
        if symbols is None:
            symbols = await self._get_fund_symbols(session)

        # Drop empty/whitespace-only symbols silently
        symbols = [s for s in symbols if s and str(s).strip()]

        if not symbols:
            return SyncReport(
                endpoint=BrsApiEndpoints.NAV.path,
                success=True,
                items_count=0,
                error="No fund symbols found",
            )

        start_time = time.monotonic()
        success_count = 0
        fail_count = 0
        total_items = 0
        failed_symbols: list[str] = []

        symbols = _dedupe_symbols(symbols)

        for i, symbol in enumerate(symbols):
            if i > 0 and sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)

            try:
                report = await self.sync_nav(session, symbol)
                if report.success:
                    success_count += 1
                    total_items += report.items_count
                else:
                    fail_count += 1
                    failed_symbols.append(symbol)
                    logger.warning("NAV sync failed for %s: %s", symbol, report.error)
            except Exception:
                fail_count += 1
                failed_symbols.append(symbol)
                logger.exception("NAV sync exception for %s", symbol)

            if (i + 1) % 10 == 0:
                logger.info(
                    "NAV sync progress: %d/%d symbols (%d ok, %d fail)",
                    i + 1,
                    len(symbols),
                    success_count,
                    fail_count,
                )

        duration_ms = (time.monotonic() - start_time) * 1000
        success = fail_count == 0
        error: str | None = None
        if not success:
            shown = failed_symbols[:10]
            suffix = f" and {len(failed_symbols) - 10} more" if len(failed_symbols) > 10 else ""
            error = f"{fail_count} symbols failed: {', '.join(shown)}{suffix}"

        return SyncReport(
            endpoint=BrsApiEndpoints.NAV.path,
            success=success,
            items_count=total_items,
            duration_ms=duration_ms,
            error=error,
            failed_symbols=failed_symbols,
        )

    async def _get_fund_symbols(self, session: AsyncSession) -> list[str]:
        """Return a list of fund/ETF symbols from the latest snapshots.

        First attempts to identify funds dynamically from the symbol snapshots
        table by sector name. The result is then combined (union) with the
        curated ``BRSAPI_ETF_SYMBOLS`` list so the NAV sync job is never left
        with an empty symbol list and newly-listed funds discovered by sector
        are still synced.
        """
        from sqlalchemy import func, select

        from brsapi.models import SymbolSnapshotModel

        db_symbols: list[str] = []
        try:
            # Try to identify funds by sector name containing "صندوق" or "fund"
            sector_col = SymbolSnapshotModel.sector
            stmt = (
                select(SymbolSnapshotModel.symbol)
                .where(
                    (sector_col.ilike("%صندوق%")) |
                    (func.lower(sector_col).like("%fund%")) |
                    (func.lower(sector_col).like("%etf%"))
                )
                .group_by(SymbolSnapshotModel.symbol)
            )
            result = await session.execute(stmt)
            db_symbols = [row[0] for row in result.fetchall() if row[0]]
            logger.info("Found %d fund symbols from snapshots", len(db_symbols))
        except Exception:
            logger.warning("Could not query fund symbols from snapshots; using hardcoded ETF list", exc_info=True)

        # Build a union of DB-discovered funds and the curated ETF list,
        # preserving the curated order while appending any extra DB symbols.
        return _dedupe_symbols(db_symbols + BRSAPI_ETF_SYMBOLS)

    # ── Transactions ─────────────────────────────────
    async def sync_transactions(
        self, session: AsyncSession, symbol: str, date: str | None = None
    ) -> SyncReport:
        """Sync intraday trades (ریز معاملات) for a symbol.

        BrsApi expects the ``date`` parameter in **Jalali (Shamsi)** format
        (e.g. ``1404-02-22``). Gregorian input (``2026-08-04``) is converted
        automatically via :func:`_to_jalali_date`.
        """
        ins_id = await self._lookup_ins_id(session, symbol)
        params = {"l18": symbol}
        if date:
            params["date"] = _to_jalali_date(date)

        def _parse_with_ins_id(data: Any) -> list[dict[str, Any]]:
            records = TsetmcParser.parse_transactions(data)
            for r in records:
                # ``id`` from the API is a per-symbol counter (starts at 1 for
                # every symbol) — using it as the PK would collide across
                # symbols and get dropped by ON CONFLICT DO NOTHING. Let the
                # DB autoincrement the PK instead.
                r.pop("id", None)
                r["symbol"] = symbol
                # The requested date (Jalali) is what the trades belong to.
                r["trade_date"] = params.get("date") or ""
                if ins_id:
                    r["ins_id"] = ins_id
            return records

        return await self.sync(
            endpoint=BrsApiEndpoints.TRANSACTION,
            parser=_parse_with_ins_id,
            model_class=IntradayTradeModel,
            params=params,
            session=session,
        )

    # ── History (Price) ─────────────────────────────
    async def _lookup_ins_id(
        self, session: AsyncSession, symbol: str
    ) -> str | None:
        """Look up TSETMC internal ``ins_id`` for a given symbol."""
        from sqlalchemy import select

        stmt = (
            select(SymbolSnapshotModel.ins_id)
            .where(SymbolSnapshotModel.symbol == symbol)
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            # Fall back to SymbolDetailModel
            from brsapi.models import SymbolDetailModel
            stmt2 = (
                select(SymbolDetailModel.ins_id)
                .where(SymbolDetailModel.symbol == symbol)
                .limit(1)
            )
            result2 = await session.execute(stmt2)
            row = result2.scalar_one_or_none()
        return str(row) if row else None

    async def sync_history_price(
        self, session: AsyncSession, symbol: str
    ) -> SyncReport:
        """Sync daily historical prices for a symbol."""

        ins_id = await self._lookup_ins_id(session, symbol)

        def _parse_with_symbol(data: Any) -> list[dict[str, Any]]:
            records = TsetmcParser.parse_history_price(data)
            for r in records:
                r["symbol"] = symbol
                if ins_id:
                    r["ins_id"] = ins_id
            return records

        return await self.sync(
            endpoint=BrsApiEndpoints.HISTORY_PRICE,
            parser=_parse_with_symbol,
            model_class=HistoricalDailyModel,
            params={"l18": symbol, "type": "0"},
            session=session,
        )

    # ── History (Real/Legal) ───────────────────────
    async def sync_history_real_legal(
        self, session: AsyncSession, symbol: str
    ) -> SyncReport:
        """Sync daily real/legal breakdown for a symbol."""

        ins_id = await self._lookup_ins_id(session, symbol)

        def _parse_with_symbol_rl(data: Any) -> list[dict[str, Any]]:
            records = TsetmcParser.parse_history_real_legal(data)
            for r in records:
                r["symbol"] = symbol
                if ins_id:
                    r["ins_id"] = ins_id
            return records

        return await self.sync(
            endpoint=BrsApiEndpoints.HISTORY_REALLEGAL,
            parser=_parse_with_symbol_rl,
            model_class=HistoricalRealLegalModel,
            params={"l18": symbol, "type": "1"},
            session=session,
        )

    # ── Symbol Detail ───────────────────────────────
    async def sync_symbol_detail(
        self, session: AsyncSession, symbol: str
    ) -> SyncReport:
        """Sync enriched detail for a single symbol."""
        ins_id = await self._lookup_ins_id(session, symbol)

        def _parse_with_ins_id(data: Any) -> dict[str, Any] | None:
            rec = TsetmcParser.parse_symbol_detail(data)
            if rec and ins_id:
                rec["ins_id"] = ins_id
            return rec

        return await self.sync(
            endpoint=BrsApiEndpoints.SYMBOL_DETAIL,
            parser=_parse_with_ins_id,
            model_class=SymbolDetailModel,
            params={"l18": symbol},
            session=session,
        )

    # ── Shareholder ─────────────────────────────────
    async def sync_shareholders(
        self, session: AsyncSession, symbol: str
    ) -> SyncReport:
        """Sync shareholder composition for a symbol."""
        ins_id = await self._lookup_ins_id(session, symbol)

        def _parse_with_ins_id(data: Any) -> list[dict[str, Any]]:
            records = TsetmcParser.parse_shareholders(data)
            for r in records:
                r["symbol"] = symbol
                if ins_id:
                    r["ins_id"] = ins_id
            return records

        return await self.sync(
            endpoint=BrsApiEndpoints.SHAREHOLDER,
            parser=_parse_with_ins_id,
            model_class=ShareholderRecordModel,
            params={"l18": symbol},
            session=session,
        )

    # ── Candlestick ─────────────────────────────────
    async def sync_candlesticks(
        self, session: AsyncSession, symbol: str, candle_type: str = "3"
    ) -> SyncReport:
        """Sync candlestick data for a symbol."""
        ins_id = await self._lookup_ins_id(session, symbol)

        def _parse_with_ins_id(data: Any) -> list[dict[str, Any]]:
            records = TsetmcParser.parse_candlesticks(data)
            for r in records:
                r["symbol"] = symbol
                if ins_id:
                    r["ins_id"] = ins_id
            return records

        return await self.sync(
            endpoint=BrsApiEndpoints.CANDLESTICK,
            parser=_parse_with_ins_id,
            model_class=CandlestickModel,
            params={"l18": symbol, "type": candle_type},
            session=session,
        )

    # ── IME Futures ─────────────────────────────────
    async def sync_ime_futures(self, session: AsyncSession) -> SyncReport:
        """Sync IME futures contracts."""
        return await self.sync(
            endpoint=BrsApiEndpoints.IME_FUTURES,
            parser=ImeParser.parse_futures,
            model_class=ImeFutureModel,
            params=None,
            dedup_seconds=60,
            session=session,
        )

    # ── IME Options ─────────────────────────────────
    async def sync_ime_options(self, session: AsyncSession) -> SyncReport:
        """Sync IME option contracts."""
        return await self.sync(
            endpoint=BrsApiEndpoints.IME_OPTION,
            parser=ImeParser.parse_options,
            model_class=ImeOptionModel,
            params=None,
            dedup_seconds=60,
            session=session,
        )

    # ── IME Certificates ────────────────────────────
    async def sync_ime_certificates(self, session: AsyncSession) -> SyncReport:
        """Sync IME certificate/depository receipts."""
        return await self.sync(
            endpoint=BrsApiEndpoints.IME_CERTIFICATE,
            parser=ImeParser.parse_certificates,
            model_class=ImeCertificateModel,
            params=None,
            dedup_seconds=60,
            session=session,
        )

    # ── IME Funds ───────────────────────────────────
    async def sync_ime_funds(self, session: AsyncSession) -> SyncReport:
        """Sync IME commodity funds."""
        return await self.sync(
            endpoint=BrsApiEndpoints.IME_FUND,
            parser=ImeParser.parse_funds,
            model_class=ImeFundModel,
            params=None,
            dedup_seconds=60,
            session=session,
        )

    # ── IME Physical Trades ─────────────────────────
    async def sync_ime_physical(
        self,
        session: AsyncSession,
        date_start: str | None = None,
        date_end: str | None = None,
    ) -> SyncReport:
        """Sync IME physical trade records."""
        params: dict[str, str] = {}
        if date_start:
            params["date_start"] = date_start
        if date_end:
            params["date_end"] = date_end
        return await self.sync(
            endpoint=BrsApiEndpoints.IME_PHYSICAL,
            parser=ImeParser.parse_physical_trades,
            model_class=ImePhysicalTradeModel,
            params=params or None,
            session=session,
        )

    # ── Options (TSETMC) ────────────────────────────
    async def sync_options(self, session: AsyncSession) -> SyncReport:
        """Sync TSETMC option contracts."""
        return await self.sync(
            endpoint=BrsApiEndpoints.OPTION,
            parser=TsetmcParser.parse_options,
            model_class=OptionSnapshotModel,
            params=None,
            dedup_seconds=60,
            session=session,
        )

    # ── Gold & Coins ────────────────────────────────
    async def sync_gold_coin(self, session: AsyncSession) -> SyncReport:
        """Sync gold & coin prices (legacy endpoint).

        DEPRECATED: /Market/Coin.php returns HTTP 404 since ~June 2026.
        Use sync_gold_currency() which fetches from /Market/Gold_Currency.php
        and stores gold data in GoldCoinPriceModel.
        """
        logger.warning("sync_gold_coin(): /Market/Coin.php is deprecated (HTTP 404). Use sync_gold_currency() instead.")
        return await self.sync(
            endpoint=BrsApiEndpoints.GOLD_COIN,
            parser=GoldCoinParser.parse,
            model_class=GoldCoinPriceModel,
            params=None,
            dedup_seconds=30,
            session=session,
        )

    # ── Gold & Currency (Combined, Free-Tier) ────────
    async def sync_gold_currency(self, session: AsyncSession) -> list[SyncReport]:
        """
        Sync gold, currency & crypto in a single API call using the free-tier
        ``/Market/Gold_Currency.php`` endpoint.

        Returns one ``SyncReport`` per section (gold, currency, cryptocurrency).
        """
        reports: list[SyncReport] = []
        start_all = time.monotonic()

        sync_log, raw_payload = self._ensure_repos(session)
        client = await self._ensure_client()

        # 1. Fetch the raw API response once
        result = await client.fetch(BrsApiEndpoints.GOLD_CURRENCY, params=None)

        if not result.success:
            err_report = SyncReport(
                endpoint="Gold_Currency.php",
                success=False,
                error=result.error,
            )
            reports.append(err_report)
            # Log the failure
            await sync_log.record(
                endpoint="Gold_Currency.php",
                category="commodity",
                status="error",
                error_message=result.error,
                duration_ms=int((time.monotonic() - start_all) * 1000),
            )
            return reports

        data = result.value.data

        # 2. Parse each section and store into the correct table
        sections: list[tuple[str, Callable[[Any], Any], type, str, str]] = [
            ("gold", GoldCurrencyParser.parse_gold, GoldCoinPriceModel, "Gold/Coin", "gold_coin_prices"),
            ("currency", GoldCurrencyParser.parse_currency, CurrencyPriceModel, "Currency", "currency_prices"),
            ("cryptocurrency", GoldCurrencyParser.parse_crypto, CryptoPriceModel, "Crypto", "crypto_prices"),
        ]

        for section_name, parser_fn, model_class, label, _table_name in sections:
            start = time.monotonic()
            try:
                records = parser_fn(data)
            except Exception as exc:
                logger.exception("Parse error for Gold_Currency/%s", section_name)
                elapsed_ms = (time.monotonic() - start) * 1000
                report = SyncReport(
                    endpoint=f"Gold_Currency/{section_name}",
                    success=False,
                    error=f"ParseError: {exc}",
                    duration_ms=elapsed_ms,
                )
                reports.append(report)
                await sync_log.record(
                    endpoint=f"Gold_Currency/{section_name}",
                    category="commodity",
                    status="error",
                    error_message=f"ParseError: {exc}",
                    duration_ms=elapsed_ms,
                )
                continue

            if not records:
                elapsed_ms = (time.monotonic() - start) * 1000
                report = SyncReport(
                    endpoint=f"Gold_Currency/{section_name}",
                    success=True,
                    items_count=0,
                    duration_ms=elapsed_ms,
                )
                reports.append(report)
                await sync_log.record(
                    endpoint=f"Gold_Currency/{section_name}",
                    category="commodity",
                    status="success",
                    items_count=0,
                    duration_ms=elapsed_ms,
                )
                continue

            repo = BulkUpsertRepository(session, model_class)
            try:
                await repo.truncate()
                total = await repo.bulk_insert(records)
                await session.flush()
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.info("Gold_Currency/%s → %d records in %.0fms", label, total, elapsed_ms)
                report = SyncReport(
                    endpoint=f"Gold_Currency/{section_name}",
                    success=True,
                    items_count=total,
                    duration_ms=elapsed_ms,
                )
                reports.append(report)
                await sync_log.record(
                    endpoint=f"Gold_Currency/{section_name}",
                    category="commodity",
                    status="success",
                    items_count=total,
                    duration_ms=elapsed_ms,
                )
            except Exception as exc:
                await session.rollback()
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.exception("DB error for Gold_Currency/%s", section_name)
                report = SyncReport(
                    endpoint=f"Gold_Currency/{section_name}",
                    success=False,
                    error=f"DBError: {exc}",
                    duration_ms=elapsed_ms,
                )
                reports.append(report)
                await sync_log.record(
                    endpoint=f"Gold_Currency/{section_name}",
                    category="commodity",
                    status="error",
                    error_message=f"DBError: {exc}",
                    duration_ms=elapsed_ms,
                )
                # After a rollback, stop processing further sections
                break

        # Store raw payload once
        if result.value.raw_bytes is not None:
            try:
                await raw_payload.store(
                    endpoint="Gold_Currency.php",
                    payload=result.value.raw_bytes.decode("utf-8", errors="replace"),
                    status_code=result.value.status_code,
                )
                await session.flush()
            except Exception:
                logger.warning("Failed to store raw payload for Gold_Currency.php", exc_info=True)

        await session.commit()
        return reports

    # ── Gold & Currency Pro (real-time sections) ────────
    async def sync_gold_currency_pro(
        self, session: AsyncSession, sections: str = "gold,currency,cryptocurrency"
    ) -> list[SyncReport]:
        """
        Sync gold, currency & crypto from the **Pro** endpoint
        ``/Market/Gold_Currency_Pro.php?section=...``.

        Args:
            sections: Comma-separated section names (default: all three).

        Returns one ``SyncReport`` per section.
        """
        reports: list[SyncReport] = []
        start_all = time.monotonic()

        sync_log, raw_payload = self._ensure_repos(session)
        client = await self._ensure_client()

        # Fetch once with all requested sections
        result = await client.fetch(
            BrsApiEndpoints.GOLD_CURRENCY_PRO,
            params={"section": sections},
        )

        if not result.success:
            err_report = SyncReport(
                endpoint="Gold_Currency_Pro.php (section)",
                success=False,
                error=result.error,
            )
            reports.append(err_report)
            await sync_log.record(
                endpoint="Gold_Currency_Pro.php (section)",
                category="commodity",
                status="error",
                error_message=result.error,
                duration_ms=int((time.monotonic() - start_all) * 1000),
            )
            return reports

        data = result.value.data

        section_names = [s.strip() for s in sections.split(",")]
        parser_map = {
            "gold": (GoldCurrencyProParser.parse_gold, GoldCurrencyProPriceModel, "Gold (Pro)"),
            "currency": (GoldCurrencyProParser.parse_currency, GoldCurrencyProPriceModel, "Currency (Pro)"),
            "cryptocurrency": (GoldCurrencyProParser.parse_crypto, GoldCurrencyProPriceModel, "Crypto (Pro)"),
        }

        for section_name in section_names:
            if section_name not in parser_map:
                logger.warning("Unknown section: %s", section_name)
                continue

            parser_fn, model_class, label = parser_map[section_name]
            start = time.monotonic()

            try:
                records = parser_fn(data)
            except Exception as exc:
                logger.exception("Parse error for Gold_Currency_Pro/%s", section_name)
                elapsed_ms = (time.monotonic() - start) * 1000
                report = SyncReport(endpoint=f"Gold_Currency_Pro/{section_name}", success=False, error=f"ParseError: {exc}", duration_ms=elapsed_ms)
                reports.append(report)
                await sync_log.record(endpoint=f"Gold_Currency_Pro/{section_name}", category="commodity", status="error", error_message=f"ParseError: {exc}", duration_ms=elapsed_ms)
                continue

            if not records:
                elapsed_ms = (time.monotonic() - start) * 1000
                report = SyncReport(endpoint=f"Gold_Currency_Pro/{section_name}", success=True, items_count=0, duration_ms=elapsed_ms)
                reports.append(report)
                await sync_log.record(endpoint=f"Gold_Currency_Pro/{section_name}", category="commodity", status="success", items_count=0, duration_ms=elapsed_ms)
                continue

            repo = BulkUpsertRepository(session, model_class)
            try:
                await repo.truncate()
                total = await repo.bulk_insert(records)
                await session.flush()
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.info("Gold_Currency_Pro/%s → %d records in %.0fms", label, total, elapsed_ms)
                report = SyncReport(endpoint=f"Gold_Currency_Pro/{section_name}", success=True, items_count=total, duration_ms=elapsed_ms)
                reports.append(report)
                await sync_log.record(endpoint=f"Gold_Currency_Pro/{section_name}", category="commodity", status="success", items_count=total, duration_ms=elapsed_ms)
            except Exception as exc:
                await session.rollback()
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.exception("DB error for Gold_Currency_Pro/%s", section_name)
                report = SyncReport(endpoint=f"Gold_Currency_Pro/{section_name}", success=False, error=f"DBError: {exc}", duration_ms=elapsed_ms)
                reports.append(report)
                await sync_log.record(endpoint=f"Gold_Currency_Pro/{section_name}", category="commodity", status="error", error_message=f"DBError: {exc}", duration_ms=elapsed_ms)
                break

        # Store raw payload once
        if result.value.raw_bytes is not None:
            try:
                await raw_payload.store(endpoint="Gold_Currency_Pro.php", payload=result.value.raw_bytes.decode("utf-8", errors="replace"), status_code=result.value.status_code)
                await session.flush()
            except Exception:
                logger.warning("Failed to store raw payload for Gold_Currency_Pro.php", exc_info=True)

        await session.commit()
        return reports

    # ── Gold & Currency Pro (24h history) ─────────────
    async def sync_gold_currency_pro_history_24h(
        self, session: AsyncSession, symbol: str
    ) -> SyncReport:
        """Sync 24-hour tick history for a symbol from the Pro endpoint."""
        return await self.sync(
            endpoint=BrsApiEndpoints.GOLD_CURRENCY_PRO,
            parser=GoldCurrencyProParser.parse_history_24h,
            model_class=GoldCurrencyProHistory24hModel,
            params={"history": "1", "symbol": symbol},
            truncate_first=True,
            session=session,
        )

    # ── Gold & Currency Pro (daily OHLC history) ─────
    async def sync_gold_currency_pro_daily_history(
        self,
        session: AsyncSession,
        symbol: str,
        date_start: str | None = None,
        date_end: str | None = None,
    ) -> SyncReport:
        """Sync daily OHLC history for a symbol from the Pro endpoint."""
        params: dict[str, str] = {"history": "2", "symbol": symbol}
        if date_start:
            params["date_start"] = date_start
        if date_end:
            params["date_end"] = date_end
        return await self.sync(
            endpoint=BrsApiEndpoints.GOLD_CURRENCY_PRO,
            parser=GoldCurrencyProParser.parse_daily_history,
            model_class=GoldCurrencyProDailyHistoryModel,
            params=params,
            truncate_first=False,
            session=session,
        )

    # ── Currency ────────────────────────────────────
    async def sync_currency(self, session: AsyncSession) -> SyncReport:
        """Sync currency/forex prices.

        DEPRECATED: /Market/Currency.php returns HTTP 404 since ~June 2026.
        Use sync_gold_currency() which fetches from /Market/Gold_Currency.php
        and stores currency data in CurrencyPriceModel.
        """
        logger.warning("sync_currency(): /Market/Currency.php is deprecated (HTTP 404). Use sync_gold_currency() instead.")
        return await self.sync(
            endpoint=BrsApiEndpoints.CURRENCY,
            parser=CurrencyParser.parse,
            model_class=CurrencyPriceModel,
            params=None,
            dedup_seconds=30,
            session=session,
        )

    # ── Codal ───────────────────────────────────────
    async def _attach_codal_instrument_refs(
        self, session: AsyncSession, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Attach ins_id and instrument_id to codal records by symbol."""
        if not records:
            return records

        symbols = list({r["symbol"] for r in records if r.get("symbol")})
        if not symbols:
            return records

        from sqlalchemy import String, column, select, text

        from brsapi.models import SymbolSnapshotModel

        lookup: dict[str, tuple[str | None, str | None]] = {}

        stmt = select(
            SymbolSnapshotModel.symbol,
            SymbolSnapshotModel.ins_id,
            SymbolSnapshotModel.instrument_id,
        ).where(SymbolSnapshotModel.symbol.in_(symbols))
        result = await session.execute(stmt)
        for row in result:
            lookup[row.symbol] = (row.ins_id, row.instrument_id)

        missing = [s for s in symbols if s not in lookup]
        if missing:
            try:
                stmt2 = (
                    select(column("symbol", String), column("id", String).label("instrument_id"))
                    .select_from(text("instruments"))
                    .where(column("symbol", String).in_(missing))
                )
                result2 = await session.execute(stmt2)
                for row in result2:
                    lookup[row.symbol] = (None, str(row.instrument_id) if row.instrument_id else None)
            except Exception:
                pass

        for r in records:
            sym = r.get("symbol", "")
            ins_id: str | None = None
            instrument_id: str | None = None
            if sym in lookup:
                ins, instr = lookup[sym]
                ins_id = ins
                instrument_id = instr
            r["ins_id"] = ins_id
            r["instrument_id"] = instrument_id

        return records

    async def sync_codal(
        self,
        session: AsyncSession,
        backfill: bool = False,
        start_page: int = 1,
        max_pages: int | None = None,
    ) -> SyncReport:
        """Sync Codal announcements with pagination.

        Args:
            session: Database session.
            backfill: If True, fetch all pages until the API end. If False
                (default), stop as soon as a full page yields no new records,
                which makes incremental syncs fast and resumable.
            start_page: First page to fetch (1-indexed).
            max_pages: Optional cap on pages to process (useful for tests).
        """
        start_time = time.monotonic()
        client = await self._ensure_client()
        sync_log, _raw_payload = self._ensure_repos(session)
        repo = BulkUpsertRepository(session, CodalAnnouncementModel)

        current_page = start_page
        total_inserted = 0
        total_pages_api = 1
        pages_processed = 0

        while current_page <= total_pages_api:
            iter_start = time.monotonic()

            result = await client.fetch(
                BrsApiEndpoints.CODAL_ANNOUNCEMENT,
                params={"page": str(current_page)},
            )

            if not result.success:
                elapsed_ms = (time.monotonic() - start_time) * 1000
                await sync_log.record(
                    endpoint=BrsApiEndpoints.CODAL_ANNOUNCEMENT.path,
                    category=BrsApiEndpoints.CODAL_ANNOUNCEMENT.category.value,
                    status="error",
                    error_message=result.error,
                    duration_ms=elapsed_ms,
                    params={"page": str(current_page), "backfill": str(backfill)},
                )
                await session.commit()
                return SyncReport(
                    endpoint=BrsApiEndpoints.CODAL_ANNOUNCEMENT.path,
                    success=False,
                    error=result.error,
                    duration_ms=elapsed_ms,
                )

            brs_resp: BrsApiResponse = result.value
            parsed = CodalParser.parse(brs_resp.data)
            count_page = max(int(parsed.get("count_page") or 0), 0)

            # First page tells us how many pages exist
            if current_page == start_page:
                total_pages_api = count_page
                if max_pages:
                    total_pages_api = min(total_pages_api, start_page + max_pages - 1)

            records: list[dict[str, Any]] = parsed.get("announcements", [])
            if records:
                records = await self._attach_codal_instrument_refs(session, records)

            inserted = 0
            if records:
                try:
                    inserted = await repo.bulk_insert(records)
                    await session.commit()
                except Exception as exc:
                    await session.rollback()
                    elapsed_ms = (time.monotonic() - start_time) * 1000
                    await sync_log.record(
                        endpoint=BrsApiEndpoints.CODAL_ANNOUNCEMENT.path,
                        category=BrsApiEndpoints.CODAL_ANNOUNCEMENT.category.value,
                        status="error",
                        error_message=f"DBError: {exc}",
                        items_count=len(records),
                        duration_ms=elapsed_ms,
                        params={"page": str(current_page), "backfill": str(backfill)},
                    )
                    await session.commit()
                    return SyncReport(
                        endpoint=BrsApiEndpoints.CODAL_ANNOUNCEMENT.path,
                        success=False,
                        error=f"DBError: {exc}",
                        duration_ms=elapsed_ms,
                    )

            total_inserted += inserted
            pages_processed += 1

            logger.info(
                "Codal page %d/%d processed (inserted %d/%d)",
                current_page,
                total_pages_api,
                inserted,
                len(records),
            )

            # Incremental sync stop condition: a full page of duplicates means
            # we've caught up with existing data.
            if not backfill and inserted == 0 and len(records) > 0:
                logger.info("Codal incremental sync reached existing data at page %d.", current_page)
                break

            # If there are no records at all, there is nothing more to fetch.
            if len(records) == 0:
                break

            current_page += 1

            # Respect rate limit: 2 req / 10s => sleep ~5.1s between pages
            elapsed_iter = time.monotonic() - iter_start
            sleep_time = max(0.0, 5.1 - elapsed_iter)
            if current_page <= total_pages_api and sleep_time > 0:
                await asyncio.sleep(sleep_time)

        duration_ms = (time.monotonic() - start_time) * 1000
        await sync_log.record(
            endpoint=BrsApiEndpoints.CODAL_ANNOUNCEMENT.path,
            category=BrsApiEndpoints.CODAL_ANNOUNCEMENT.category.value,
            status="success",
            items_count=total_inserted,
            duration_ms=duration_ms,
            params={
                "pages_processed": str(pages_processed),
                "backfill": str(backfill),
                "start_page": str(start_page),
            },
        )
        await session.commit()

        return SyncReport(
            endpoint=BrsApiEndpoints.CODAL_ANNOUNCEMENT.path,
            success=True,
            items_count=total_inserted,
            duration_ms=duration_ms,
        )

    # ── Bulk sync ──────────────────────────────────

    async def sync_all(self, session: AsyncSession) -> list[SyncReport]:
        """
        Run all available sync operations in sequence (respecting rate limits).

        Returns a list of ``SyncReport`` for each operation.
        """
        reports: list[SyncReport] = []
        operations = [
            ("TSETMC Symbols", lambda: self.sync_all_symbols(session)),
            ("TSETMC Index", lambda: self.sync_index(session, "1")),
            ("TSETMC Index (Farabours)", lambda: self.sync_index(session, "2")),
            ("TSETMC Options", lambda: self.sync_options(session)),
            ("IME Futures", lambda: self.sync_ime_futures(session)),
            ("IME Options", lambda: self.sync_ime_options(session)),
            ("IME Certificates", lambda: self.sync_ime_certificates(session)),
            ("IME Funds", lambda: self.sync_ime_funds(session)),
            ("Commodities", lambda: self.sync_commodities(session)),
            ("Crypto", lambda: self.sync_crypto(session)),
            ("Gold/Currency (combined)", lambda: self.sync_gold_currency(session)),
            # Codal is intentionally excluded from sync_all() because the
            # Announcement endpoint is paginated (~610k items, 20/page).
            # Use sync_codal(session) directly or a dedicated paginator.
        ]
        for name, op in operations:
            logger.info("Starting sync: %s", name)
            result = await op()
            if isinstance(result, list):
                # Combined endpoints return multiple reports
                reports.extend(result)
            else:
                reports.append(result)
            # Brief delay between categories to avoid rate-limit bursts
            await asyncio.sleep(2)
        return reports

    async def health(self) -> dict[str, Any]:
        """Check the health of the BrsApi connection."""
        client = await self._ensure_client()
        return await client.health()

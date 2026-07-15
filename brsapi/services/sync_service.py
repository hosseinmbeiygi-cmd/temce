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
from dataclasses import dataclass
from logging import getLogger
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.client import BrsApiClient, BrsApiResponse, get_client
from brsapi.config import BrsApiEndpoints, EndpointConfig
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

        # 3. Parse
        try:
            parsed = parser(brs_resp.data)
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

        try:
            if truncate_first:
                await repo.truncate()

            # Batch insert
            total = 0
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                inserted = await repo.bulk_insert(batch)
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
            truncate_first=True,
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

    # ── Transactions ─────────────────────────────────
    async def sync_transactions(
        self, session: AsyncSession, symbol: str, date: str | None = None
    ) -> SyncReport:
        """Sync intraday trades for a symbol."""
        ins_id = await self._lookup_ins_id(session, symbol)
        params = {"l18": symbol}
        if date:
            params["date"] = date

        def _parse_with_ins_id(data: Any) -> list[dict[str, Any]]:
            records = TsetmcParser.parse_transactions(data)
            for r in records:
                r["symbol"] = symbol
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

        for section_name, parser_fn, model_class, label, table_name in sections:
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
    async def sync_codal(self, session: AsyncSession) -> SyncReport:
        """Sync Codal announcements."""

        async def _parse_with_instrument_ref(data: Any) -> list[dict[str, Any]]:
            records = CodalParser.parse_announcements_only(data)
            if not records:
                return records

            # Collect unique symbols to batch-lookup ins_id + instrument_id
            symbols = list({r["symbol"] for r in records if r.get("symbol")})
            if not symbols:
                return records

            # Build a lookup map: symbol -> (ins_id, instrument_id)
            from sqlalchemy import select

            from brsapi.models import SymbolSnapshotModel

            lookup: dict[str, tuple[str | None, str | None]] = {}

            # Try from snapshots first
            stmt = select(
                SymbolSnapshotModel.symbol,
                SymbolSnapshotModel.ins_id,
                SymbolSnapshotModel.instrument_id,
            ).where(SymbolSnapshotModel.symbol.in_(symbols))
            result = await session.execute(stmt)
            for row in result:
                lookup[row.symbol] = (row.ins_id, row.instrument_id)

            # Fallback: try instruments table for symbols not in snapshots
            missing = [s for s in symbols if s not in lookup]
            if missing:
                from sqlalchemy import String, column, text
                stmt2 = (
                    select(column("symbol", String), column("id", String).label("instrument_id"))
                    .select_from(text("instruments"))
                    .where(column("symbol", String).in_(missing))
                )
                try:
                    result2 = await session.execute(stmt2)
                    for row in result2:
                        lookup[row.symbol] = (None, str(row.instrument_id) if row.instrument_id else None)
                except Exception:
                    pass

            # Apply to records
            for r in records:
                sym = r.get("symbol", "")
                if sym in lookup:
                    ins, instr = lookup[sym]
                    if ins:
                        r["ins_id"] = ins
                    if instr:
                        r["instrument_id"] = instr

            return records

        return await self.sync(
            endpoint=BrsApiEndpoints.CODAL_ANNOUNCEMENT,
            parser=_parse_with_instrument_ref,
            model_class=CodalAnnouncementModel,
            params=None,
            dedup_seconds=300,
            session=session,
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
            # Gold 24h and Currency 24h removed — these API endpoints
            # now return HTTP 404. The data is available via the combined
            # Gold_Currency.php endpoint (synced above).
            # ("Gold 24h", lambda: self.sync_gold_24h(session)),
            # ("Currency 24h", lambda: self.sync_currency_24h(session)),
            # Codal removed from batch sync – requires l18 param (per-symbol)
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

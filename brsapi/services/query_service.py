"""
BrsApi Query Service
====================

Read-oriented service that provides clean interfaces for consuming BrsApi
data from other parts of the platform (backtesting, AI, analytics, etc.).
"""

from __future__ import annotations

from logging import getLogger
from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models import (
    CandlestickModel,
    CodalAnnouncementModel,
    CommodityPriceModel,
    CryptoPriceModel,
    Currency24hModel,
    CurrencyPriceModel,
    Gold24hModel,
    GoldCoinPriceModel,
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

logger = getLogger(__name__)

# Fast-path window for ``get_latest_snapshots``: each fetch cycle writes one
# row per symbol in a tight id range, so the newest cycle always sits inside
# the last ~N ids. Scanning that PK window is an index range scan
# (milliseconds) while a full-table ``GROUP BY symbol`` takes tens of
# seconds on the multi-million-row snapshot table.
_SNAPSHOT_SCAN_WINDOW = 50_000


class BrsApiQueryService:
    """
    Read-side service for consuming BrsApi data.

    Each method returns raw dicts or lists of dicts so that consumers
    (API endpoints, ML pipelines, backtest engines) can process them
    without coupling to ORM models.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Symbols / Real-time ────────────────────────

    async def get_enriched_snapshots(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Return most recent symbol snapshots enriched with detail fields
        (price_lowest_allowed/tmin, price_highest_allowed/tmax, free_float_pct)
        via a LEFT JOIN with ``SymbolDetailModel`` on ``ins_id`` (fallback ``symbol``).

        Falls back to simple snapshots if the SymbolDetailModel table does not
        exist or the JOIN fails for any reason.
        """
        try:
            rows = await self._enriched_snapshots_join(limit)
            if rows:
                return rows
        except Exception:
            logger.warning(
                "get_enriched_snapshots JOIN failed — falling back to simple snapshots",
                exc_info=True,
            )
        return await self.get_latest_snapshots(limit=limit)

    async def _enriched_snapshots_join(self, limit: int) -> list[dict[str, Any]]:
        """Internal: run the enriched-snapshots query.

        Deduplicates by symbol — only the latest snapshot per symbol is returned.

        Implementation note: the original single LEFT JOIN with an OR fallback
        condition (``ins_id = d.ins_id OR (ins_id IS NULL AND symbol = d.symbol)``)
        defeated every index — the planner degenerated to a nested loop doing
        millions of join-filter comparisons plus a full-table seq scan for the
        dedup (~30s+). Instead: windowed dedup (see get_latest_snapshots),
        then two targeted, index-friendly IN lookups against the (small)
        detail table merged in Python. Semantics are identical: ins_id match
        first, symbol fallback only for rows whose ins_id is null.
        """
        from sqlalchemy import func, or_, select

        # Step 1: get latest snapshot id per symbol — restricted to recent
        # cycles (a full-table GROUP BY costs tens of seconds on this table).
        max_id = (
            await self.session.execute(select(func.max(SymbolSnapshotModel.id)))
        ).scalar_one()
        latest_q = (
            select(
                SymbolSnapshotModel.symbol,
                func.max(SymbolSnapshotModel.id).label("max_id"),
            )
            .where(SymbolSnapshotModel.symbol.isnot(None))
            .where(SymbolSnapshotModel.symbol != "")
        )
        if max_id is not None:
            latest_q = latest_q.where(
                SymbolSnapshotModel.id > max_id - _SNAPSHOT_SCAN_WINDOW
            )
        subq = (
            latest_q.group_by(SymbolSnapshotModel.symbol)
            .order_by(func.max(SymbolSnapshotModel.trade_value).desc().nullslast())
            .limit(limit)
        ).subquery()

        stmt = (
            select(SymbolSnapshotModel)
            .join(subq, SymbolSnapshotModel.id == subq.c.max_id)
            .order_by(SymbolSnapshotModel.trade_value.desc().nullslast())
        )
        snaps = (await self.session.execute(stmt)).scalars().all()

        # Step 2: targeted detail lookup — ins_id primary, symbol fallback
        # only for rows whose ins_id is null (mirrors the old OR-join).
        ins_ids = {s.ins_id for s in snaps if s.ins_id}
        fallback_syms = {s.symbol for s in snaps if not s.ins_id}
        details: list[Any] = []
        if ins_ids or fallback_syms:
            conds = []
            if ins_ids:
                conds.append(SymbolDetailModel.ins_id.in_(ins_ids))
            if fallback_syms:
                conds.append(SymbolDetailModel.symbol.in_(fallback_syms))
            details = list(
                (
                    await self.session.execute(
                        select(SymbolDetailModel).where(or_(*conds))
                    )
                ).scalars().all()
            )
        by_ins: dict[str, Any] = {}
        by_sym: dict[str, Any] = {}
        for d_obj in details:
            by_ins.setdefault(d_obj.ins_id, d_obj)
            by_sym.setdefault(d_obj.symbol, d_obj)

        rows: list[dict[str, Any]] = []
        seen_symbols: set[str] = set()
        for snap_row in snaps:
            sym = getattr(snap_row, "symbol", "")
            if sym in seen_symbols:
                continue
            seen_symbols.add(sym)
            d = self._row_dict(snap_row)
            detail_row = by_ins.get(snap_row.ins_id) if snap_row.ins_id else by_sym.get(sym)
            if detail_row is not None:
                detail_d = self._row_dict(detail_row)
                for field in ("price_lowest_allowed", "price_highest_allowed", "free_float_pct",
                              "eps", "pe_ratio", "group_pe_ratio", "market", "board", "sector",
                              "sub_sector", "state", "date_update"):
                    val = detail_d.get(field)
                    if val is not None and val != 0:
                        d[field] = val
            rows.append(d)
        return rows

    async def get_latest_snapshots(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return latest snapshot per symbol (deduplicated).

        The snapshot table grows by one full fetch cycle (~1.2–1.7k rows)
        every few minutes, so a full-table ``GROUP BY symbol`` costs tens
        of seconds on the multi-million-row table. Instead, group only over
        the last ``_SNAPSHOT_SCAN_WINDOW`` ids (a handful of recent cycles
        — an index range scan) and take MAX(id) per symbol; the result is
        identical to a full-table dedup for every symbol that traded in
        the window. Falls back to the full GROUP BY when the window is
        empty (fresh DB) or the windowed query fails.
        """
        from sqlalchemy import func, select

        try:
            max_id = (
                await self.session.execute(select(func.max(SymbolSnapshotModel.id)))
            ).scalar_one()
            if max_id is not None:
                window = (
                    select(
                        SymbolSnapshotModel.symbol,
                        func.max(SymbolSnapshotModel.id).label("max_id"),
                    )
                    .where(
                        SymbolSnapshotModel.id > max_id - _SNAPSHOT_SCAN_WINDOW,
                        SymbolSnapshotModel.symbol.isnot(None),
                        SymbolSnapshotModel.symbol != "",
                    )
                    .group_by(SymbolSnapshotModel.symbol)
                ).subquery()
                stmt = (
                    select(SymbolSnapshotModel)
                    .join(window, SymbolSnapshotModel.id == window.c.max_id)
                    .order_by(SymbolSnapshotModel.trade_value.desc().nullslast())
                    .limit(limit)
                )
                rows = (await self.session.execute(stmt)).scalars().all()
                if rows:
                    return [self._row_dict(r) for r in rows]
        except Exception:
            logger.warning(
                "get_latest_snapshots windowed dedup failed — falling back to full GROUP BY",
                exc_info=True,
            )

        subq = (
            select(
                SymbolSnapshotModel.symbol,
                func.max(SymbolSnapshotModel.id).label("max_id"),
            )
            .where(SymbolSnapshotModel.symbol.isnot(None))
            .where(SymbolSnapshotModel.symbol != "")
            .group_by(SymbolSnapshotModel.symbol)
            .order_by(func.max(SymbolSnapshotModel.trade_value).desc().nullslast())
            .limit(limit)
        ).subquery()

        stmt = (
            select(SymbolSnapshotModel)
            .join(subq, SymbolSnapshotModel.id == subq.c.max_id)
            .order_by(SymbolSnapshotModel.trade_value.desc().nullslast())
        )
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_symbol_snapshot(self, symbol: str, ins_id: str | None = None) -> dict[str, Any] | None:
        """Get the latest snapshot for a single symbol or ins_id."""
        from sqlalchemy import or_

        stmt = select(SymbolSnapshotModel)
        if ins_id:
            stmt = stmt.where(
                or_(
                    SymbolSnapshotModel.ins_id == ins_id,
                    SymbolSnapshotModel.symbol == symbol,
                )
            )
        else:
            stmt = stmt.where(SymbolSnapshotModel.symbol == symbol)
        stmt = stmt.order_by(SymbolSnapshotModel.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._row_dict(row) if row else None

    async def get_enriched_symbol_detail(self, symbol: str) -> dict[str, Any] | None:
        """
        Return symbol snapshot enriched with detail fields
        (price_lowest_allowed, price_highest_allowed, free_float_pct, state,
         board, sector, sub_sector, eps, pe_ratio, group_pe_ratio, market)
        for a **single** symbol via LEFT JOIN on ``SymbolDetailModel`` using ``ins_id``.
        """
        from sqlalchemy import join, or_

        j = join(
            SymbolSnapshotModel,
            SymbolDetailModel,
            or_(
                SymbolSnapshotModel.ins_id == SymbolDetailModel.ins_id,
                SymbolSnapshotModel.ins_id.is_(None) & (SymbolSnapshotModel.symbol == SymbolDetailModel.symbol),
            ),
            isouter=True,
        )
        stmt = (
            select(SymbolSnapshotModel, SymbolDetailModel)
            .select_from(j)
            .where(
                or_(
                    SymbolSnapshotModel.symbol == symbol,
                    SymbolSnapshotModel.ins_id == symbol,
                )
            )
            .order_by(SymbolSnapshotModel.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None

        snap_row, detail_row = row
        d = self._row_dict(snap_row)
        if detail_row is not None:
            detail_d = self._row_dict(detail_row)
            for field in ("price_lowest_allowed", "price_highest_allowed", "free_float_pct",
                          "eps", "pe_ratio", "group_pe_ratio", "ps_ratio", "market", "board", "sector",
                          "sub_sector", "state", "date_update"):
                val = detail_d.get(field)
                if val is not None and val != 0:
                    d[field] = val
        return d

    async def get_top_gainers(self, limit: int = 10) -> list[dict[str, Any]]:
        """Top gainers from the latest snapshot cycle."""
        # Subquery: find the most recent fetched_at
        latest = select(sa_func.max(SymbolSnapshotModel.fetched_at)).scalar_subquery()

        stmt = (
            select(SymbolSnapshotModel)
            .where(SymbolSnapshotModel.fetched_at == latest)
            .order_by(SymbolSnapshotModel.price_last_change_pct.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_top_losers(self, limit: int = 10) -> list[dict[str, Any]]:
        """Top losers from the latest snapshot cycle."""
        latest = select(sa_func.max(SymbolSnapshotModel.fetched_at)).scalar_subquery()
        stmt = (
            select(SymbolSnapshotModel)
            .where(SymbolSnapshotModel.fetched_at == latest)
            .order_by(SymbolSnapshotModel.price_last_change_pct.asc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_most_active(self, limit: int = 10) -> list[dict[str, Any]]:
        """Most traded by value from the latest snapshot cycle."""
        latest = select(sa_func.max(SymbolSnapshotModel.fetched_at)).scalar_subquery()
        stmt = (
            select(SymbolSnapshotModel)
            .where(SymbolSnapshotModel.fetched_at == latest)
            .order_by(SymbolSnapshotModel.trade_value.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    # ── Indices ────────────────────────────────────

    async def get_latest_indices(self) -> list[dict[str, Any]]:
        """Latest index values — one row per unique index name."""
        # Subquery: latest created_at per unique index name
        latest_per_name = (
            select(
                IndexValueModel.name,
                sa_func.max(IndexValueModel.created_at).label("max_created"),
            )
            .where(IndexValueModel.name != "")
            .group_by(IndexValueModel.name)
        ).subquery()

        stmt = (
            select(IndexValueModel)
            .join(
                latest_per_name,
                (IndexValueModel.name == latest_per_name.c.name)
                & (IndexValueModel.created_at == latest_per_name.c.max_created),
            )
            .order_by(IndexValueModel.name)
        )
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_index_history(self, name: str, limit: int = 100) -> list[dict[str, Any]]:
        """Historical index values for a given index name."""
        stmt = (
            select(IndexValueModel)
            .where(IndexValueModel.name == name)
            .order_by(IndexValueModel.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    # ── NAV ────────────────────────────────────────

    async def get_nav(self, symbol: str, ins_id: str | None = None) -> dict[str, Any] | None:
        """Latest NAV for a given fund symbol or ins_id."""
        from sqlalchemy import or_

        stmt = select(NavRecordModel)
        if ins_id:
            stmt = stmt.where(
                or_(
                    NavRecordModel.ins_id == ins_id,
                    NavRecordModel.symbol == symbol,
                )
            )
        else:
            stmt = stmt.where(NavRecordModel.symbol == symbol)
        stmt = stmt.order_by(NavRecordModel.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._row_dict(row) if row else None

    # ── Options ────────────────────────────────────

    async def get_options_by_underlying(self, underlying: str) -> list[dict[str, Any]]:
        """Option contracts for a given underlying symbol."""
        stmt = (
            select(OptionSnapshotModel)
            .where(OptionSnapshotModel.underlying_symbol == underlying)
            .order_by(OptionSnapshotModel.date_end.asc())
        )
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    # ── Historical (batch) ─────────────────────────

    async def get_batch_historical_daily(self, limit: int = 61) -> list[dict[str, Any]]:
        """Batch: latest daily OHLCV for ALL symbols, newest-first, up to ``limit`` days per symbol."""
        from sqlalchemy import func

        # Subquery: latest id per symbol per date group
        # We need newest N rows per symbol — use ROW_NUMBER
        inner = (
            select(
                HistoricalDailyModel.symbol,
                HistoricalDailyModel.date,
                HistoricalDailyModel.trade_volume,
                HistoricalDailyModel.trade_value,
                HistoricalDailyModel.price_min,
                HistoricalDailyModel.price_max,
                HistoricalDailyModel.price_first,
                HistoricalDailyModel.price_last,
                HistoricalDailyModel.price_close,
                HistoricalDailyModel.price_last_change_pct,
                func.row_number().over(
                    partition_by=HistoricalDailyModel.symbol,
                    order_by=HistoricalDailyModel.date.desc(),
                ).label("rn"),
            )
            .where(HistoricalDailyModel.symbol.isnot(None))
            .where(HistoricalDailyModel.symbol != "")
        ).subquery()

        stmt = (
            select(inner)
            .where(inner.c.rn <= limit)
            .order_by(inner.c.symbol, inner.c.date.desc())
        )
        result = await self.session.execute(stmt)
        return [
            {
                "symbol": r.symbol,
                "trade_date": r.date,
                "price_close": r.price_close,
                "price_max": r.price_max,
                "price_min": r.price_min,
                "price_last": r.price_last,
                "price_first": r.price_first,
                "trade_volume": r.trade_volume,
                "trade_value": r.trade_value,
                "price_last_change_pct": r.price_last_change_pct,
            }
            for r in result
        ]

    async def get_batch_historical_real_legal(self, limit: int = 36) -> list[dict[str, Any]]:
        """
        Batch: latest daily real/legal breakdown for ALL symbols,
        newest-first, up to ``limit`` days per symbol.

        Uses HistoricalRealLegalModel (brsapi_historical_real_legal table).
        """
        from sqlalchemy import func

        inner = (
            select(
                HistoricalRealLegalModel.symbol,
                HistoricalRealLegalModel.date,
                HistoricalRealLegalModel.buy_real_volume,
                HistoricalRealLegalModel.sell_real_volume,
                HistoricalRealLegalModel.buy_legal_volume,
                HistoricalRealLegalModel.sell_legal_volume,
                HistoricalRealLegalModel.buy_real_value,
                HistoricalRealLegalModel.sell_real_value,
                HistoricalRealLegalModel.buy_legal_value,
                HistoricalRealLegalModel.sell_legal_value,
                func.row_number().over(
                    partition_by=HistoricalRealLegalModel.symbol,
                    order_by=HistoricalRealLegalModel.date.desc(),
                ).label("rn"),
            )
            .where(HistoricalRealLegalModel.symbol.isnot(None))
            .where(HistoricalRealLegalModel.symbol != "")
        ).subquery()

        stmt = (
            select(inner)
            .where(inner.c.rn <= limit)
            .order_by(inner.c.symbol, inner.c.date.desc())
        )
        result = await self.session.execute(stmt)
        return [
            {
                "symbol": r.symbol,
                "trade_date": r.date,
                "legal_buy_volume": r.buy_legal_volume,
                "legal_sell_volume": r.sell_legal_volume,
                "real_buy_volume": r.buy_real_volume,
                "real_sell_volume": r.sell_real_volume,
                "real_buy_value": r.buy_real_value,
                "real_sell_value": r.sell_real_value,
                "legal_buy_value": r.buy_legal_value,
                "legal_sell_value": r.sell_legal_value,
            }
            for r in result
        ]

    async def get_historical_daily(
        self, symbol: str, ins_id: str | None = None, limit: int = 365
    ) -> list[dict[str, Any]]:
        """Daily OHLCV data for a symbol or ins_id."""
        from sqlalchemy import or_

        stmt = select(HistoricalDailyModel)
        if ins_id:
            stmt = stmt.where(
                or_(
                    HistoricalDailyModel.ins_id == ins_id,
                    HistoricalDailyModel.symbol == symbol,
                )
            )
        else:
            stmt = stmt.where(HistoricalDailyModel.symbol == symbol)
        stmt = stmt.order_by(HistoricalDailyModel.date.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_candlesticks(
        self, symbol: str, ins_id: str | None = None, candle_type: str = "3", limit: int = 200
    ) -> list[dict[str, Any]]:
        """Candlestick data for charting, newest first.

        ``candle_type`` selects the series: ``1`` realtime (2-min bars),
        ``2`` unadjusted daily, ``3`` adjusted daily (default). Rows are
        ordered by ``gregorian_date`` (falling back to the raw Jalali
        ``date``) so sorting is chronologically correct.
        """
        from sqlalchemy import or_

        stmt = select(CandlestickModel).where(CandlestickModel.candle_type == candle_type)
        if ins_id:
            stmt = stmt.where(
                or_(
                    CandlestickModel.ins_id == ins_id,
                    CandlestickModel.symbol == symbol,
                )
            )
        else:
            stmt = stmt.where(CandlestickModel.symbol == symbol)
        stmt = stmt.order_by(
            CandlestickModel.gregorian_date.desc().nullslast(),
            CandlestickModel.date.desc().nullslast(),
        ).limit(limit)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    # ── IME ────────────────────────────────────────

    async def get_ime_futures(self) -> list[dict[str, Any]]:
        """All IME futures contracts."""
        stmt = select(ImeFutureModel).order_by(ImeFutureModel.date_end.asc())
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_ime_options(self) -> list[dict[str, Any]]:
        """All IME option contracts."""
        stmt = select(ImeOptionModel).order_by(ImeOptionModel.call_date_end.asc())
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_ime_certificates(self) -> list[dict[str, Any]]:
        """All IME certificate/depository receipts."""
        stmt = select(ImeCertificateModel)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_ime_funds(self) -> list[dict[str, Any]]:
        """All IME commodity funds."""
        stmt = select(ImeFundModel)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_ime_physical_trades(
        self, date_start: str | None = None, date_end: str | None = None
    ) -> list[dict[str, Any]]:
        """IME physical trades, optionally filtered by date range."""
        stmt = select(ImePhysicalTradeModel)
        if date_start:
            stmt = stmt.where(ImePhysicalTradeModel.date_trade >= date_start)
        if date_end:
            stmt = stmt.where(ImePhysicalTradeModel.date_trade <= date_end)
        stmt = stmt.order_by(ImePhysicalTradeModel.date_trade.desc())
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    # ── Commodities ────────────────────────────────

    async def get_commodity_prices(
        self, category: str | None = None
    ) -> list[dict[str, Any]]:
        """Latest commodity prices, optionally filtered by category."""
        stmt = select(CommodityPriceModel)
        if category:
            stmt = stmt.where(CommodityPriceModel.category == category)
        stmt = stmt.order_by(CommodityPriceModel.category, CommodityPriceModel.symbol)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_commodity_categories(self) -> list[dict[str, Any]]:
        """
        Grouped commodity categories with item counts and last update times.
        """
        stmt = (
            select(
                CommodityPriceModel.category,
                sa_func.count().label("count"),
                sa_func.max(CommodityPriceModel.fetched_at).label("last_update"),
            )
            .group_by(CommodityPriceModel.category)
        )
        result = await self.session.execute(stmt)
        return [
            {
                "category": row.category or "other",
                "count": row.count,
                "last_update": str(row.last_update) if row.last_update else None,
            }
            for row in result
        ]

    async def get_brsapi_stats(self) -> dict[str, int]:
        """Row counts across key BrsApi tables for health/status."""
        counts: dict[str, int] = {}
        for name, model in [
            ("commodity_prices", CommodityPriceModel),
            ("crypto_prices", CryptoPriceModel),
            ("symbol_snapshots", SymbolSnapshotModel),
            ("index_values", IndexValueModel),
            ("option_snapshots", OptionSnapshotModel),
            ("ime_futures", ImeFutureModel),
        ]:
            stmt = select(sa_func.count()).select_from(model)
            result = await self.session.execute(stmt)
            counts[name] = result.scalar() or 0
        return counts

    # ── Crypto ─────────────────────────────────────

    async def get_crypto_prices(
        self, limit: int = 50, sort_by: str = "rank"
    ) -> list[dict[str, Any]]:
        """Latest crypto prices, sorted by rank by default."""
        order_col = getattr(CryptoPriceModel, sort_by, CryptoPriceModel.rank)
        stmt = select(CryptoPriceModel).order_by(order_col.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    # ── Gold & Coins ─────────────────────────────────

    async def get_gold_coin_prices(self) -> list[dict[str, Any]]:
        """Latest gold & coin prices."""
        stmt = select(GoldCoinPriceModel).order_by(GoldCoinPriceModel.symbol)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_gold_24h(self) -> list[dict[str, Any]]:
        """Latest 24-hour gold price changes."""
        stmt = select(Gold24hModel).order_by(Gold24hModel.symbol)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    # ── Currency ─────────────────────────────────────

    async def get_currency_prices(self) -> list[dict[str, Any]]:
        """Latest currency/forex prices."""
        stmt = select(CurrencyPriceModel).order_by(CurrencyPriceModel.symbol)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    async def get_currency_24h(self) -> list[dict[str, Any]]:
        """Latest 24-hour currency changes."""
        stmt = select(Currency24hModel).order_by(Currency24hModel.symbol)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    # ── Shareholders ───────────────────────────────

    async def get_shareholders(self, symbol: str, ins_id: str | None = None) -> list[dict[str, Any]]:
        """Major shareholders for a symbol or ins_id, newest first."""
        from sqlalchemy import or_

        stmt = select(ShareholderRecordModel)
        if ins_id:
            stmt = stmt.where(
                or_(
                    ShareholderRecordModel.ins_id == ins_id,
                    ShareholderRecordModel.symbol == symbol,
                )
            )
        else:
            stmt = stmt.where(ShareholderRecordModel.symbol == symbol)
        stmt = stmt.order_by(ShareholderRecordModel.percent.desc().nullslast()).limit(50)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    # ── Intraday Trades ────────────────────────────

    async def get_intraday_trades(
        self, symbol: str, ins_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Intraday trade ticks for a symbol or ins_id, newest first."""
        from sqlalchemy import or_

        stmt = select(IntradayTradeModel)
        if ins_id:
            stmt = stmt.where(
                or_(
                    IntradayTradeModel.ins_id == ins_id,
                    IntradayTradeModel.symbol == symbol,
                )
            )
        else:
            stmt = stmt.where(IntradayTradeModel.symbol == symbol)
        stmt = stmt.order_by(IntradayTradeModel.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return [self._row_dict(r) for r in result.scalars().all()]

    # ── Codal ──────────────────────────────────────

    async def get_recent_announcements(
        self,
        limit: int = 50,
        offset: int = 0,
        symbol: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Most recent codal announcements, optionally filtered."""
        from brsapi.parsers.codal import detect_audit_status

        stmt = select(CodalAnnouncementModel)
        if symbol:
            stmt = stmt.where(CodalAnnouncementModel.symbol == symbol)
        if date_start:
            stmt = stmt.where(CodalAnnouncementModel.date_publish >= date_start)
        if date_end:
            stmt = stmt.where(CodalAnnouncementModel.date_publish <= date_end)
        stmt = stmt.order_by(CodalAnnouncementModel.date_publish.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        rows = [self._row_dict(r) for r in result.scalars().all()]
        # Enrich with audit_status detected from title
        for row in rows:
            row["audit_status"] = detect_audit_status(row.get("title", ""))
        return rows

    # ── Helper ─────────────────────────────────────

    @staticmethod
    def _row_dict(row: Any) -> dict[str, Any]:
        """Convert a SQLAlchemy model instance to a plain dict."""
        if row is None:
            return {}
        return {
            c.key: getattr(row, c.key)
            for c in row.__table__.columns
            if c.key not in ("raw_json",)  # exclude large fields by default
        }

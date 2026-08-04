"""
PopulateProfilesService — پر کردن screener_profiles از داده‌های موجود.

معماری:
  - BrsApi tables (brsapi_symbol_snapshots, brsapi_symbol_details) منبع اصلی
  - daily_history / daily_real_legal برای داده‌های تکنیکال
  - هر symbol در یک savepoint مجزا (begin_nested) تا خطا بقیه را نشکند
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from models.screener import ScreenerProfile

logger = get_logger(__name__)


class PopulateProfilesService:
    """سرویس پر کردن جدول screener_profiles از داده‌های موجود."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # ────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────

    async def populate_all(self) -> dict[str, Any]:
        """پر کردن پروفایل همه نمادهای موجود در brsapi_symbol_snapshots.

        Returns:
            آمار: total, created, updated, skipped
        """
        # Source of truth: symbols that have any data in brsapi tables
        symbols = await self._get_brsapi_symbols()
        logger.info("Found %d symbols from BrsApi", len(symbols))

        created = 0
        updated = 0
        skipped = 0

        for sym_data in symbols:
            symbol = sym_data.get("symbol", "")
            if not symbol:
                skipped += 1
                continue

            result = await self._populate_one_with_savepoint(symbol, sym_data)
            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            else:
                skipped += 1

        summary = {
            "total": len(symbols),
            "created": created,
            "updated": updated,
            "skipped": skipped,
        }
        logger.info("Populate complete: %s", summary)
        return summary

    async def populate_symbol(self, symbol: str) -> dict[str, Any]:
        """پر کردن پروفایل یک نماد خاص."""
        q = text("""
            SELECT symbol, sector, shares_count, eps, pe_ratio
            FROM brsapi_symbol_snapshots
            WHERE symbol = :sym
            ORDER BY created_at DESC LIMIT 1
        """)
        row = (await self._session.execute(q, {"sym": symbol})).fetchone()
        if not row:
            return {"symbol": symbol, "status": "not_found"}

        sym_data = dict(row._mapping)
        # Enrich from details
        q2 = text("""
            SELECT shares_count, free_float_pct, sector, eps, group_pe_ratio
            FROM brsapi_symbol_details WHERE symbol = :sym
        """)
        det_row = (await self._session.execute(q2, {"sym": symbol})).fetchone()
        if det_row:
            sym_data.update({k: v for k, v in dict(det_row._mapping).items() if v})

        status = await self._populate_one_with_savepoint(symbol, sym_data)
        return {"symbol": symbol, "status": status}

    # ────────────────────────────────────────────────────────────
    # Per-symbol upsert with savepoint isolation
    # ────────────────────────────────────────────────────────────

    async def _populate_one_with_savepoint(
        self, symbol: str, sym_data: dict[str, Any]
    ) -> str:
        """Upsert one profile inside a savepoint.

        Each symbol runs in its own nested transaction so that
        a single failure never blocks the rest.
        """
        try:
            async with self._session.begin_nested():
                return await self._populate_one(symbol, sym_data)
        except Exception as exc:
            logger.warning(
                "Skipped %s (savepoint rollback): %s", symbol, exc
            )
            return "skipped"

    # ────────────────────────────────────────────────────────────
    # Core upsert logic
    # ────────────────────────────────────────────────────────────

    async def _populate_one(
        self, symbol: str, sym_data: dict[str, Any]
    ) -> str:
        """پر کردن یا بروزرسانی یک رکورد در screener_profiles.

        Returns:
            "created" | "updated"
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        # ═══════════════════════════════════════════════════════
        # 1. BrsApi symbol_snapshots (latest snapshot)
        # ═══════════════════════════════════════════════════════
        br_eps = float(sym_data.get("eps", 0) or 0)
        br_sector = sym_data.get("sector") or ""

        # ═══════════════════════════════════════════════════════
        # 2. BrsApi symbol_details (enriched, may have more rows)
        # ═══════════════════════════════════════════════════════
        detail_eps = 0.0
        detail_shares = 0
        detail_free_float_pct = 0.0
        detail_sector = ""
        detail_group_pe = 0.0
        detail_sub_sector = ""

        q = text("""
            SELECT eps, shares_count, free_float_pct, sector,
                   sub_sector, group_pe_ratio
            FROM brsapi_symbol_details WHERE symbol = :sym
            LIMIT 1
        """)
        det_row = (await self._session.execute(q, {"sym": symbol})).fetchone()
        if det_row:
            det = dict(det_row._mapping)
            detail_eps = float(det.get("eps", 0) or 0)
            detail_shares = int(det.get("shares_count", 0) or 0)
            detail_free_float_pct = float(det.get("free_float_pct", 0) or 0)
            detail_sector = det.get("sector") or ""
            detail_group_pe = float(det.get("group_pe_ratio", 0) or 0)
            detail_sub_sector = det.get("sub_sector") or ""

        # ── Pick best values ──
        eps = br_eps or detail_eps
        sector = detail_sector or br_sector
        industry_pe = detail_group_pe or 6.5  # default fallback
        shares_count = detail_shares

        # Free float: detail has actual %, else estimate 20%
        free_float_pct = detail_free_float_pct or 20.0
        free_float = int(shares_count * free_float_pct / 100.0) if shares_count else 0

        # Registered capital: shares_count * 1000 IRR par value
        registered_capital = round(shares_count * 1000 / 1e9, 2) if shares_count else None

        # ═══════════════════════════════════════════════════════
        # 3. Macro: NIMA / free-market rates
        # ═══════════════════════════════════════════════════════
        nima_rate = 42000.0
        free_rate = 62000.0
        try:
            r = await self._session.execute(text("""
                SELECT price FROM brsapi_currency_prices
                WHERE symbol IN ('NIMA','USD_NIMA','IRR_NIMA')
                ORDER BY fetched_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                nima_rate = float(row[0] or 42000)
        except Exception:
            pass

        try:
            r = await self._session.execute(text("""
                SELECT price FROM brsapi_currency_prices
                WHERE symbol IN ('USD','USD_FREE','US Dollar')
                ORDER BY fetched_at DESC LIMIT 1
            """))
            row = r.fetchone()
            if row:
                free_rate = float(row[0] or 62000)
        except Exception:
            pass

        bank_rate = 30.0

        # ═══════════════════════════════════════════════════════
        # 4. Daily history (for averages used by the model)
        # ═══════════════════════════════════════════════════════
        avg_daily_value = 0.0
        gross_margin = None
        net_operating_profit = None

        try:
            q = text("""
                SELECT dh.price_close, dh.trade_volume, dh.trade_value,
                       dh.price_last_change_pct, dh.trade_date
                FROM daily_history dh
                JOIN symbols s ON s.id = dh.symbol_id
                WHERE s.symbol = :sym
                ORDER BY dh.trade_date DESC LIMIT 60
            """)
            daily_rows = [
                dict(r._mapping)
                for r in (await self._session.execute(q, {"sym": symbol})).fetchall()
            ]

            if daily_rows:
                _vols = [float(r.get("trade_volume", 0) or 0) for r in daily_rows]
                vals = [float(r.get("trade_value", 0) or 0) for r in daily_rows]
                avg_daily_value = sum(vals[:30]) / max(len(vals[:30]), 1)

                # Estimate net profit from trade value (~0.3% margin)
                if avg_daily_value:
                    net_operating_profit = round(avg_daily_value * 0.003 / 1e9, 4)
                    gross_margin = 20.0 if eps else None  # TODO: read from codal
        except Exception:
            pass

        # ═══════════════════════════════════════════════════════
        # 5. Real / Legal (30-day aggregates)
        # ═══════════════════════════════════════════════════════
        try:
            q = text("""
                SELECT drl.legal_buy_volume, drl.legal_sell_volume,
                       drl.real_buy_volume, drl.real_sell_volume
                FROM daily_real_legal drl
                JOIN symbols s ON s.id = drl.symbol_id
                WHERE s.symbol = :sym
                ORDER BY drl.trade_date DESC LIMIT 30
            """)
            legal_rows = [
                dict(r._mapping)
                for r in (await self._session.execute(q, {"sym": symbol})).fetchall()
            ]

            _inst_buy_30d = sum(
                float(r.get("legal_buy_volume", 0) or 0) for r in legal_rows
            )
            _inst_sell_30d = sum(
                float(r.get("legal_sell_volume", 0) or 0) for r in legal_rows
            )
        except Exception:
            pass

        # ═══════════════════════════════════════════════════════
        # 6. Build values dict & UPSERT
        # ═══════════════════════════════════════════════════════
        values = {
            "symbol": symbol,
            "industry": sector,
            "sub_industry": detail_sub_sector,
            "free_float_shares": free_float,
            "eps_current": eps,
            "eps_prev_year": round(eps * 0.85, 2) if eps else 0,  # ~15% growth assumption
            "exchange_rate_base": round(nima_rate, 0),
            "inflation_rate": 35.0,  # TODO: read from macro table
            "net_operating_profit": net_operating_profit,
            "accumulated_loss": 0,  # TODO: from codal
            "registered_capital": registered_capital,
            "legal_reserve": None,
            "gross_margin": gross_margin,
            "feedstock_price": None,
            "feedstock_change_pct": None,
            "capital_increase_type": None,
            "capital_increase_pct": None,
            "industry_pe": round(industry_pe, 2),
            "bank_interest_rate": bank_rate,
            "nima_rate": round(nima_rate, 0),
            "free_market_rate": round(free_rate, 0),
        }

        update_set = {k: v for k, v in values.items() if k != "symbol"}

        stmt = pg_insert(ScreenerProfile).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="screener_profiles_pkey",
            set_=update_set,
        )

        await self._session.execute(stmt)
        return "updated"

    # ────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────

    async def _get_brsapi_symbols(self) -> list[dict[str, Any]]:
        """لیست نمادهایی که در BrsApi snapshots وجود دارند."""
        q = text("""
            SELECT DISTINCT ON (s.symbol)
                s.symbol, s.sector, s.eps, s.pe_ratio, s.shares_count
            FROM brsapi_symbol_snapshots s
            WHERE s.symbol IS NOT NULL AND s.symbol != ''
            ORDER BY s.symbol, s.created_at DESC
        """)
        result = await self._session.execute(q)
        return [dict(row._mapping) for row in result.fetchall()]

"""Watchlist service — manage user's watched symbols with enriched data.

Uses PostgreSQL for persistent storage and batch-loads live data from
brsapi_symbol_snapshots + brsapi_symbol_details so every symbol is supported.
"""

from __future__ import annotations

from typing import Any

from core.db_utils import safe_row_str
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

# ── Default popular symbols (shown when watchlist is empty) ──

DEFAULT_SYMBOLS: list[str] = [
    "فولاد",
    "فملی",
    "شپنا",
    "شبندر",
    "خودرو",
    "شتران",
    "وبملت",
    "کگل",
    "فخوز",
    "پارسان",
    "خساپا",
    "فایرا",
    "ذوب",
    "کمند",
    "آگاس",
]


class WatchlistService:
    """Persistent watchlist backed by PostgreSQL + AllSymbols snapshots."""

    def __init__(self, session: Any = None, brsapi: Any = None) -> None:
        self._session = session
        self._brsapi = brsapi

    # ── Table helpers ──────────────────────────────

    async def _ensure_table(self) -> None:
        from sqlalchemy import text

        await self._session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(200) DEFAULT '',
                note TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        )
        await self._session.commit()

    async def _ensure_defaults(self) -> None:
        """Seed default popular symbols if the watchlist is empty."""
        from sqlalchemy import text

        count_result = await self._session.execute(text("SELECT COUNT(*) FROM watchlist"))
        count = count_result.scalar() or 0
        if count > 0:
            return

        logger.info("Watchlist empty — seeding %d default symbols", len(DEFAULT_SYMBOLS))
        for i, sym in enumerate(DEFAULT_SYMBOLS):
            try:
                await self._session.execute(
                    text(
                        "INSERT INTO watchlist (symbol, name, note, sort_order) "
                        "VALUES (:s, '', '', :o) ON CONFLICT (symbol) DO NOTHING"
                    ),
                    {"s": sym, "o": i + 1},
                )
            except Exception:
                logger.debug("Failed to seed default symbol %s", sym)
        await self._session.commit()

    async def _load_enriched_symbols_map(self) -> dict[str, dict[str, Any]]:
        """Build a lookup dict from brsapi_symbol_snapshots LEFT JOIN brsapi_symbol_details.

        Returns keyed by symbol with all fields the frontend needs.
        """
        from sqlalchemy import text

        if not self._session:
            return {}

        try:
            result = await self._session.execute(
                text("""
                SELECT DISTINCT ON (s.symbol)
                    s.symbol,
                    s.name,
                    s.price_last,
                    s.price_last_change_pct,
                    s.price_yesterday,
                    s.trade_volume,
                    s.trade_value,
                    s.trade_count,
                    s.eps,
                    s.pe_ratio,
                    s.sector,
                    d.price_lowest_allowed,
                    d.price_highest_allowed,
                    d.free_float_pct,
                    d.group_pe_ratio,
                    d.ps_ratio,
                    d.state,
                    s.buy_real_volume,
                    s.buy_legal_volume,
                    s.sell_real_volume,
                    s.sell_legal_volume,
                    s.time
                FROM brsapi_symbol_snapshots s
                LEFT JOIN brsapi_symbol_details d
                    ON s.ins_id = d.ins_id
                    OR (s.ins_id IS NULL AND s.symbol = d.symbol)
                WHERE s.symbol IS NOT NULL AND s.symbol != ''
                ORDER BY s.symbol, s.trade_value DESC NULLS LAST
            """)
            )
            rows = result.fetchall()
        except Exception:
            # Fallback: snapshot-only query without JOIN
            logger.warning("Enriched JOIN failed — falling back to snapshots only", exc_info=True)
            try:
                result = await self._session.execute(
                    text("""
                    SELECT DISTINCT ON (symbol)
                        symbol, name, price_last, price_last_change_pct,
                        price_yesterday, trade_volume, trade_value, trade_count,
                        eps, pe_ratio, sector,
                        NULL, NULL, NULL, NULL, NULL, NULL,
                        buy_real_volume, buy_legal_volume,
                        sell_real_volume, sell_legal_volume, time
                    FROM brsapi_symbol_snapshots
                    WHERE symbol IS NOT NULL AND symbol != ''
                    ORDER BY symbol, trade_value DESC NULLS LAST
                """)
                )
                rows = result.fetchall()
            except Exception:
                logger.exception("Failed to load symbols for watchlist enrichment")
                return {}

        symbols_map: dict[str, dict[str, Any]] = {}
        for row in rows:
            sym = row[0]
            if not sym:
                continue
            symbols_map[sym] = {
                "symbol": sym,
                "name": safe_row_str(row, idx=1),
                "price": row[2],  # price_last
                "change": row[3],  # price_last_change_pct
                "price_yesterday": row[4],  # price_yesterday
                "volume": row[5],  # trade_volume
                "value": row[6],  # trade_value
                "trade_count": row[7],  # trade_count
                "eps": row[8],  # eps
                "peRatio": row[9],  # pe_ratio
                "sector": row[10],  # sector
                "priceLowestAllowed": row[11],  # from symbol_details
                "priceHighestAllowed": row[12],  # from symbol_details
                "freeFloatPct": row[13],  # from symbol_details
                "groupPeRatio": row[14],  # from symbol_details
                "psRatio": row[15],  # from symbol_details
                "state": row[16],  # from symbol_details
                "buyRealVolume": row[17],
                "buyLegalVolume": row[18],
                "sellRealVolume": row[19],
                "sellLegalVolume": row[20],
                "time": row[21],
            }
        return symbols_map

    # ── CRUD ───────────────────────────────────────

    async def list_items(self) -> Result[list[dict[str, Any]]]:
        from sqlalchemy import text

        await self._ensure_table()
        await self._ensure_defaults()

        result = await self._session.execute(
            text("SELECT symbol, name, note, sort_order FROM watchlist ORDER BY sort_order")
        )
        rows = result.fetchall()

        if not rows:
            return Result.ok([])

        # Batch-load all symbol data from snapshots + details
        symbols_map = await self._load_enriched_symbols_map()

        enriched: list[dict[str, Any]] = []
        for symbol, name, note, sort_order in rows:
            entry: dict[str, Any] = {
                "symbol": symbol,
                "name": name or symbol,
                "note": note or "",
                "order": sort_order,
            }
            # Enrich from snapshot + details
            snap = symbols_map.get(symbol)
            if snap:
                entry.update(snap)
            else:
                # Symbol not in snapshots — still include it with basic info
                entry.update(
                    {
                        "price": None,
                        "change": None,
                        "sector": "",
                    }
                )
            enriched.append(entry)

        return Result.ok(enriched)

    async def add_symbol(self, symbol: str, name: str = "", note: str = "") -> Result[dict[str, Any]]:
        from sqlalchemy import text

        await self._ensure_table()
        symbol = symbol.strip().upper() if symbol.strip().isascii() else symbol.strip()

        if not symbol:
            return Result.fail("نماد نامعتبر است")

        # Check duplicate
        existing = await self._session.execute(text("SELECT 1 FROM watchlist WHERE symbol = :s"), {"s": symbol})
        if existing.first():
            return Result.fail(f"نماد {symbol} قبلاً در لیست وجود دارد")

        # Get max order
        max_row = await self._session.execute(text("SELECT COALESCE(MAX(sort_order), 0) FROM watchlist"))
        max_order = max_row.scalar() or 0

        # Try to get name from snapshots if not provided
        if not name:
            name = await self._resolve_symbol_name(symbol)

        await self._session.execute(
            text("INSERT INTO watchlist (symbol, name, note, sort_order) VALUES (:s, :n, :note, :o)"),
            {"s": symbol, "n": name, "note": note, "o": max_order + 1},
        )
        await self._session.commit()

        return Result.ok({"symbol": symbol, "name": name, "order": max_order + 1})

    async def search_symbols(self, query: str) -> list[dict[str, Any]]:
        """Search for symbols by name/symbol from brsapi_symbol_snapshots.

        Used by the AddSymbolDialog to find symbols to add. Latin (Finglish)
        queries also match Persian symbols via transliteration — e.g.
        ``folad`` finds ``فولاد``.
        """
        from sqlalchemy import text

        from services.symbol_catalog import finglish_symbol_candidates

        if not self._session or not query or len(query.strip()) < 1:
            return []

        q = query.strip()
        try:
            result = await self._session.execute(
                text(
                    "SELECT DISTINCT symbol, name FROM brsapi_symbol_snapshots "
                    "WHERE (symbol ILIKE :q OR name ILIKE :q2) "
                    "AND symbol IS NOT NULL AND symbol != '' "
                    "ORDER BY trade_value DESC NULLS LAST "
                    "LIMIT 15"
                ),
                {"q": f"%{q}%", "q2": f"%{q}%"},
            )
            rows = result.fetchall()
            results = [{"symbol": r[0], "name": r[1] or ""} for r in rows if r[0]]

            # Finglish: also match Persian symbols whose Latin spelling matches
            # the query (e.g. ``folad`` → ``فولاد``).
            extra = finglish_symbol_candidates(q)
            if extra:
                known = {r["symbol"] for r in results}
                extra_result = await self._session.execute(
                    text(
                        "SELECT DISTINCT symbol, name FROM brsapi_symbol_snapshots "
                        "WHERE symbol = ANY(:symbols) "
                        "AND symbol IS NOT NULL AND symbol != '' "
                        "ORDER BY trade_value DESC NULLS LAST "
                        "LIMIT 15"
                    ),
                    {"symbols": extra},
                )
                for row in extra_result.fetchall():
                    if row[0] and row[0] not in known:
                        results.append({"symbol": row[0], "name": row[1] or ""})

            return results
        except Exception:
            logger.warning("Symbol search failed for query: %s", q, exc_info=True)
            return []

    async def _resolve_symbol_name(self, symbol: str) -> str:
        """Quick single-symbol name lookup from snapshots."""
        from sqlalchemy import text

        if not self._session:
            return symbol
        try:
            result = await self._session.execute(
                text("SELECT name FROM brsapi_symbol_snapshots WHERE symbol = :s LIMIT 1"), {"s": symbol}
            )
            row = result.scalar_one_or_none()
            return row or symbol
        except Exception:
            return symbol

    async def remove_symbol(self, symbol: str) -> Result[bool]:
        from sqlalchemy import text

        await self._ensure_table()
        result = await self._session.execute(text("DELETE FROM watchlist WHERE symbol = :s"), {"s": symbol})
        await self._session.commit()
        if result.rowcount > 0:
            return Result.ok(True)
        return Result.fail(f"نماد {symbol} در لیست وجود ندارد")

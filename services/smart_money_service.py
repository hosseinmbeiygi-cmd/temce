"""Smart Money Service — uses real data from brsapi tables.

No mock data. When symbol or quote data is not found in DB,
returns an error instead of fabricated scores.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.result import Result
from services.smart_money.scoring_engine import ScoringEngine

logger = get_logger(__name__)


class SmartMoneyService:
    def __init__(self, session: AsyncSession | None = None, brsapi_query_service: Any = None) -> None:
        self._engine = ScoringEngine()
        self._session = session
        self._brsapi = brsapi_query_service

    async def analyze(self, symbol: str) -> Result[dict[str, Any]]:
        """Analyze a symbol using real data from brsapi_symbol_snapshots + brsapi_historical_daily."""
        # 1. Get current quote from snapshot
        quote_raw = await self._get_quote_from_snapshot(symbol)
        if not quote_raw:
            return Result.fail(f"Symbol {symbol} not found in database — no snapshot data available")

        # 2. Get historical data
        history = await self._get_history(symbol)

        # 3. Run scoring engine
        result = self._engine.analyze(quote=quote_raw, history=history)
        logger.info(
            "Smart money analysis for %s: SMC=%.4f phase=%s (history_days=%d)",
            symbol, result["smart_money_score"], result["phase"], len(history),
        )
        return Result.ok(result)

    async def _get_quote_from_snapshot(self, symbol: str) -> dict[str, Any] | None:
        """Build engine quote from brsapi_symbol_snapshots."""
        if self._brsapi:
            try:
                snap = await self._brsapi.get_symbol_snapshot(symbol)
                if snap:
                    return self._build_quote_from_snapshot(snap)
            except Exception:
                logger.exception("Failed to get snapshot for %s", symbol)

        # Fallback: query directly from session
        if self._session:
            try:
                from sqlalchemy import text
                result = await self._session.execute(
                    text("SELECT * FROM brsapi_symbol_snapshots WHERE symbol = :sym ORDER BY created_at DESC LIMIT 1"),
                    {"sym": symbol},
                )
                row = result.mappings().first()
                if row:
                    return self._build_quote_from_snapshot(dict(row))
            except Exception:
                logger.exception("Direct snapshot query failed for %s", symbol)

        return None

    @staticmethod
    def _build_quote_from_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
        """Map snapshot fields to engine-expected quote dict."""
        close = float(snap.get("price_close") or 0)
        open_ = float(snap.get("price_first") or close)
        high = float(snap.get("price_max") or close)
        low = float(snap.get("price_min") or close)
        last = float(snap.get("price_last") or close)
        volume = int(snap.get("trade_volume") or 0)
        value = float(snap.get("trade_value") or 0)

        buy_real_vol = int(snap.get("buy_real_volume") or 0)
        buy_legal_vol = int(snap.get("buy_legal_volume") or 0)
        sell_real_vol = int(snap.get("sell_real_volume") or 0)
        sell_legal_vol = int(snap.get("sell_legal_volume") or 0)
        buy_real_cnt = int(snap.get("buy_real_count") or 0)
        buy_legal_cnt = int(snap.get("buy_legal_count") or 0)
        sell_real_cnt = int(snap.get("sell_real_count") or 0)
        sell_legal_cnt = int(snap.get("sell_legal_count") or 0)

        total_buy_vol = buy_real_vol + buy_legal_vol
        total_sell_vol = sell_real_vol + sell_legal_vol
        total_buy_cnt = buy_real_cnt + buy_legal_cnt
        total_sell_cnt = sell_real_cnt + sell_legal_cnt

        avg_buy = (total_buy_vol / total_buy_cnt) if total_buy_cnt > 0 else 0.0
        avg_sell = (total_sell_vol / total_sell_cnt) if total_sell_cnt > 0 else 0.0

        avg_price = (high + low + close) / 3.0 if (high + low + close) else close or 1.0
        real_buy_value = buy_real_vol * avg_price
        real_sell_value = sell_real_vol * avg_price

        return {
            "symbol": snap.get("symbol", ""),
            "price_open": open_,
            "price_close": close,
            "price_high": high,
            "price_low": low,
            "price_last": last,
            "price_change": float(snap.get("price_last_change") or 0),
            "price_change_pct": float(snap.get("price_last_change_pct") or 0),
            "volume": volume,
            "value": value,
            "trade_count": int(snap.get("trade_count") or max(1, volume // 5000)),
            "avg_buy": avg_buy,
            "avg_sell": avg_sell,
            "real_buy_value": real_buy_value,
            "real_sell_value": real_sell_value,
            "real_buy_count": buy_real_cnt,
            "real_sell_count": sell_real_cnt,
            "date": snap.get("date", ""),
            "time": snap.get("time", ""),
        }

    async def _get_history(self, symbol: str, limit: int = 60) -> list[dict[str, Any]]:
        """Fetch real daily history from brsapi_historical_daily."""
        if not self._session:
            return []

        from sqlalchemy import text

        try:
            q = text("""
                SELECT symbol, date, price_first as price_open, price_close,
                       price_max as price_high, price_min as price_low,
                       price_last, trade_volume as volume, trade_value as value,
                       trade_count
                FROM brsapi_historical_daily
                WHERE symbol = :sym
                ORDER BY date DESC
                LIMIT :lim
            """)
            result = await self._session.execute(q, {"sym": symbol, "lim": limit})
            rows = [dict(row._mapping) for row in result.fetchall()]

            # Reverse to chronological order (oldest first)
            rows.reverse()

            # Enrich with real/legal data
            rl_q = text("""
                SELECT date, buy_real_volume, sell_real_volume,
                       buy_real_count, sell_real_count,
                       buy_legal_volume, sell_legal_volume,
                       buy_legal_count, sell_legal_count
                FROM brsapi_historical_real_legal
                WHERE symbol = :sym
                ORDER BY date DESC
                LIMIT :lim
            """)
            rl_result = await self._session.execute(rl_q, {"sym": symbol, "lim": limit})
            rl_by_date = {dict(row._mapping)["date"]: dict(row._mapping) for row in rl_result.fetchall()}

            enriched = []
            for row in rows:
                dt = row.get("date", "")
                rl = rl_by_date.get(dt, {})
                close = float(row.get("price_close") or 0)
                high = float(row.get("price_high") or close)
                low = float(row.get("price_low") or close)

                buy_real_vol = int(rl.get("buy_real_volume") or 0)
                sell_real_vol = int(rl.get("sell_real_volume") or 0)
                buy_real_cnt = int(rl.get("buy_real_count") or 0)
                sell_real_cnt = int(rl.get("sell_real_count") or 0)
                buy_legal_vol = int(rl.get("buy_legal_volume") or 0)
                sell_legal_vol = int(rl.get("sell_legal_volume") or 0)
                buy_legal_cnt = int(rl.get("buy_legal_count") or 0)
                sell_legal_cnt = int(rl.get("sell_legal_count") or 0)

                total_buy_vol = buy_real_vol + buy_legal_vol
                total_sell_vol = sell_real_vol + sell_legal_vol
                total_buy_cnt = buy_real_cnt + buy_legal_cnt
                total_sell_cnt = sell_real_cnt + sell_legal_cnt

                avg_buy = (total_buy_vol / total_buy_cnt) if total_buy_cnt > 0 else 0.0
                avg_sell = (total_sell_vol / total_sell_cnt) if total_sell_cnt > 0 else 0.0
                avg_price = (high + low + close) / 3.0 if (high + low + close) else close or 1.0

                enriched.append({
                    **row,
                    "avg_buy": avg_buy,
                    "avg_sell": avg_sell,
                    "real_buy_value": buy_real_vol * avg_price,
                    "real_sell_value": sell_real_vol * avg_price,
                    "real_buy_count": buy_real_cnt,
                    "real_sell_count": sell_real_cnt,
                })

            return enriched
        except Exception:
            logger.exception("Failed to fetch history for %s", symbol)
            return []

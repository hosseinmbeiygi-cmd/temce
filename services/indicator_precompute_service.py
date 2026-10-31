"""📐 Indicator Precompute Service — موتور ساعات غیربازاری (Overnight Engine).

بخش ۱.۱ معماری Enterprise سهام:
  - برای همه نمادهای فعال، کندل‌های روزانه (تعدیل‌شده با رویدادهای شرکتی)
    خوانده و compute_indicator_snapshot روی آن‌ها اجرا می‌شود.
  - نتیجه به‌صورت idempotent (symbol, trade_date) در stock_indicators_snapshot
    upsert می‌شود تا خواندن فرانت از DB زیر ۵۰ms باشد (بدون JIT).
  - Batch-based با سقف per-run برای کنترل بار DB در شب.

No Look-Ahead: هر snapshot فقط با کندل‌های تا همان تاریخ محاسبه می‌شود
(کل دنباله تا trade_date — اندیکاتورها ذاتاً causal هستند).
"""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.time import utc_now_naive
from models.stock_enterprise import StockIndicatorsSnapshotModel
from services.adjusted_price_reader import (
    AdjustedPriceSourceUnavailable,
    load_daily_candles,
)
from services.stock_technical_engine import compute_indicator_snapshot

logger = get_logger(__name__)


class IndicatorPrecomputeService:
    """Precompute اندیکاتورهای روزانه برای کل بازار (شبانه)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(
        self,
        *,
        batch_limit: int = 400,
        symbol: str | None = None,
        lookback_days: int = 320,
    ) -> dict[str, int]:
        """محاسبه و upsert snapshot اندیکاتورها.

        - ``symbol`` داده شود فقط همان نماد (برای retry انفرادی).
        - ``batch_limit`` سقف تعداد نماد per run است تا Job شبانه در چند
          شبه توزیع شود (سهم از کل بازار ~۱۲۰۰ نماد فعال).
        """
        stats = {"symbols": 0, "snapshots": 0, "errors": 0, "skipped": 0}

        rows = await self._select_symbols(batch_limit, symbol)

        for row in rows:
            sym, last_date = row[0], row[1]
            if last_date is None:
                stats["skipped"] += 1
                continue
            try:
                saved = await self._compute_symbol(str(sym), last_date, lookback_days)
                if saved:
                    stats["snapshots"] += saved
                    stats["symbols"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as exc:  # noqa: BLE001 — هر نماد مستقل است
                logger.debug("indicator precompute failed for %s: %s", sym, exc)
                stats["errors"] += 1

        await self.session.flush()
        return stats

    async def _select_symbols(
        self, batch_limit: int, symbol: str | None
    ) -> list[tuple[str, date]]:
        """Symbols to process + their latest **true** trade date, cheaply.

        The obvious form — ``SELECT symbol, MAX(trade_date) FROM daily_history
        WHERE price_last IS NOT NULL GROUP BY symbol`` — reads every row of the
        view (which itself LEFT JOINs ``symbols``) and measured **70.8 s** on
        the dev DB. The lateral rewrite probes ``idx_hist_symbol_date`` once
        per symbol instead: **11 ms**, same ordering.

        It reads ``brsapi_historical_daily`` (the table behind the
        ``daily_history`` view) on purpose: this step only needs metadata, so
        the ``symbols`` join of the view would be pure overhead, and
        ``h.date`` is the true trade date (Shamsi) whose Gregorian form the
        snapshot is keyed on. Ordering by ``h.date`` — not by
        ``jalali_to_gregorian(h.date)`` — keeps the index scan (Shamsi
        ``YYYY-MM-DD`` sorts chronologically), and the converter then runs
        once per symbol instead of once per row.

        Note this query is deliberately NOT routed through the adjusted view —
        a MAX(date) needs no price adjustment, and joining 10M rows for it
        would be wasted work.
        """
        symbol_filter = "AND symbol = :symbol" if symbol else ""
        rows = (
            await self.session.execute(
                text(
                    f"""
                    SELECT s.symbol, l.last_date
                    FROM (
                        SELECT DISTINCT symbol
                        FROM brsapi_historical_daily
                        WHERE symbol IS NOT NULL {symbol_filter}
                    ) s
                    CROSS JOIN LATERAL (
                        SELECT jalali_to_gregorian(h.date) AS last_date
                        FROM brsapi_historical_daily h
                        WHERE h.symbol = s.symbol AND h.price_last IS NOT NULL
                        ORDER BY h.date DESC
                        LIMIT 1
                    ) l
                    ORDER BY s.symbol
                    LIMIT :lim
                    """
                ),
                {"lim": batch_limit, "symbol": symbol},
            )
        ).fetchall()
        return [(str(r[0]), r[1]) for r in rows]

    async def _compute_symbol(
        self, symbol: str, last_date: date, lookback_days: int
    ) -> int:
        """محاسبه snapshot آخرین روز یک نماد؛ اگر از قبل هست skip می‌شود."""
        existing = (
            await self.session.execute(
                select(StockIndicatorsSnapshotModel.symbol).where(
                    StockIndicatorsSnapshotModel.symbol == symbol,
                    StockIndicatorsSnapshotModel.trade_date == last_date,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return 0  # idempotent — از قبل محاسبه شده

        candles = await self._load_candles(symbol, lookback_days)
        if len(candles) < 30:  # حداقل داده برای اندیکاتورهای معنادار
            return 0

        snapshot = compute_indicator_snapshot(candles)
        if not snapshot.get("ok"):
            return 0

        # ── نگاشت خروجی موتور تکنیکال → ستون‌های جدول ──
        ich = snapshot.get("ichimoku") or {}
        pivots = snapshot.get("pivots") or {}
        bb = {k: snapshot.get(f"bb_{k}") for k in ("upper", "middle", "lower")}
        squeeze = snapshot.get("squeeze")
        div = snapshot.get("rsi_divergence")
        div_str = (div.get("type") if isinstance(div, dict) else div) or "none"

        flat: dict[str, object] = {
            "rsi_14": snapshot.get("rsi_14"),
            "rsi_divergence": str(div_str)[:10],
            "macd": snapshot.get("macd"),
            "macd_signal": snapshot.get("macd_signal"),
            "macd_hist": snapshot.get("macd_hist"),
            "ema_20": snapshot.get("ema_20"),
            "ema_50": snapshot.get("ema_50"),
            "ema_100": snapshot.get("ema_100"),
            "ema_200": snapshot.get("ema_200"),
            "ema_cross": (snapshot.get("ema_cross") or "none")[:20],
            "bb_upper": bb.get("upper"),
            "bb_middle": bb.get("middle"),
            "bb_lower": bb.get("lower"),
            "bb_squeeze": squeeze == "squeeze" if squeeze is not None else None,
            "keltner_upper": None,  # در snapshot برنمی‌گردد؛ فقط برای squeeze استفاده شده
            "keltner_lower": None,
            "ichimoku_tenkan": ich.get("tenkan"),
            "ichimoku_kijun": ich.get("kijun"),
            "ichimoku_senkou_a": ich.get("senkou_a"),
            "ichimoku_senkou_b": ich.get("senkou_b"),
            "ichimoku_state": (ich.get("state") or "insufficient")[:20],
            "atr_14": snapshot.get("atr_14"),
            "mfi_14": snapshot.get("mfi_14"),
            "vwap_daily": snapshot.get("vwap_daily"),
            "pivot_standard_json": json.dumps(pivots.get("classic"), ensure_ascii=False) if pivots.get("classic") is not None else None,
            "pivot_camarilla_json": json.dumps(pivots.get("camarilla"), ensure_ascii=False) if pivots.get("camarilla") is not None else None,
            "pivot_fibonacci_json": json.dumps(pivots.get("fibonacci"), ensure_ascii=False) if pivots.get("fibonacci") is not None else None,
            "trend_alignment_score": snapshot.get("trend_alignment_score"),
        }

        values: dict[str, object] = {
            "symbol": symbol,
            "trade_date": last_date,
            "computed_at": utc_now_naive(),
            **flat,
        }

        stmt = (
            pg_insert(StockIndicatorsSnapshotModel)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_stock_ind",
                set_=dict(flat),
            )
        )
        await self.session.execute(stmt)
        return 1

    async def _load_candles(self, symbol: str, limit: int) -> list[dict[str, object]]:
        """Adjusted OHLCV candles (see ``services/adjusted_price_reader.py``).

        Adjusting here (rather than at the raw table) is what makes the whole
        snapshot column set — MA/EMA, RSI, MACD, Bollinger, Ichimoku, ATR,
        pivots — corporate-action safe: every one of them is a function of the
        close series handed to ``compute_indicator_snapshot``.

        DB-04: no silent raw fallback. A missing adjusted view yields an empty
        series (snapshot reports "not ok"), never indicators over fetch dates.
        """
        try:
            return await load_daily_candles(self.session, symbol, limit)
        except AdjustedPriceSourceUnavailable as exc:
            logger.error("precompute skipped %s: %s", symbol, exc)
            return []


__all__ = ["IndicatorPrecomputeService"]

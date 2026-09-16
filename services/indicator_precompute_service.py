"""📐 Indicator Precompute Service — موتور ساعات غیربازاری (Overnight Engine).

بخش ۱.۱ معماری Enterprise سهام:
  - برای همه نمادهای فعال، کندل‌های روزانه از daily_history خوانده و
    compute_indicator_snapshot روی آن‌ها اجرا می‌شود.
  - نتیجه به‌صورت idempotent (symbol, trade_date) در stock_indicators_snapshot
    upsert می‌شود تا خواندن فرانت از DB زیر ۵۰ms باشد (بدون JIT).
  - Batch-based با سقف per-run برای کنترل بار DB در شب.

No Look-Ahead: هر snapshot فقط با کندل‌های تا همان تاریخ محاسبه می‌شود
(کل دنباله تا trade_date — اندیکاتورها ذاتاً causal هستند).
"""

from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from models.stock_enterprise import StockIndicatorsSnapshotModel
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

        symbol_filter = "WHERE d.symbol = :symbol" if symbol else ""
        params: dict[str, object] = {"lim": batch_limit, "symbol": symbol}
        rows = (
            await self.session.execute(
                text(
                    f"""
                    SELECT d.symbol, MAX(d.trade_date) AS last_date
                    FROM daily_history d
                    WHERE d.price_last IS NOT NULL {symbol_filter}
                    GROUP BY d.symbol
                    ORDER BY d.symbol
                    LIMIT :lim
                    """
                ),
                params,
            )
        ).fetchall()

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
            "computed_at": datetime.utcnow(),
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
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT d.trade_date, d.price_first, d.price_max, d.price_min,
                           d.price_last, d.trade_volume, d.trade_value
                    FROM daily_history d
                    WHERE d.symbol = :sym AND d.price_last IS NOT NULL
                    ORDER BY d.trade_date DESC LIMIT :lim
                    """
                ),
                {"sym": symbol, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "date": str(r[0]),
                "open": float(r[1] or r[4]),
                "high": float(r[2] or r[4]),
                "low": float(r[3] or r[4]),
                "close": float(r[4]),
                "volume": float(r[5] or 0),
                "value": float(r[6] or 0),
            }
            for r in reversed(rows)
        ]


__all__ = ["IndicatorPrecomputeService"]

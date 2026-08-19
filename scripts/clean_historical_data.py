#!/usr/bin/env python
"""
Clean Historical Data — پاکسازی داده‌های تاریخی brsapi_historical_daily
======================================================================

عملیات (روی brsapi_historical_daily):
  1. حذف ردیف‌های با قیمت بسته‌شدن صفر یا حجم صفر
  2. حذف تاریخ‌های تکراری (نگه‌داشتن آخرین رکورد — max id) برای هر (symbol, gregorian_date)
  3. شناسایی Outlierها: قیمت > ۵ برابر میانگین متحرک ۲۰ روزه
  4. ایجاد View پاک: ``vw_clean_daily_history`` (در migration 0036 — اینجا فقط read)

⚠️ --dry-run فقط گزارش می‌دهد و چیزی را تغییر نمی‌دهد.
⚠️ روی داده‌های واقعی اجرا نشود مگر با پشتیبان‌گیری (backup) قبلی.

Usage:
    python scripts/clean_historical_data.py --dry-run      # فقط گزارش
    python scripts/clean_historical_data.py                # اعمال واقعی (با پشتیبان)
    python scripts/clean_historical_data.py --symbols فولاد,خودرو
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from sqlalchemy import text  # noqa: E402

from core.database import init_database, get_session  # noqa: E402
from core.logging import get_logger  # noqa: E402

logger = get_logger(__name__)

OUTLIER_FACTOR = 5.0   # قیمت > ۵ برابر میانگین متحرک ۲۰ روزه
MA_WINDOW = 20


# ═══════════════════════════════════════════════════════════════════════════
#  CLEANER
# ═══════════════════════════════════════════════════════════════════════════

async def clean_historical_data(
    session: Any,
    *,
    dry_run: bool = True,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """Run the cleanup pipeline. Returns stats."""
    started_at = time.monotonic()
    stats: dict[str, Any] = {"dry_run": dry_run}

    symbol_filter = ""
    params: dict[str, Any] = {}
    if symbols:
        symbol_filter = " AND symbol = ANY(:syms)"
        params["syms"] = symbols

    # ── 1. حذف قیمت/حجم صفر (دریافت تعداد) ──
    zero_stats = (await session.execute(text(f"""
        SELECT
            COUNT(*) FILTER (WHERE price_close IS NULL OR price_close <= 0)
                AS bad_price,
            COUNT(*) FILTER (WHERE trade_volume IS NULL OR trade_volume <= 0)
                AS bad_volume
        FROM brsapi_historical_daily
        WHERE 1=1 {symbol_filter}
    """), params)).fetchone()
    stats["zero_price_rows"] = zero_stats.bad_price or 0
    stats["zero_volume_rows"] = zero_stats.bad_volume or 0

    # ── 2. تاریخ‌های تکراری — تعداد ردیف‌های اضافی ──
    dup_stats = (await session.execute(text(f"""
        SELECT COUNT(*) AS dup_rows
        FROM (
            SELECT symbol, gregorian_date, COUNT(*) AS cnt
            FROM brsapi_historical_daily
            WHERE gregorian_date IS NOT NULL {symbol_filter}
            GROUP BY symbol, gregorian_date
            HAVING COUNT(*) > 1
        ) d
    """), params)).fetchone()
    stats["duplicate_date_rows"] = dup_stats.dup_rows or 0

    # ── 3. Outlierها — قیمت > ۵x میانگین متحرک ۲۰ روزه ──
    outlier_stats = (await session.execute(text(f"""
        WITH base AS (
            SELECT id, symbol, gregorian_date, price_close,
                   AVG(price_close) OVER (
                       PARTITION BY symbol ORDER BY gregorian_date
                       ROWS BETWEEN {MA_WINDOW - 1} PRECEDING AND CURRENT ROW
                   ) AS ma_20
            FROM brsapi_historical_daily
            WHERE price_close > 0 AND gregorian_date IS NOT NULL {symbol_filter}
        )
        SELECT COUNT(*) AS outliers
        FROM base
        WHERE ma_20 > 0 AND price_close > :factor * ma_20
    """), {**params, "factor": OUTLIER_FACTOR})).fetchone()
    stats["outlier_rows"] = outlier_stats.outliers or 0

    stats["total_candidates"] = (
        stats["zero_price_rows"] + stats["zero_volume_rows"]
        + stats["duplicate_date_rows"] + stats["outlier_rows"]
    )

    # ── اعمال واقعی (اگر dry_run نباشد) ──
    if not dry_run:
        # 1. حذف ردیف‌های با قیمت/حجم صفر
        del_price = await session.execute(text(f"""
            DELETE FROM brsapi_historical_daily
            WHERE (price_close IS NULL OR price_close <= 0)
               OR (trade_volume IS NULL OR trade_volume <= 0) {symbol_filter}
        """), params)
        stats["deleted_zero_rows"] = del_price.rowcount

        # 2. حذف ردیف‌های تکراری — نگه‌داشتن max(id) برای هر (symbol, gregorian_date)
        dup_del = await session.execute(text(f"""
            DELETE FROM brsapi_historical_daily h
            USING brsapi_historical_daily d
            WHERE h.symbol = d.symbol
              AND h.gregorian_date = d.gregorian_date
              AND h.id < d.id
              AND h.gregorian_date IS NOT NULL {symbol_filter}
        """), params)
        stats["deleted_duplicate_rows"] = dup_del.rowcount

        # 3. Outlierها — فقط گزارش (پیشنهاد: حذف نشود، نگه‌داری برای تحلیل)
        stats["outliers_kept"] = stats["outlier_rows"]

        await session.commit()
        logger.info("Cleanup applied: %s", stats)
    else:
        logger.info("Dry-run — nothing changed: %s", stats)

    stats["duration_ms"] = round((time.monotonic() - started_at) * 1000, 1)

    # لاگ در brsapi_sync_log (فقط برای اجراهای واقعی)
    if not dry_run:
        try:
            await session.execute(
                text("""
                    INSERT INTO brsapi_sync_log
                        (endpoint, category, status, items_count, duration_ms,
                         params_snapshot, started_at, completed_at, gregorian_date)
                    VALUES
                        (:endpoint, 'cleanup', 'OK', :items_count, :duration_ms,
                         :params_snapshot, :started_at, :completed_at, CURRENT_DATE)
                """),
                {
                    "endpoint": "clean_historical_data",
                    "items_count": stats.get("deleted_zero_rows", 0)
                                 + stats.get("deleted_duplicate_rows", 0),
                    "duration_ms": stats["duration_ms"],
                    "params_snapshot": f"dry_run={dry_run},symbols={len(symbols) if symbols else 'all'}",
                    "started_at": __import__("datetime").datetime.fromtimestamp(started_at),
                    "completed_at": __import__("datetime").datetime.now(),
                },
            )
            await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to write sync log for cleanup")

    return stats


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

async def main() -> None:
    parser = argparse.ArgumentParser(description="Clean brsapi_historical_daily")
    parser.add_argument("--apply", action="store_true",
                        help="Actually apply the cleanup (backup first!) — default is dry-run")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Comma-separated symbols to scope the cleanup")
    args = parser.parse_args()

    await init_database()

    dry_run = not args.apply
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] if args.symbols else None

    async for session in get_session():
        stats = await clean_historical_data(session, dry_run=dry_run, symbols=symbols)
        print(f"{'🔍 Dry-run' if dry_run else '🧹 Applied'} — {stats}")
        return


if __name__ == "__main__":
    asyncio.run(main())

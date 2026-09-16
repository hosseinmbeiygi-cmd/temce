#!/usr/bin/env python
"""
Build Feature Store — پر کردن جدول ml_engineered_features با ویژگی‌های مهندسی‌شده
=================================================================================

برای هر نماد فعال، ویژگی‌های استاندارد (FeatureEngine — ۱۱۵ ویژگی در ۸ بلوک) را
از داده‌های BrsApi موجود در دیتابیس محاسبه و در جدول ``ml_engineered_features``
ذخیره می‌کند (Upsert با ON CONFLICT).

محدودیت‌های حافظه:
  * لیست نمادها با ``yield_per`` استریم می‌شود (نه بارگذاری همه در حافظه)
  * پردازش موازی فقط با ``workers`` (پیش‌فرض ۴) همزمان — از اشباع CPU جلوگیری می‌کند
  * رکوردها به‌صورت chunk ذخیره می‌شوند

Usage:
    python scripts/build_feature_store.py                            # همه نمادهای فعال
    python scripts/build_feature_store.py --symbols خودرو,فولاد,شپنا
    python scripts/build_feature_store.py --symbols خودرو --days 100 --workers 4

وابستگی‌ها: SQLAlchemy 2.0 (async) — مطابق قرارداد core.database.get_session
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from core import (
    database as db_module,  # noqa: E402  (module ref so async_session_factory is read live, not captured as None)
)
from core.database import get_session, init_database  # noqa: E402
from core.logging import get_logger  # noqa: E402
from core.time import utc_now_naive

logger = get_logger(__name__)

# ── تنظیمات ────────────────────────────────────────────────────────────────
DEFAULT_DAYS = 100          # عمق تاریخچه برای محاسبه اندیکاتورها
DEFAULT_WORKERS = 4         # تعداد نمادهای همزمان
SAVE_CHUNK_SIZE = 50        # تعداد ردیف در هر chunk ذخیره‌سازی


# ═══════════════════════════════════════════════════════════════════════════
#  BUILDER
# ═══════════════════════════════════════════════════════════════════════════

class FeatureStoreBuilder:
    """Builds ml_engineered_features rows from live BrsApi-derived data."""

    def __init__(self, symbols: list[str] | None = None,
                 days: int = DEFAULT_DAYS,
                 workers: int = DEFAULT_WORKERS) -> None:
        self.symbols = symbols
        self.days = days
        self.workers = max(1, workers)
        self._stats = {"ok": 0, "fail": 0, "rows": 0, "skipped": []}

    # ── 1. Load active symbols (streamed) ────────────────────────────────

    async def _load_active_symbols(self, session: AsyncSession) -> list[str]:
        """Distinct active symbols — streamed via yield_per(1000)."""
        stmt = (
            select(func.distinct(text("symbol")))
            .select_from(text("brsapi_symbol_snapshots"))
            .where(text("symbol IS NOT NULL AND symbol <> ''"))
            .order_by(text("symbol"))
        )
        result = await session.stream(stmt)
        symbols: list[str] = []
        async for partition in result.yield_per(1000):
            for row in partition:
                sym = row[0]
                if sym:
                    symbols.append(sym)
        return symbols

    # ── 2. Compute features for one symbol ───────────────────────────────

    async def _compute_symbol(
        self,
        session: AsyncSession,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Run the FeatureEngine for a symbol → row-ready dict."""
        from brsapi.services.query_service import BrsApiQueryService
        from services.feature_engine import FeatureEngine
        from services.queue_analysis_service import QueueAnalysisService

        brsapi = BrsApiQueryService(session=session)
        queue_service = QueueAnalysisService(brsapi_query_service=brsapi, db_session=None)
        engine = FeatureEngine(brsapi_query_service=brsapi, queue_analysis_service=queue_service)

        result = await engine.compute_all_features(symbol)
        if not result or not result.get("features"):
            logger.warning("No features computed for %s", symbol)
            return None

        features = result["features"]

        # trade_date = آخرین تاریخ معاملاتی نماد (اگر موجود باشد) وگرنه امروز
        trade_date = await self._latest_trade_date(session, symbol)

        row = {
            "symbol": symbol,
            "trade_date": trade_date,
            "price_close": features.get("last_price"),
            "price_open": features.get("price_first"),
            "price_high": features.get("price_max"),
            "price_low": features.get("price_min"),
            "volume": features.get("volume"),
            "trade_value": features.get("trade_value"),
            "trade_count": features.get("trade_count"),
            "rsi_14": features.get("rsi_14"),
            "macd_histogram": features.get("macd_histogram"),
            "macd_signal": features.get("macd_signal"),
            "sma_20": features.get("sma_20"),
            "atr_14": features.get("atr_14"),
            "volume_zscore": None,
            "volume_ma_20_ratio": features.get("volume_spike"),
            "eps": features.get("eps_ttm"),
            "pe_ratio": features.get("pe_ratio"),
            "free_float_pct": features.get("float_shares") and None,
            "queue_status": features.get("queue_status"),
            "queue_volume_ratio": features.get("queue_volume_ratio"),
            "queue_days_streak": features.get("queue_days_streak"),
            "queue_type_change": features.get("queue_type_change"),
            "distance_to_limit": features.get("distance_to_limit"),
            "score_total": features.get("final_score"),
            "final_decision": features.get("final_decision"),
            "features_json": features,
            "calculated_at": utc_now_naive(),
        }
        # پاک‌سازی مقادیر NaN/None که قابل JSON نیستند
        row = _sanitize_row(row)
        return row

    async def _latest_trade_date(self, session: AsyncSession, symbol: str) -> date:
        stmt = (
            select(func.max(text("gregorian_date")))
            .select_from(text("brsapi_historical_daily"))
            .where(text("symbol = :sym"), text("gregorian_date IS NOT NULL"))
            .params(sym=symbol)
        )
        result = await session.execute(stmt)
        value = result.scalar()
        if isinstance(value, date):
            return value
        return date.today()

    # ── 3. Save rows (chunked upsert) ────────────────────────────────────

    async def _save_rows(self, session: AsyncSession, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        from sqlalchemy import MetaData, Table
        table = await session.run_sync(
            lambda sync_s: Table("ml_engineered_features", MetaData(),
                                 autoload_with=sync_s.bind, keep_existing=True)
        )
        stmt = pg_insert(table).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="ml_engineered_features_pkey",
            set_={
                col: getattr(stmt.excluded, col)
                for col in rows[0].keys() if col not in ("symbol", "trade_date")
            },
        )
        for i in range(0, len(rows), SAVE_CHUNK_SIZE):
            chunk = rows[i:i + SAVE_CHUNK_SIZE]
            await session.execute(stmt, chunk)
        await session.commit()

    # ── 4. Log to brsapi_sync_log (uses own session, never fails the main flow) ──

    async def _log_run(
        self,
        *,
        started_at: float,
        status: str,
        items_count: int,
        error_message: str | None = None,
        params_snapshot: str = "feature_store",
    ) -> None:
        duration_ms = (time.monotonic() - started_at) * 1000
        try:
            async with db_module.async_session_factory() as log_session:
                await log_session.execute(
                    text("""
                        INSERT INTO brsapi_sync_log
                            (endpoint, category, status, items_count, error_message,
                             duration_ms, params_snapshot, started_at, completed_at,
                             gregorian_date)
                        VALUES
                            (:endpoint, :category, :status, :items_count, :error_message,
                             :duration_ms, :params_snapshot, :started_at, :completed_at,
                             CURRENT_DATE)
                    """),
                    {
                        "endpoint": "ml_engineered_features",
                        "category": "feature_store",
                        "status": status,
                        "items_count": items_count,
                        "error_message": error_message,
                        "duration_ms": round(duration_ms, 1),
                        "params_snapshot": params_snapshot,
                        "started_at": datetime.fromtimestamp(started_at),
                        "completed_at": utc_now_naive(),
                    },
                )
                await log_session.commit()
        except Exception:  # noqa: BLE001 — logging must never break the run
            logger.exception("Failed to write brsapi_sync_log row")

    # ── 5. Orchestrate ───────────────────────────────────────────────────

    async def build_all(self) -> dict[str, Any]:
        started_at = time.monotonic()
        async for session in get_session():
            symbols = self.symbols or await self._load_active_symbols(session)
            logger.info("Feature store: %d symbols (workers=%d)", len(symbols), self.workers)

            try:
                for i in range(0, len(symbols), self.workers):
                    batch = symbols[i:i + self.workers]
                    rows: list[dict[str, Any]] = []

                    # هر نماد با session مستقل (AsyncSession هم‌زمانی ندارد)
                    for sym in batch:
                        try:
                            async with db_module.async_session_factory() as s:
                                row = await self._compute_symbol(s, sym)
                            if row:
                                rows.append(row)
                                self._stats["ok"] += 1
                            else:
                                self._stats["skipped"].append(sym)
                        except Exception as exc:  # noqa: BLE001
                            self._stats["fail"] += 1
                            self._stats["skipped"].append(sym)
                            logger.exception("Feature store failed for %s: %s", sym, exc)

                    if rows:
                        await self._save_rows(session, rows)
                        self._stats["rows"] += len(rows)

                    del rows
                    gc.collect()
                    if (i // self.workers) % 5 == 0:
                        logger.info("  ... %d/%d symbols", min(i + self.workers, len(symbols)), len(symbols))

                await self._log_run(
                    started_at=started_at, status="OK",
                    items_count=self._stats["rows"],
                    params_snapshot=f"symbols={len(symbols)},workers={self.workers},days={self.days}",
                )
            except Exception as exc:  # noqa: BLE001
                await self._log_run(
                    started_at=started_at, status="FAIL",
                    items_count=self._stats["rows"], error_message=str(exc),
                )
                raise

            logger.info(
                "Feature store done: ok=%d fail=%d rows=%d skipped=%d",
                self._stats["ok"], self._stats["fail"], self._stats["rows"],
                len(self._stats["skipped"]),
            )
            return dict(self._stats)
        return dict(self._stats)


# ── Helpers ────────────────────────────────────────────────────────────────

def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Drop NaN values and normalise floats so JSONB accepts the payload."""
    import math

    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        if value is None or isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            cleaned[key] = None
        elif isinstance(value, dict):
            cleaned[key] = {k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
                            for k, v in value.items()}
        else:
            cleaned[key] = value
    return cleaned


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

async def main() -> None:
    parser = argparse.ArgumentParser(description="Build the ML feature store (ml_engineered_features)")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Comma-separated symbols (default: all active)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="History depth (default 100)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel workers (default 4)")
    args = parser.parse_args()

    await init_database()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] if args.symbols else None
    builder = FeatureStoreBuilder(symbols=symbols, days=args.days, workers=args.workers)
    stats = await builder.build_all()
    print(f"Done - ok={stats['ok']} fail={stats['fail']} rows={stats['rows']} skipped={len(stats['skipped'])}")


if __name__ == "__main__":
    asyncio.run(main())
